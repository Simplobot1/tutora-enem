"""Service for Socratic Questioning Mode.

M3-S1: After incorrect answer, guide student with up to 2 questions before revealing answer.
- If mood is "cansada" (tired), skip to direct explanation
- Otherwise, ask guiding questions to help student self-discover the answer
"""

from __future__ import annotations

import logging
import re

from app.domain.session_metadata import AnkiMetadata, ReviewCard, SessionMetadata
from app.domain.models import ServiceResult, SessionRecord
from app.domain.states import SessionState
from app.repositories.submitted_questions_repository import SubmittedQuestionsRepository
from app.services.alternative_explanation_service import AlternativeExplanationService

logger = logging.getLogger(__name__)


class SocraticoService:
    """Guide student through Socratic questioning after incorrect answer."""

    def __init__(self, apkg_builder=None, submitted_questions_repository: SubmittedQuestionsRepository | None = None) -> None:
        self.apkg_builder = apkg_builder
        self.submitted_questions_repository = submitted_questions_repository
        self.alternative_explanation_service = AlternativeExplanationService()

    async def route_incorrect_answer(self, session: SessionRecord) -> ServiceResult:
        """Determine whether to use Socratic mode or direct explanation.

        If mood is "cansada", skip Socratic and go direct.
        Otherwise, start with first Socratic question.
        """
        mood = session.mood or ""
        is_tired = "cansada" in mood.lower()

        logger.info(
            f"socratico_service: routing incorrect answer for session={session.session_id}, "
            f"mood={mood}, is_tired={is_tired}"
        )

        if is_tired:
            # Skip Socratic, go directly to explanation
            return await self.skip_to_direct_explanation(session)
        else:
            # Start Socratic mode with Q1
            return await self.generate_q1(session)

    async def generate_q1(self, session: SessionRecord) -> ServiceResult:
        """Generate first Socratic question (Q1).

        Goal: Guide student to reconsider the question without giving answer.
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )

        snapshot = session.question_snapshot
        session.state = SessionState.WAITING_SOCRATIC_Q1
        session.metadata.state = SessionState.WAITING_SOCRATIC_Q1

        # Generate Q1 based on question content
        q1_text = self._build_q1(snapshot.content, snapshot.subject or "")

        logger.info(f"socratico_service: Q1 generated for session={session.session_id}")

        return ServiceResult(
            state=SessionState.WAITING_SOCRATIC_Q1,
            reply_text=q1_text,
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "question_step": "q1",
            },
        )

    async def process_q1_response(self, session: SessionRecord, student_response: str) -> ServiceResult:
        """Process student's response to Q1.

        Q1 now asks for a forced retry in A-E format. If the user still doesn't
        answer with an alternative, escalate to a final explicit prompt (Q2).
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        parsed = self._parse_alternative(student_response)
        if parsed is not None:
            return await self._finalize_retry_attempt(session, parsed)

        snapshot = session.question_snapshot
        session.state = SessionState.WAITING_SOCRATIC_Q2
        session.metadata.state = SessionState.WAITING_SOCRATIC_Q2
        q2_text = self._build_q2(
            snapshot.content,
            snapshot.correct_alternative or "",
            student_response,
        )

        logger.info(f"socratico_service: Q2 generated for session={session.session_id}")

        return ServiceResult(
            state=SessionState.WAITING_SOCRATIC_Q2,
            reply_text=q2_text,
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "question_step": "q2",
            },
        )

    async def process_q2_response(self, session: SessionRecord, student_response: str) -> ServiceResult:
        """Process student's response to Q2.

        Q2 is the last forced retry. A second wrong answer generates the review deck.
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )
        parsed = self._parse_alternative(student_response)
        if parsed is None:
            return ServiceResult(
                state=SessionState.WAITING_SOCRATIC_Q2,
                reply_text="Me responde só com a letra da alternativa, tá? A, B, C, D ou E.",
                metadata={
                    "flow": session.flow.value,
                    "session_id": session.session_id,
                    "question_step": "q2",
                },
            )

        return await self._finalize_retry_attempt(session, parsed)

    async def skip_to_direct_explanation(self, session: SessionRecord) -> ServiceResult:
        """Skip Socratic mode and provide direct explanation (for tired students)."""
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )

        snapshot = session.question_snapshot
        session.state = SessionState.WAITING_FOLLOWUP_CHAT
        session.metadata.state = SessionState.WAITING_FOLLOWUP_CHAT

        # Build explanation message
        explanation_text = self._build_explanation(
            snapshot.correct_alternative or "",
            snapshot.explanation,
        )
        self._mark_submitted_question_result(
            session=session,
            answered_correct=False,
            sent_to_anki=True,
            apkg_generated=False,
        )

        logger.info(f"socratico_service: direct explanation (tired mode) for session={session.session_id}")

        return ServiceResult(
            state=SessionState.WAITING_FOLLOWUP_CHAT,
            reply_text=(
                "Tudo bem, vamos no caminho mais leve.\n\n"
                f"{explanation_text}\n\n"
                "Se quiser, eu também posso te resumir o racional em uma frase ou comparar as alternativas com você, sem pressa."
            ),
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "learning_path": "direct_explanation",
            },
        )

    def _build_q1(self, question_content: str, subject: str) -> str:
        """Build first Socratic question (Q1).

        Ask student to reconsider and commit to a new alternative.
        """
        return "\n".join(
            [
                "Você errou a primeira tentativa, então vamos fazer uma releitura estratégica juntas. 🤔",
                "",
                "Pensa no que a questão quer comparar: medidas preventivas parecidas.",
                "O ponto central aqui é prevenção por carne crua ou malcozida.",
                "",
                "Relê as alternativas e me responde de novo só com A, B, C, D ou E.",
            ]
        )

    def _build_q2(self, question_content: str, correct_alt: str, q1_response: str) -> str:
        """Build second Socratic question (Q2).

        Dig deeper based on Q1 response.
        """
        return "\n".join(
            [
                "Quase lá. Só preciso da resposta no formato certinho. 👀",
                "",
                "Quero a sua segunda tentativa objetiva.",
                "Qual alternativa você marca agora?",
                "",
                "Responde só com A, B, C, D ou E.",
            ]
        )

    def _build_explanation(self, correct_answer: str, explanation: str) -> str:
        """Build final explanation message."""
        return "\n".join(
            [
                f"A resposta correta é a alternativa **{correct_answer}**. ✅",
                "",
                "**Por quê?**",
                explanation or "Ainda não tenho uma explicação confiável para essa questão específica, mas o gabarito correto já foi registrado.",
                "",
                "Isso não apaga o que você tentou antes; só mostra exatamente onde vale ajustar a leitura.",
            ]
        )

    async def _finalize_retry_attempt(self, session: SessionRecord, student_answer: str) -> ServiceResult:
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        correct_answer = session.question_snapshot.correct_alternative or ""
        # Normalize answer to uppercase (defensive: may receive lowercase from parse)
        student_answer_normalized = student_answer.strip().upper()
        if student_answer_normalized == correct_answer:
            session.state = SessionState.WAITING_FOLLOWUP_CHAT
            session.metadata.state = SessionState.WAITING_FOLLOWUP_CHAT
            session.metadata.retry_attempts = 0
            session.metadata.review_card = ReviewCard()
            session.metadata.anki = AnkiMetadata(status="not_needed")
            self._mark_submitted_question_result(
                session=session,
                answered_correct=True,
                sent_to_anki=False,
                apkg_generated=False,
            )
            logger.info(f"socratico_service: retry corrected for session={session.session_id}")
            return ServiceResult(
                state=SessionState.WAITING_FOLLOWUP_CHAT,
                reply_text=(
                    f"✅ Boa, agora foi. A correta é **{correct_answer}**.\n\n"
                    "Gostei da insistência, porque você voltou para a questão e ajustou a leitura.\n"
                    "Se quiser, me diz qual foi a virada no seu raciocínio ou já manda a próxima."
                ),
                metadata={
                    "flow": session.flow.value,
                    "session_id": session.session_id,
                    "learning_path": "retry_success",
                    "is_correct": True,
                },
            )

        session.state = SessionState.WAITING_FOLLOWUP_CHAT
        session.metadata.state = SessionState.WAITING_FOLLOWUP_CHAT
        session.metadata.retry_attempts = 2
        self.alternative_explanation_service.ensure_alternative_explanations(session)

        apkg_path = None
        if self.apkg_builder is not None:
            try:
                apkg_path = self.apkg_builder.build_apkg_from_session(session)
            except Exception as exc:
                logger.warning("socratico_service: failed to build apkg for session=%s error=%s", session.session_id, exc)

        session.metadata.anki = AnkiMetadata(
            status="prepared" if apkg_path else "queued_local_build",
            builder_mode="review_card",
            apkg_path=apkg_path,
        )
        self._mark_submitted_question_result(
            session=session,
            answered_correct=False,
            sent_to_anki=True,
            apkg_generated=bool(apkg_path),
            apkg_path=apkg_path,
        )
        logger.info(f"socratico_service: second retry failed for session={session.session_id}, apkg={apkg_path}")

        explanation_text = self._build_explanation(
            correct_answer,
            session.question_snapshot.explanation,
        )
        apkg_notice = (
            "\n\n📦 Preparei seu deck de revisão. Segue abaixo o arquivo para importar no Anki."
            if apkg_path
            else "\n\n📦 Deixei a revisão pronta para gerar o `.apkg` localmente."
        )
        return ServiceResult(
            state=SessionState.WAITING_FOLLOWUP_CHAT,
            reply_text=(
                "❌ Segunda tentativa ainda incorreta.\n\n"
                "Mas tudo bem: esse tipo de erro é exatamente o tipo que vale transformar em revisão.\n\n"
                f"{explanation_text}"
                f"{apkg_notice}\n\n"
                "Se quiser, eu posso te explicar o racional passo a passo ou comparar alternativa por alternativa com você."
            ),
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "learning_path": "retry_failed_apkg",
                "is_correct": False,
                "apkg_path": apkg_path,
            },
        )

    def _parse_alternative(self, raw_text: str) -> str | None:
        normalized = raw_text.strip().upper()
        if normalized in {"A", "B", "C", "D", "E"}:
            return normalized
        match = re.search(r"\b([A-E])\b", normalized)
        if match is None:
            return None
        return match.group(1)

    def _mark_submitted_question_result(
        self,
        *,
        session: SessionRecord,
        answered_correct: bool,
        sent_to_anki: bool,
        apkg_generated: bool,
        apkg_path: str | None = None,
    ) -> None:
        if not isinstance(session.metadata, SessionMetadata):
            return
        snapshot_id = session.metadata.question_ref.snapshot_id
        if self.submitted_questions_repository is None or not snapshot_id:
            return
        review_card = session.metadata.review_card
        error_type = None
        if review_card and (review_card.front or review_card.back):
            match = re.search(r"Classificação(?:\s+do\s+erro)?:\s*([A-Za-zÀ-ÿ_]+)", f"{review_card.front}\n{review_card.back}")
            if match is not None:
                error_type = match.group(1)
        self.submitted_questions_repository.mark_result(
            snapshot_id,
            answered_correct=answered_correct,
            retry_attempts=session.metadata.retry_attempts,
            sent_to_anki=sent_to_anki,
            apkg_generated=apkg_generated,
            apkg_path=apkg_path,
            error_type=error_type,
        )
