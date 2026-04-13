"""Service for processing me-testa answers and classifications.

M2-S3: Handle answer submission, error classification, and review card preparation.
"""

from __future__ import annotations

from uuid import uuid4

from app.domain.error_classification import ErrorClassification, ErrorType
from app.domain.models import ServiceResult, SessionRecord
from app.domain.session_metadata import AnkiMetadata, ReviewCard, SessionMetadata
from app.domain.states import SessionState
from app.clients.llm import LLMClient
from app.repositories.submitted_questions_repository import SubmittedQuestionsRepository
from app.repositories.study_sessions_repository import StudySessionsRepository
from app.services.alternative_explanation_service import AlternativeExplanationService
from app.services.socratico_service import SocraticoService


class MeTestaAnswerService:
    """Process student answers and prepare review materials.

    M2-S3 Workflow:
    1. Receive student answer (A/B/C/D/E)
    2. Classify error if wrong (Conceitual, Interpretação, Atenção)
    3. Prepare review_card for Anki
    4. Set anki_status = queued_local_build
    """

    def __init__(
        self,
        repository: StudySessionsRepository,
        socratico_service: SocraticoService | None = None,
        submitted_questions_repository: SubmittedQuestionsRepository | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.repository = repository
        self.socratico_service = socratico_service
        self.submitted_questions_repository = submitted_questions_repository
        self.llm_client = llm_client
        self.alternative_explanation_service = AlternativeExplanationService()

    async def process_answer(
        self,
        telegram_id: int,
        student_answer: str,
        session: SessionRecord,
    ) -> ServiceResult:
        """Process student's answer to a question.

        Args:
            telegram_id: Student's telegram ID
            student_answer: Student's selected alternative (A-E)
            session: Active session with question snapshot

        Returns:
            ServiceResult with feedback and updated session state
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Eu me perdi da questão anterior aqui. Me manda de novo que eu retomo com você.",
                should_reply=True,
            )

        snapshot = session.question_snapshot
        correct_answer = snapshot.correct_alternative or ""
        student_answer_upper = student_answer.strip().upper()

        # Validate answer format
        if student_answer_upper not in "ABCDE":
            return ServiceResult(
                state=SessionState.WAITING_ANSWER,
                reply_text="Me responde só com a letra da alternativa: A, B, C, D ou E.",
                should_reply=True,
            )

        # If no gabarito, resolve using Claude and generate explanation
        if not correct_answer and self.llm_client is not None:
            resolved = await self._resolve_correct_answer(snapshot)
            if resolved:
                correct_answer = resolved
                snapshot.correct_alternative = correct_answer
                # Generate explanation for student-submitted questions
                if not snapshot.explanation:
                    snapshot.explanation = await self._generate_explanation(snapshot, correct_answer)

        # Ensure correct_answer is always a string
        correct_answer = correct_answer or ""

        # Check if answer is correct
        is_correct = student_answer_upper == correct_answer if correct_answer else False

        if is_correct:
            return await self._handle_correct_answer(session)
        else:
            return await self._handle_incorrect_answer(
                session, student_answer_upper, correct_answer
            )

    async def _resolve_correct_answer(self, snapshot) -> str | None:
        """Use Claude to resolve correct answer when not in database."""
        if self.llm_client is None:
            return None

        try:
            alternatives_text = "\n".join(
                f"{alt.label}) {alt.text}" for alt in snapshot.alternatives
            )
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
                answer = response.content[0].text.strip().upper()
                if answer in "ABCDE":
                    return answer
        except Exception as e:
            import logging
            logging.warning(f"Failed to resolve correct answer with Claude: {e}")

        return None

    async def _generate_explanation(self, snapshot, correct_answer: str) -> str:
        """Generate pedagogical explanation for a question using Claude."""
        if self.llm_client is None or not correct_answer:
            return ""

        try:
            alternatives_text = "\n".join(
                f"{alt.label}) {alt.text}" for alt in snapshot.alternatives
            )
            prompt = (
                f"Você é um tutor expert em ENEM. Gere uma explicação pedagógica clara e concisa para esta questão.\n\n"
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
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
        except Exception as e:
            import logging
            logging.warning(f"Failed to generate explanation with Claude: {e}")

        return ""

    async def _handle_correct_answer(self, session: SessionRecord) -> ServiceResult:
        """Handle case where student answered correctly."""
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        snapshot = session.question_snapshot
        if snapshot is not None:
            self.alternative_explanation_service.ensure_alternative_explanations(session)
        session.state = SessionState.WAITING_FOLLOWUP_CHAT
        session.metadata.state = SessionState.WAITING_FOLLOWUP_CHAT
        session.metadata.anki = AnkiMetadata(status="not_needed")
        session.metadata.review_card = ReviewCard()
        session.metadata.retry_attempts = 0
        self.repository.save(session)
        self._sync_submitted_question_snapshot(session)
        self._mark_submitted_question_result(
            session=session,
            answered_correct=True,
            sent_to_anki=False,
            apkg_generated=False,
        )
        alternatives_review = self._build_alternatives_review(snapshot, snapshot.correct_alternative or "") if snapshot is not None else ""

        return ServiceResult(
            state=SessionState.WAITING_FOLLOWUP_CHAT,
            reply_text="\n".join(
                [
                    "✅ Boa! Você acertou essa.",
                    "",
                    "Gostei de ver você chegando na resposta certa.",
                    "",
                    "Aqui vai a questão comentada para firmar o raciocínio:",
                    "",
                    (
                        alternatives_review
                        if alternatives_review
                        else "Ainda não tenho uma explicação detalhada por alternativa para essa questão."
                    ),
                    "",
                    "Se preferir, já me manda a próxima questão.",
                ]
            ),
            should_reply=True,
            metadata={
                "is_correct": True,
                "session_id": session.session_id,
            },
        )

    async def _handle_incorrect_answer(
        self,
        session: SessionRecord,
        student_answer: str,
        correct_answer: str,
    ) -> ServiceResult:
        """Handle case where student answered incorrectly.

        Workflow:
        1. Classify error type
        2. Prepare review card for Anki
        3. Route to Socratic mode if available, else direct explanation
        """
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        snapshot = session.question_snapshot
        if snapshot is None:
            raise ValueError("Question snapshot is required")

        # Classify error
        error_classification = ErrorClassification.classify(
            student_answer=student_answer,
            correct_answer=correct_answer,
            question_content=snapshot.content,
            explanation=snapshot.explanation,
        )

        # Prepare review card for Anki
        review_card = self._build_review_card(
            snapshot=snapshot,
            student_answer=student_answer,
            correct_answer=correct_answer,
            error_classification=error_classification,
        )

        # Save error classification and review card
        session.metadata.review_card = review_card
        session.metadata.anki = AnkiMetadata(
            status="queued_local_build",
            builder_mode="review_card",
        )
        session.metadata.retry_attempts = 1

        # Route to Socratic mode if available, else go direct
        if self.socratico_service is not None:
            # M3-S1: Socratic mode
            result = await self.socratico_service.route_incorrect_answer(session)
            self.repository.save(session)
            return ServiceResult(
                state=result.state,
                reply_text=result.reply_text,
                should_reply=True,
                metadata={
                    "is_correct": False,
                    "session_id": session.session_id,
                    "error_type": error_classification.error_type.value if error_classification.error_type else None,
                    "review_card_id": review_card.review_card_id,
                    "learning_path": "socratic" if result.state == SessionState.WAITING_SOCRATIC_Q1 else "direct",
                },
            )
        else:
            # Legacy: Direct explanation (M2-S3 behavior)
            session.state = SessionState.EXPLAINING_DIRECT
            session.metadata.state = SessionState.EXPLAINING_DIRECT
            self.repository.save(session)
            self._mark_submitted_question_result(
                session=session,
                answered_correct=False,
                sent_to_anki=True,
                apkg_generated=False,
                error_type=error_classification.error_type.value if error_classification.error_type else None,
            )

            # Build feedback message
            feedback = self._build_feedback_message(
                correct_answer=correct_answer,
                explanation=snapshot.explanation,
                error_type=error_classification.error_type,
                error_reasoning=error_classification.reasoning,
            )

            return ServiceResult(
                state=SessionState.EXPLAINING_DIRECT,
                reply_text=feedback,
                should_reply=True,
                metadata={
                    "is_correct": False,
                    "session_id": session.session_id,
                    "error_type": error_classification.error_type.value if error_classification.error_type else None,
                    "review_card_id": review_card.review_card_id,
                },
            )

    def _mark_submitted_question_result(
        self,
        *,
        session: SessionRecord,
        answered_correct: bool,
        sent_to_anki: bool,
        apkg_generated: bool,
        apkg_path: str | None = None,
        error_type: str | None = None,
    ) -> None:
        if not isinstance(session.metadata, SessionMetadata):
            return
        snapshot_id = session.metadata.question_ref.snapshot_id
        if self.submitted_questions_repository is None or not snapshot_id:
            return
        self.submitted_questions_repository.mark_result(
            snapshot_id,
            answered_correct=answered_correct,
            retry_attempts=session.metadata.retry_attempts,
            sent_to_anki=sent_to_anki,
            apkg_generated=apkg_generated,
            apkg_path=apkg_path,
            error_type=error_type,
        )

    def _sync_submitted_question_snapshot(self, session: SessionRecord) -> None:
        if not isinstance(session.metadata, SessionMetadata):
            return
        snapshot_id = session.metadata.question_ref.snapshot_id
        if self.submitted_questions_repository is None or not snapshot_id or session.question_snapshot is None:
            return
        self.submitted_questions_repository.sync_snapshot(snapshot_id, session.question_snapshot)

    def _build_review_card(
        self,
        snapshot,
        student_answer: str,
        correct_answer: str,
        error_classification: ErrorClassification,
    ) -> ReviewCard:
        """Build Anki review card for spaced repetition."""
        alternatives_text = self._format_alternatives(snapshot.alternatives)
        alternatives_review = self._build_alternatives_review(snapshot, correct_answer)
        explanation = snapshot.explanation or "Ainda não tenho uma explicação confiável para essa questão específica."
        classification = error_classification.error_type.value if error_classification.error_type else "desconhecida"

        front = f"""📝 {snapshot.subject} - {snapshot.topic}

{snapshot.content}

{alternatives_text}"""

        back = f"""✅ Resposta correta: {correct_answer}

📚 Explicação:
{explanation}

🔎 Alternativas:
{alternatives_review}

🎯 Foco de estudo:
{error_classification.suggested_focus or 'Revisar este tópico'}

🧭 Sua resposta:
Você marcou {student_answer}. Classificação do erro: {classification}."""

        return ReviewCard(
            review_card_id=str(uuid4()),
            front=front,
            back=back,
        )

    def _format_alternatives(self, alternatives) -> str:
        if not alternatives:
            return ""
        return "\n".join(f"{alternative.label}) {alternative.text}" for alternative in alternatives)

    def _build_alternatives_review(self, snapshot, correct_answer: str) -> str:
        """Build complete review of ALL alternatives.

        Shows all 5 alternatives with explanations so student understands:
        - Why the correct answer is right
        - Why incorrect answers are wrong
        - Full pedagogical context
        """
        if not snapshot.alternatives:
            return f"{correct_answer}) Correta. {snapshot.explanation}".strip()

        lines: list[str] = []
        for alternative in snapshot.alternatives:
            if alternative.label == correct_answer:
                explanation = alternative.explanation or snapshot.explanation or "Esta é a alternativa correta."
                lines.append(f"**{alternative.label}) {alternative.text}** — ✅ correta\n{explanation}")
            else:
                explanation = alternative.explanation or (
                    "Justificativa específica ainda não cadastrada; revisar comparando com a explicação da alternativa correta."
                )
                lines.append(f"**{alternative.label}) {alternative.text}** — ❌ incorreta\n{explanation}")
        return "\n".join(lines)

    def _build_feedback_message(
        self,
        correct_answer: str,
        explanation: str,
        error_type: ErrorType | None,
        error_reasoning: str,
    ) -> str:
        """Build pedagogical feedback message for student."""
        error_label = (
            f"_{error_type.value.upper()}_" if error_type else "_DESCONHECIDO_"
        )

        return "\n".join(
            [
                "❌ Ainda não foi dessa vez, mas vamos usar isso a seu favor.",
                "",
                f"**Tipo de erro: {error_label}**",
                f"_{error_reasoning}_",
                "",
                f"**Resposta correta: {correct_answer}**",
                "",
                f"**Explicação:**",
                explanation or "Ainda não tenho uma explicação confiável para essa questão específica, mas agora já registrei o gabarito correto.",
                "",
                "Se quiser, eu posso te ajudar a destrinchar isso com calma agora mesmo. 💪",
            ]
        )

