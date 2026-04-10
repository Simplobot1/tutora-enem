"""Service for processing me-testa answers and classifications.

M2-S3: Handle answer submission, error classification, and review card preparation.
"""

from __future__ import annotations

from uuid import uuid4

from app.domain.error_classification import ErrorClassification, ErrorType
from app.domain.models import ServiceResult, SessionRecord
from app.domain.session_metadata import AnkiMetadata, ReviewCard, SessionMetadata
from app.domain.states import SessionState
from app.repositories.study_sessions_repository import StudySessionsRepository
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
    ) -> None:
        self.repository = repository
        self.socratico_service = socratico_service

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
                reply_text="Erro: nenhuma questão ativa",
                should_reply=True,
            )

        snapshot = session.question_snapshot
        correct_answer = snapshot.correct_alternative or ""
        student_answer_upper = student_answer.strip().upper()

        # Validate answer format
        if student_answer_upper not in "ABCDE":
            return ServiceResult(
                state=SessionState.WAITING_ANSWER,
                reply_text="Por favor, responda com A, B, C, D ou E.",
                should_reply=True,
            )

        # Check if answer is correct
        is_correct = student_answer_upper == correct_answer

        if is_correct:
            return await self._handle_correct_answer(session)
        else:
            return await self._handle_incorrect_answer(
                session, student_answer_upper, correct_answer
            )

    async def _handle_correct_answer(self, session: SessionRecord) -> ServiceResult:
        """Handle case where student answered correctly."""
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        session.state = SessionState.DONE
        session.metadata.state = SessionState.DONE
        session.metadata.anki = AnkiMetadata(status="not_needed")
        self.repository.save(session)

        return ServiceResult(
            state=SessionState.DONE,
            reply_text="✅ Parabéns! Você acertou!",
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
            builder_mode="append_to_deck",
        )

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

    def _build_review_card(
        self,
        snapshot,
        student_answer: str,
        correct_answer: str,
        error_classification: ErrorClassification,
    ) -> ReviewCard:
        """Build Anki review card for spaced repetition."""
        front = f"""📝 {snapshot.subject} - {snapshot.topic}

{snapshot.content}

Você respondeu: {student_answer}
Resposta correta: {correct_answer}

Classificação: {error_classification.error_type.value if error_classification.error_type else 'desconhecida'}"""

        back = f"""✅ Resposta correta: {correct_answer}

📚 Explicação:
{snapshot.explanation}

🎯 Foco de estudo:
{error_classification.suggested_focus or 'Revisar este tópico'}"""

        return ReviewCard(
            review_card_id=str(uuid4()),
            front=front,
            back=back,
        )

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
                "❌ Infelizmente, essa não é a resposta correta.",
                "",
                f"**Tipo de erro: {error_label}**",
                f"_{error_reasoning}_",
                "",
                f"**Resposta correta: {correct_answer}**",
                "",
                f"**Explicação:**",
                explanation,
                "",
                "Vamos revisar esse tópico mais tarde para fixar melhor? 💪",
            ]
        )
