"""Tests for me-testa answer processing (M2-S3).

Tests that answers are correctly processed:
1. Classification of errors
2. Review card preparation
3. Anki status management
"""

import unittest

from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import SupabaseStudySessionsRepository
from app.services.me_testa_answer_service import MeTestaAnswerService
from tests.test_study_sessions_repository import FakeSupabaseClient


class MeTestaAnswerServiceTest(unittest.TestCase):
    """Test M2-S3: Answer processing and classification."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.client = FakeSupabaseClient()
        self.repository = SupabaseStudySessionsRepository(self.client)
        self.service = MeTestaAnswerService(self.repository)

    def _create_session_with_question(self) -> SessionRecord:
        """Helper to create session with question snapshot."""
        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Qual é a capital do Brasil?",
            alternatives=[
                QuestionAlternative(label="A", text="São Paulo"),
                QuestionAlternative(label="B", text="Rio de Janeiro", explanation="Rio de Janeiro foi capital no passado, mas não é a capital atual."),
                QuestionAlternative(label="C", text="Brasília", explanation="Brasília é a capital federal atual do Brasil."),
                QuestionAlternative(label="D", text="Salvador"),
                QuestionAlternative(label="E", text="Belo Horizonte"),
            ],
            correct_alternative="C",
            explanation="Brasília é a capital federal do Brasil desde 1960.",
            subject="Geografia",
            topic="Capitais",
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=3000,
            chat_id=4000,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
                question_snapshot=snapshot,
            ),
        )

        self.repository.save(session)
        return session

    def test_process_correct_answer(self) -> None:
        """Test M2-S3: Correct answer marks session as DONE."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="C",
                session=session,
            )
        )

        self.assertEqual(result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertIn("questão comentada", result.reply_text.lower())
        self.assertIn("C) Brasília — correta", result.reply_text)
        self.assertIn("A) São Paulo — incorreta", result.reply_text)
        self.assertTrue(result.metadata.get("is_correct"))

    def test_process_incorrect_answer_sets_anki_status(self) -> None:
        """Test M2-S3: Incorrect answer sets anki_status = queued_local_build."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="A",
                session=session,
            )
        )

        self.assertEqual(result.state, SessionState.EXPLAINING_DIRECT)
        self.assertFalse(result.metadata.get("is_correct"))

        # Reload session and verify anki status was set
        reloaded = self.repository.get_active_session(3000, SessionFlow.ME_TESTA)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertIsNotNone(reloaded.metadata.anki)
        self.assertEqual(reloaded.metadata.anki.status, "queued_local_build")

    def test_process_incorrect_answer_prepares_review_card(self) -> None:
        """Test M2-S3: Review card is prepared for Anki."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="B",
                session=session,
            )
        )

        # Reload session and check review card
        reloaded = self.repository.get_active_session(3000, SessionFlow.ME_TESTA)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        review_card = reloaded.metadata.review_card

        self.assertIsNotNone(review_card.review_card_id)
        self.assertGreater(len(review_card.front), 0)
        self.assertGreater(len(review_card.back), 0)
        self.assertIn("Geografia", review_card.front)
        self.assertIn("A) São Paulo", review_card.front)
        self.assertIn("C) Brasília", review_card.front)
        self.assertIn("Brasília", review_card.back)
        self.assertIn("🔎 Alternativas", review_card.back)
        self.assertIn("C) Brasília — correta. Brasília é a capital federal atual do Brasil.", review_card.back)
        self.assertIn("A) São Paulo — incorreta", review_card.back)
        self.assertIn("B) Rio de Janeiro — incorreta. Rio de Janeiro foi capital no passado", review_card.back)
        self.assertIn("Você marcou B", review_card.back)

    def test_process_incorrect_answer_includes_error_type(self) -> None:
        """Test M2-S3: Error type is included in result metadata."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="A",
                session=session,
            )
        )

        self.assertIn("error_type", result.metadata)
        self.assertIsNotNone(result.metadata.get("error_type"))

    def test_invalid_answer_format_rejected(self) -> None:
        """Test M2-S3: Invalid answer format is rejected."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="F",  # Invalid
                session=session,
            )
        )

        # Should stay in WAITING_ANSWER state
        self.assertEqual(result.state, SessionState.WAITING_ANSWER)
        self.assertIn("A, B, C, D ou E", result.reply_text)

    def test_unknown_gabarito_requests_confirmation_instead_of_guessing(self) -> None:
        snapshot = self._create_session_with_question().question_snapshot
        assert snapshot is not None
        snapshot.correct_alternative = None
        session = SessionRecord(
            session_id=None,
            telegram_id=3001,
            chat_id=4001,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
                question_snapshot=snapshot,
            ),
        )
        self.repository.save(session)

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3001,
                student_answer="A",
                session=session,
            )
        )

        self.assertEqual(result.state, SessionState.WAITING_GABARITO)
        self.assertIn("gabarito", result.reply_text.lower())

    def test_process_gabarito_uses_pending_answer(self) -> None:
        snapshot = self._create_session_with_question().question_snapshot
        assert snapshot is not None
        snapshot.correct_alternative = None
        session = SessionRecord(
            session_id=None,
            telegram_id=3002,
            chat_id=4002,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_GABARITO,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_GABARITO,
                source_mode="student_submitted",
                question_snapshot=snapshot,
                pending_student_answer="A",
            ),
        )
        self.repository.save(session)

        result = self._run_async(self.service.process_gabarito(session=session, gabarito_input="gabarito: C"))

        self.assertEqual(result.state, SessionState.EXPLAINING_DIRECT)
        self.assertIn("Resposta correta: C", result.reply_text)

    def test_feedback_message_format(self) -> None:
        """Test M2-S3: Feedback message is well-formatted."""
        session = self._create_session_with_question()

        result = self._run_async(
            self.service.process_answer(
                telegram_id=3000,
                student_answer="D",
                session=session,
            )
        )

        self.assertIn("❌", result.reply_text)
        self.assertIn("resposta correta", result.reply_text.lower())
        self.assertIn("Brasília", result.reply_text)
        self.assertIn("Explicação", result.reply_text)

    def _run_async(self, coro):
        """Helper to run async functions in sync tests."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
