"""Service for Socratic Questioning Mode.

M3-S1: After incorrect answer, guide student with up to 2 questions before revealing answer.
- If mood is "cansada" (tired), skip to direct explanation
- Otherwise, ask guiding questions to help student self-discover the answer
"""

from __future__ import annotations

import logging

from app.domain.models import ServiceResult, SessionRecord
from app.domain.states import SessionState

logger = logging.getLogger(__name__)


class SocraticoService:
    """Guide student through Socratic questioning after incorrect answer."""

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
                reply_text="Erro: nenhuma questão ativa",
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

        If response suggests correct understanding, move to explanation.
        Otherwise, ask Q2.
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Erro: nenhuma questão ativa",
            )

        snapshot = session.question_snapshot
        session.state = SessionState.WAITING_SOCRATIC_Q2
        session.metadata.state = SessionState.WAITING_SOCRATIC_Q2

        # Generate Q2 based on Q1 response
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

        After Q2, provide explanation regardless of response.
        """
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Erro: nenhuma questão ativa",
            )

        snapshot = session.question_snapshot
        session.state = SessionState.DONE
        session.metadata.state = SessionState.DONE

        # Build explanation message
        explanation_text = self._build_explanation(
            snapshot.correct_alternative or "",
            snapshot.explanation,
        )

        logger.info(f"socratico_service: explanation delivered for session={session.session_id}")

        return ServiceResult(
            state=SessionState.DONE,
            reply_text=explanation_text,
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "learning_path": "socratic_q1_q2",
            },
        )

    async def skip_to_direct_explanation(self, session: SessionRecord) -> ServiceResult:
        """Skip Socratic mode and provide direct explanation (for tired students)."""
        if session.question_snapshot is None:
            return ServiceResult(
                state=SessionState.FAILED_RETRYABLE,
                reply_text="Erro: nenhuma questão ativa",
            )

        snapshot = session.question_snapshot
        session.state = SessionState.DONE
        session.metadata.state = SessionState.DONE

        # Build explanation message
        explanation_text = self._build_explanation(
            snapshot.correct_alternative or "",
            snapshot.explanation,
        )

        logger.info(f"socratico_service: direct explanation (tired mode) for session={session.session_id}")

        return ServiceResult(
            state=SessionState.DONE,
            reply_text=explanation_text,
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "learning_path": "direct_explanation",
            },
        )

    def _build_q1(self, question_content: str, subject: str) -> str:
        """Build first Socratic question (Q1).

        Ask student to reconsider the question.
        """
        return "\n".join(
            [
                "Vamos refletir sobre a questão juntas. 🤔",
                "",
                "Qual você acha que é a palavra-chave nesse enunciado?",
                "O que ela quer dizer de verdade?",
                "",
                "Tira um segundo para reler e me diz o que você pensa.",
            ]
        )

    def _build_q2(self, question_content: str, correct_alt: str, q1_response: str) -> str:
        """Build second Socratic question (Q2).

        Dig deeper based on Q1 response.
        """
        return "\n".join(
            [
                "Entendi sua reflexão. 👀",
                "",
                "Agora me pensa junto: qual é a relação entre o que você disse e",
                "cada uma das alternativas A, B, C, D, E?",
                "",
                "Qual delas se encaixa melhor com a ideia que você teve?",
            ]
        )

    def _build_explanation(self, correct_answer: str, explanation: str) -> str:
        """Build final explanation message."""
        return "\n".join(
            [
                f"A resposta correta é a alternativa **{correct_answer}**. ✅",
                "",
                "**Por quê?**",
                explanation,
                "",
                "Vamos revisar esse tópico mais tarde para fixar melhor? 💪",
            ]
        )

