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

    def __init__(self, apkg_builder=None, submitted_questions_repository: SubmittedQuestionsRepository | None = None, llm_client=None) -> None:
        self.apkg_builder = apkg_builder
        self.submitted_questions_repository = submitted_questions_repository
        self.llm_client = llm_client
        self.alternative_explanation_service = AlternativeExplanationService()

    async def _resolve_correct_answer(self, snapshot) -> str | None:
        """Use Claude to resolve correct answer when not in database."""
        if self.llm_client is None or not snapshot.alternatives:
            return None
        try:
            alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in snapshot.alternatives)
            prompt = (
                f"Você é um especialista em questões do ENEM. "
                f"Analise esta questão e determine qual é a alternativa correta.\n\n"
                f"Enunciado:\n{snapshot.content}\n\n"
                f"Alternativas:\n{alternatives_text}\n\n"
                f"Responda APENAS com a letra da alternativa correta (A, B, C, D ou E)."
            )
            response = await self.llm_client.create_message(
                model="claude-sonnet-4-6",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            if response.content and len(response.content) > 0:
                raw = response.content[0].text.strip().upper()
                # Extract first standalone letter A-E (handles "D)", "Letra D", "D." etc.)
                match = re.search(r'\b([A-E])\b', raw)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.warning(f"socratico_service: failed to resolve correct answer: {e}")
        return None

    async def _generate_first_attempt_explanation(self, snapshot, correct_answer: str, first_wrong_answer: str) -> str:
        """Explain why the first attempt was wrong and why the correct answer is right."""
        if self.llm_client is None or not correct_answer or not first_wrong_answer:
            return ""
        try:
            alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in (snapshot.alternatives or []))
            prompt = (
                f"Você é uma tutora socrática do ENEM. A aluna errou na primeira tentativa e depois acertou.\n\n"
                f"Enunciado:\n{snapshot.content}\n\n"
                f"Alternativas:\n{alternatives_text}\n\n"
                f"Primeira resposta da aluna (ERRADA): {first_wrong_answer}\n"
                f"Resposta correta: {correct_answer}\n\n"
                f"Gere uma explicação pedagógica que:\n"
                f"1. Explique brevemente por que a alternativa {first_wrong_answer} está errada (1-2 linhas)\n"
                f"2. Explique por que a alternativa {correct_answer} é correta (2-3 linhas)\n"
                f"3. Para cada uma das outras alternativas incorretas, uma frase curta explicando por que está errada\n\n"
                f"Seja direta, acolhedora e concisa. Não use introduções longas."
            )
            response = await self.llm_client.create_message(
                model="claude-sonnet-4-6",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"socratico_service: failed to generate first attempt explanation: {e}")
        return ""

    async def _generate_explanation(self, snapshot, correct_answer: str) -> str:
        """Generate pedagogical explanation using Claude."""
        if self.llm_client is None or not correct_answer:
            return ""
        try:
            alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in snapshot.alternatives)
            prompt = (
                f"Você é uma tutora expert em ENEM. Gere uma explicação pedagógica clara e concisa para esta questão.\n\n"
                f"Enunciado:\n{snapshot.content}\n\n"
                f"Alternativas:\n{alternatives_text}\n\n"
                f"Resposta correta: {correct_answer}\n\n"
                f"Crie uma explicação que:\n"
                f"1. Explique POR QUE a alternativa {correct_answer} é correta (2-3 linhas)\n"
                f"2. Para cada alternativa incorreta, uma frase explicando por que está errada\n\n"
                f"Formato: Mantenha conciso e pedagógico, focando no aprendizado."
            )
            response = await self.llm_client.create_message(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"socratico_service: failed to generate explanation: {e}")
        return ""

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

        # Generate Q1 with Claude hint if available, otherwise generic
        q1_text = await self._generate_q1_text(snapshot)

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

    async def _generate_q1_text(self, snapshot) -> str:
        """Generate Socratic Q1 hint using Claude, or fallback to generic."""
        if self.llm_client is not None and snapshot.content:
            try:
                alternatives_text = "\n".join(
                    f"{alt.label}) {alt.text}" for alt in (snapshot.alternatives or [])
                )
                prompt = (
                    f"Você é uma tutora socrática do ENEM. A aluna errou esta questão.\n\n"
                    f"Enunciado:\n{snapshot.content}\n\n"
                    f"Alternativas:\n{alternatives_text}\n\n"
                    f"Gere UMA dica socrática curta (2-3 linhas) que:\n"
                    f"1. NÃO revele a resposta correta\n"
                    f"2. Aponte o conceito-chave ou a palavra central do enunciado que a aluna deve reler\n"
                    f"3. Termine pedindo para ela responder só com A, B, C, D ou E\n\n"
                    f"Seja direta e acolhedora. Não use saudações nem introduções longas."
                )
                response = await self.llm_client.create_message(
                    model="claude-sonnet-4-6",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                if response.content and len(response.content) > 0:
                    return response.content[0].text.strip()
            except Exception as e:
                logger.warning(f"socratico_service: failed to generate Q1 hint: {e}")

        # Generic fallback
        return "\n".join([
            "Você errou a primeira tentativa, então vamos fazer uma releitura juntas. 🤔",
            "",
            "Relê o enunciado com atenção — geralmente tem uma palavra-chave que muda tudo.",
            "",
            "Qual alternativa você marca agora? Responde só com A, B, C, D ou E.",
        ])

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

        session.state = SessionState.WAITING_SOCRATIC_Q2
        session.metadata.state = SessionState.WAITING_SOCRATIC_Q2
        q2_text = "Quase lá. Me responde só com a letra: A, B, C, D ou E."

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

        # Resolve correct answer and explanation with Claude if missing
        if not snapshot.correct_alternative:
            resolved = await self._resolve_correct_answer(snapshot)
            if resolved:
                snapshot.correct_alternative = resolved
        if not snapshot.explanation and snapshot.correct_alternative:
            snapshot.explanation = await self._generate_explanation(snapshot, snapshot.correct_alternative)

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

    def _build_explanation(self, correct_answer: str, explanation: str) -> str:
        """Build final explanation message."""
        if not correct_answer:
            return (
                "Essa questão parece ter um gráfico ou dado visual que não consigo analisar só pelo texto. 📊\n\n"
                "Você sabe qual é o gabarito? Me conta a alternativa correta e eu explico o raciocínio completo."
            )
        lines = [
            f"A resposta correta é a alternativa **{correct_answer}**. ✅",
            "",
            "**Por quê?**",
        ]
        if explanation:
            lines.append(explanation)
        else:
            lines.append("Não consegui gerar a explicação automática para essa questão. Me pergunta que explico o racional passo a passo!")
        lines += ["", "Isso não apaga o que você tentou antes; só mostra exatamente onde vale ajustar a leitura."]
        return "\n".join(lines)

    async def _finalize_retry_attempt(self, session: SessionRecord, student_answer: str) -> ServiceResult:
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
            )
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        correct_answer = session.question_snapshot.correct_alternative or ""
        # If no correct answer in snapshot, resolve with Claude
        if not correct_answer:
            resolved = await self._resolve_correct_answer(session.question_snapshot)
            if resolved:
                correct_answer = resolved
                session.question_snapshot.correct_alternative = correct_answer
        # If no explanation, generate with Claude
        if not session.question_snapshot.explanation and correct_answer:
            session.question_snapshot.explanation = await self._generate_explanation(
                session.question_snapshot, correct_answer
            )
        # Normalize answer to uppercase (defensive: may receive lowercase from parse)
        student_answer_normalized = student_answer.strip().upper()
        if student_answer_normalized == correct_answer:
            session.state = SessionState.WAITING_FOLLOWUP_CHAT
            session.metadata.state = SessionState.WAITING_FOLLOWUP_CHAT
            first_wrong_answer = session.metadata.pending_student_answer or ""
            session.metadata.retry_attempts = 0
            session.metadata.review_card = ReviewCard()
            session.metadata.anki = AnkiMetadata(status="not_needed")
            self.alternative_explanation_service.ensure_alternative_explanations(session)
            self._mark_submitted_question_result(
                session=session,
                answered_correct=True,
                sent_to_anki=False,
                apkg_generated=False,
            )
            logger.info(f"socratico_service: retry corrected for session={session.session_id}")

            explanation_text = await self._generate_first_attempt_explanation(
                session.question_snapshot, correct_answer, first_wrong_answer
            )
            alternatives_review = self._build_alternatives_review(
                session.question_snapshot,
                correct_answer,
            )

            reply_parts = [f"✅ Boa, agora foi. A correta é **{correct_answer}**."]
            if first_wrong_answer:
                reply_parts += [
                    "",
                    f"Na primeira tentativa você marcou **{first_wrong_answer}**.",
                    f"Antes de seguir, tenta me dizer em uma frase: o que te puxou para a alternativa **{first_wrong_answer}**?",
                ]
            if explanation_text:
                reply_parts += ["", "Sobre a primeira tentativa:", "", explanation_text]
            if alternatives_review:
                reply_parts += ["", "Aqui vai a questão comentada para comparar as alternativas:", "", alternatives_review]
            reply_parts += ["", "Se preferir, já me manda a próxima questão."]

            return ServiceResult(
                state=SessionState.WAITING_FOLLOWUP_CHAT,
                reply_text="\n".join(reply_parts),
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

    def _build_alternatives_review(self, snapshot, correct_answer: str) -> str:
        if not snapshot.alternatives:
            return ""

        lines: list[str] = []
        for alternative in snapshot.alternatives:
            if alternative.label == correct_answer:
                explanation = alternative.explanation or snapshot.explanation or "Esta é a alternativa correta."
                lines.append(f"**{alternative.label}) {alternative.text}** — correta\n{explanation}")
            else:
                explanation = self._clean_incorrect_alternative_explanation(
                    alternative.explanation,
                    alternative.text,
                    correct_answer,
                    self._alternative_text(snapshot, correct_answer),
                ) or "Compare com a alternativa correta indicada no gabarito."
                lines.append(f"**{alternative.label}) {alternative.text}** — incorreta\n{explanation}")
        return "\n".join(lines)

    def _alternative_text(self, snapshot, label: str) -> str:
        for alternative in snapshot.alternatives or []:
            if alternative.label == label:
                return alternative.text
        return ""

    def _clean_incorrect_alternative_explanation(
        self,
        explanation: str,
        alternative_text: str,
        correct_answer: str,
        correct_text: str,
    ) -> str:
        if not explanation:
            return ""
        bloated_marker = " A explicação da correta é: "
        if bloated_marker in explanation:
            return explanation.split(bloated_marker, 1)[0].strip()
        if len(explanation) > 700 or "## Por que" in explanation or "\n---" in explanation:
            correct_reference = (
                f"A alternativa {correct_answer} ({correct_text}) é a correta."
                if correct_answer and correct_text
                else "Compare com a alternativa correta indicada no gabarito."
            )
            return (
                f"Incorreta: {alternative_text} não corresponde ao gabarito confirmado. "
                f"{correct_reference}"
            )
        return explanation

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
