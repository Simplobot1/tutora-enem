from __future__ import annotations

import logging
from pathlib import Path
import re

from app.clients.llm import LLMClient
from app.adapters.telegram_api import TelegramGateway
from app.domain.session_metadata import AnkiMetadata, QuestionRef, ReviewCard, SessionMetadata
from app.domain.models import InboundEvent, ServiceResult, SessionRecord
from app.domain.states import SessionFlow
from app.domain.states import SessionState
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_answer_service import MeTestaAnswerService
from app.services.session_service import SessionService
from app.services.socratico_service import SocraticoService

logger = logging.getLogger(__name__)


class MeTestaService:
    def __init__(
        self,
        session_service: SessionService,
        telegram_gateway: TelegramGateway,
        llm_client: LLMClient,
        entry_service: MeTestaEntryService,
        answer_service: MeTestaAnswerService | None = None,
        socratico_service: SocraticoService | None = None,
    ) -> None:
        self.session_service = session_service
        self.telegram_gateway = telegram_gateway
        self.llm_client = llm_client
        self.entry_service = entry_service
        self.answer_service = answer_service
        self.socratico_service = socratico_service

    def _reset_session_for_restart(self, session: SessionRecord) -> None:
        setattr(session, "state", SessionState.IDLE)
        setattr(session, "source_mode", "student_content_only")
        setattr(session, "question_snapshot", None)
        setattr(session, "question_id", None)
        metadata = getattr(session, "metadata", None)
        if metadata is not None:
            metadata.question_snapshot = None
            metadata.question_id = None
            metadata.question_ref = QuestionRef()
            metadata.pending_student_answer = None
            metadata.retry_attempts = 0
            metadata.review_card = ReviewCard()
            metadata.anki = AnkiMetadata()
            metadata.last_user_message = {}

    async def _finalize_result(self, event: InboundEvent, result: ServiceResult) -> ServiceResult:
        if result.should_reply and result.reply_text:
            await self.telegram_gateway.send_text(
                event.chat_id,
                result.reply_text,
                reply_markup=result.metadata.get("telegram_reply_markup"),
            )
        apkg_path = result.metadata.get("apkg_path")
        if isinstance(apkg_path, str) and apkg_path:
            path = Path(apkg_path)
            if path.is_file():
                await self.telegram_gateway.send_document(
                    event.chat_id,
                    apkg_path,
                    caption="Aqui está seu deck de revisão em `.apkg` para importar no Anki.",
                )
        self._mark_event_processed(event)
        return result

    def _event_fingerprint(self, event: InboundEvent) -> str:
        if event.update_id is not None:
            return f"update:{event.update_id}"
        if event.message_id is not None:
            return f"message:{event.message_id}"
        return ""

    def _is_duplicate_event(self, session: SessionRecord, event: InboundEvent) -> bool:
        if not isinstance(session.metadata, SessionMetadata):
            return False
        fingerprint = self._event_fingerprint(event)
        return bool(fingerprint and session.metadata.llm_trace.get("last_processed_event") == fingerprint)

    def _mark_event_processed(self, event: InboundEvent) -> None:
        fingerprint = self._event_fingerprint(event)
        if not fingerprint:
            return
        session = self.session_service.repository.get_active_session(event.telegram_id, SessionFlow.ME_TESTA)
        if session is None or not isinstance(session.metadata, SessionMetadata):
            return
        session.metadata.llm_trace["last_processed_event"] = fingerprint
        session.metadata.llm_trace["last_processed_message_id"] = event.message_id
        session.metadata.llm_trace["last_processed_update_id"] = event.update_id
        self.session_service.save(session)

    def _is_greeting(self, event: InboundEvent) -> bool:
        normalized = (event.text or event.caption).strip().lower()
        return normalized in {"oi", "ola", "olá", "/start", "start"}

    def _is_restart_intent(self, event: InboundEvent) -> bool:
        normalized = (event.text or event.caption).strip().lower()
        return normalized in {
            "/nova",
            "/novo",
            "/reset",
            "nova questão",
            "nova questao",
            "outra questão",
            "outra questao",
            "trocar questão",
            "trocar questao",
            "resetar",
            "recomeçar",
            "recomecar",
            "começar de novo",
            "comecar de novo",
        }

    def _looks_like_question_submission(self, event: InboundEvent) -> bool:
        text = (event.text or event.caption).strip()
        if event.attachment.file_id:
            return True
        if len(text) < 20:
            return False
        if self.entry_service.question_snapshot_service.build_from_text(text) is not None:
            return True
        has_alternative_block = len(re.findall(r"(?:^|[\n\r])\s*[A-E](?:\)|\.|:|-)?\s+", text, re.MULTILINE)) >= 4
        return has_alternative_block

    def _build_mood_keyboard(self) -> dict[str, object]:
        return {
            "inline_keyboard": [
                [
                    {"text": "😴 Cansada", "callback_data": "mood:cansada"},
                    {"text": "😐 Normal", "callback_data": "mood:normal"},
                    {"text": "⚡ Animada", "callback_data": "mood:animada"},
                ],
                [
                    {"text": "💭 Ansiosa", "callback_data": "mood:ansiosa"},
                ]
            ]
        }

    async def _handle_check_in(self, session: SessionRecord, event: InboundEvent) -> ServiceResult:
        self._reset_session_for_restart(session)
        self.session_service.save(session)
        return ServiceResult(
            state=SessionState.IDLE,
            reply_text=(
                "Oi! Eu sou a Tutora ENEM. Antes da questão, me conta rapidinho como você tá hoje para eu ajustar o ritmo com você:"
            ),
            metadata={
                "entrypoint": "check_in",
                "telegram_reply_markup": self._build_mood_keyboard(),
            },
        )

    async def _handle_followup_chat(self, session: SessionRecord, event: InboundEvent) -> ServiceResult:
        text = (event.text or event.caption).strip()
        normalized = text.lower()
        snapshot = session.question_snapshot
        explanation = snapshot.explanation if snapshot is not None else ""
        correct_answer = snapshot.correct_alternative if snapshot is not None else None
        apkg_path = None
        if hasattr(session.metadata, "anki") and session.metadata.anki is not None:
            apkg_path = session.metadata.anki.apkg_path

        if any(token in normalized for token in ["racional", "por que", "por quê", "explica", "explicacao", "explicação"]):
            reply = "\n".join(
                [
                    "Boa pergunta. Vamos organizar isso juntas.",
                    "O raciocínio mais seguro aqui é olhar o tipo de prevenção que a questão está pedindo.",
                    explanation or "A chave é comparar a lógica preventiva da alternativa correta com a doença citada no enunciado.",
                    "",
                    (
                        f"Em resumo: a melhor resposta era **{correct_answer}**."
                        if correct_answer
                        else "Se quiser, eu também posso resumir isso em uma frase bem curta."
                    ),
                    "Se quiser, posso ainda comparar as alternativas uma por uma com você.",
                ]
            )
            metadata = {
                "session_id": session.session_id,
                "followup_chat": True,
            }
        elif any(token in normalized for token in ["anki", "apkg", "colar", "importar"]):
            apkg_line = (
                "Preparei seu deck e vou te mandar o arquivo `.apkg` logo abaixo."
                if apkg_path
                else "Neste momento a revisão ficou preparada, mas o arquivo `.apkg` ainda depende do builder local."
            )
            reply = "\n".join(
                [
                    "Não é só colar no Anki.",
                    apkg_line,
                    "No Anki, você importa esse arquivo pelo menu `Arquivo > Importar`.",
                    "Quando importar, o deck e os cards entram prontos para revisão.",
                    "",
                    "Se quiser, eu também posso te explicar o racional da questão antes de você revisar.",
                ]
            )
            metadata = {
                "session_id": session.session_id,
                "followup_chat": True,
                "apkg_path": apkg_path,
            }
        elif any(token in normalized for token in ["próxima", "proxima", "outra questão", "manda outra"]):
            reply = "Perfeito. Me manda a próxima questão completa com enunciado e alternativas A-E que eu sigo com você."
            metadata = {
                "session_id": session.session_id,
                "followup_chat": True,
            }
        else:
            # Always send full alternatives review when there's an active snapshot
            alternatives_review = ""
            if snapshot is not None:
                # Resolve correct_answer on-the-fly if missing
                if not correct_answer and self.socratico_service is not None:
                    resolved = await self.socratico_service._resolve_correct_answer(snapshot)
                    if resolved:
                        correct_answer = resolved
                        snapshot.correct_alternative = resolved

                # Generate explanation if still missing
                if correct_answer and not snapshot.explanation and self.socratico_service is not None:
                    snapshot.explanation = await self.socratico_service._generate_explanation(snapshot, correct_answer)

                if correct_answer and self.answer_service is not None:
                    alternatives_review = self.answer_service._build_alternatives_review(snapshot, correct_answer)
                    if snapshot.explanation and not any(alt.explanation for alt in (snapshot.alternatives or [])):
                        alternatives_review = snapshot.explanation
                elif snapshot.explanation:
                    alternatives_review = snapshot.explanation

            if alternatives_review:
                reply = "\n".join(
                    [
                        "Aqui estão todas as alternativas comentadas:",
                        "",
                        alternatives_review,
                        "",
                        "Se preferir, já me manda a próxima questão.",
                    ]
                )
            else:
                reply = "Me manda a próxima questão completa com enunciado e alternativas A-E que eu sigo com você."
            metadata = {
                "session_id": session.session_id,
                "followup_chat": True,
            }

        self.session_service.save(session)
        return ServiceResult(
            state=SessionState.WAITING_FOLLOWUP_CHAT,
            reply_text=reply,
            metadata=metadata,
        )

    async def _handle_mood_callback(self, session, event: InboundEvent) -> ServiceResult:
        callback = event.callback_data.strip().lower()
        mood = callback.split(":", 1)[1] if ":" in callback else ""
        if mood not in {"cansada", "normal", "animada", "ansiosa"}:
            return ServiceResult(
                state=session.state,
                reply_text="Não consegui ler esse botão daqui. Toca em um dos humores para eu seguir com você.",
                metadata={"invalid_callback": event.callback_data},
            )
        self._reset_session_for_restart(session)
        session.mood = mood
        self.session_service.save(session)
        mood_message = {
            "cansada": (
                "Entendi. Se hoje você tá mais cansada, a gente vai no ritmo certo, sem te esmagar."
            ),
            "normal": (
                "Perfeito. Com a cabeça mais estável dá para olhar a questão com calma e construir bem o raciocínio."
            ),
            "animada": (
                "Aí sim. Vamos aproveitar essa energia para fazer uma leitura afiada e atacar a questão."
            ),
            "ansiosa": (
                "Recebi. Vamos organizar isso juntas e quebrar a questão em partes para tirar o peso."
            ),
        }[mood]
        return ServiceResult(
            state=SessionState.IDLE,
            reply_text=(
                f"{mood_message}\n\n"
                "Agora me manda a questão completa com enunciado e alternativas A-E."
            ),
            metadata={"mood": mood},
        )

    async def handle_event(self, event: InboundEvent) -> ServiceResult:
        session = self.session_service.get_or_create_active_session(
            telegram_id=event.telegram_id,
            chat_id=event.chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        if self._is_duplicate_event(session, event):
            logger.info(
                "me_testa_service: ignoring duplicate event for telegram_id=%s, event=%s",
                event.telegram_id,
                self._event_fingerprint(event),
            )
            return ServiceResult(
                state=session.state,
                reply_text="",
                should_reply=False,
                metadata={
                    "duplicate_event": True,
                    "session_id": session.session_id,
                },
            )

        logger.info(
            f"me_testa_service: handling event for telegram_id={event.telegram_id}, "
            f"session_id={session.session_id}, state={session.state}"
        )

        if event.input_mode == "callback" and event.callback_data.startswith("mood:"):
            result = await self._handle_mood_callback(session, event)
            return await self._finalize_result(event, result)

        if self._is_greeting(event):
            result = await self._handle_check_in(session, event)
            return await self._finalize_result(event, result)

        if self._is_restart_intent(event):
            self._reset_session_for_restart(session)
            self.session_service.save(session)
            result = ServiceResult(
                state=SessionState.IDLE,
                reply_text="Fechado. Zerei a questão anterior. Agora me manda a nova questão completa com enunciado e alternativas A-E.",
                metadata={"entrypoint": "manual_restart"},
            )
            return await self._finalize_result(event, result)

        if session.state == SessionState.WAITING_FOLLOWUP_CHAT:
            if self._looks_like_question_submission(event):
                self._reset_session_for_restart(session)
                self.session_service.save(session)
                result = await self.entry_service.handle_question_intake(event)
                return await self._finalize_result(event, result)
            result = await self._handle_followup_chat(session, event)
            return await self._finalize_result(event, result)

        # Intake: new question or fallback details
        if session.state in {SessionState.IDLE, SessionState.WAITING_FALLBACK_DETAILS, SessionState.DONE}:
            result = await self.entry_service.handle_question_intake(event)
            return await self._finalize_result(event, result)

        # Answer processing
        if session.state == SessionState.WAITING_ANSWER:
            if self._looks_like_question_submission(event):
                self._reset_session_for_restart(session)
                self.session_service.save(session)
                result = await self.entry_service.handle_question_intake(event)
                return await self._finalize_result(event, result)

            if self.answer_service is None:
                reply = "Tive um problema aqui para corrigir sua resposta agora. Se você quiser, me manda de novo em seguida que eu tento outra vez."
                logger.error(f"answer_service is None for telegram_id={event.telegram_id}")
                result = ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_answer_service"})
                return await self._finalize_result(event, result)

            result = await self.answer_service.process_answer(
                telegram_id=event.telegram_id,
                student_answer=event.text or event.caption,
                session=session,
            )
            return await self._finalize_result(event, result)

        if session.state == SessionState.WAITING_GABARITO:
            if self.answer_service is None:
                result = ServiceResult(
                    state=session.state,
                    reply_text="Tive um problema aqui para confirmar o gabarito agora. Me manda de novo em seguida que eu tento outra vez.",
                    metadata={"error": "no_answer_service"},
                )
                return await self._finalize_result(event, result)

            result = await self.answer_service.process_gabarito(
                session=session,
                gabarito_input=event.text or event.caption,
            )
            return await self._finalize_result(event, result)

        # Socratic mode: Q1 response
        if session.state == SessionState.WAITING_SOCRATIC_Q1:
            if self.socratico_service is None:
                reply = "Agora eu não consegui abrir o modo guiado, mas posso seguir de outro jeito se você me mandar a resposta de novo."
                logger.error(f"socratico_service is None for telegram_id={event.telegram_id}")
                result = ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_socratico_service"})
                return await self._finalize_result(event, result)

            result = await self.socratico_service.process_q1_response(
                session=session,
                student_response=event.text or event.caption,
            )
            self.session_service.save(session)
            return await self._finalize_result(event, result)

        # Socratic mode: Q2 response
        if session.state == SessionState.WAITING_SOCRATIC_Q2:
            if self.socratico_service is None:
                reply = "Agora eu não consegui continuar o modo guiado, mas se você me responder de novo eu retomo daqui."
                logger.error(f"socratico_service is None for telegram_id={event.telegram_id}")
                result = ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_socratico_service"})
                return await self._finalize_result(event, result)

            result = await self.socratico_service.process_q2_response(
                session=session,
                student_response=event.text or event.caption,
            )
            self.session_service.save(session)
            return await self._finalize_result(event, result)

        result = ServiceResult(
            state=session.state,
            reply_text="Recebi sua mensagem, mas esse pedaço do fluxo ainda não ficou redondo aqui. Se quiser, me manda a questão de novo que eu te recoloco no caminho certo.",
            metadata={"state": session.state},
        )
        return await self._finalize_result(event, result)
