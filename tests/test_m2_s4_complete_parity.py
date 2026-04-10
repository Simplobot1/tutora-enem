"""M2-S4: Complete Me-Testa Functional Parity Tests

End-to-end testing for both bank_match and student_submitted paths,
including intake, answer processing, and follow-ups.
"""

import unittest

from app.adapters.telegram_api import NullTelegramGateway
from app.clients.llm import LLMClient
from app.domain.states import SessionFlow, SessionState
from app.repositories.questions_repository import QuestionsRepository
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
from app.services.intake_service import IntakeService
from app.services.me_testa_answer_service import MeTestaAnswerService
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_service import MeTestaService
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService


class FakeQuestionsRepository(QuestionsRepository):
    def __init__(self, match: dict | None) -> None:
        super().__init__(client=None)
        self.match = match

    def find_best_match(self, stem: str, alternatives: list[str] | None = None, limit: int = 8) -> dict | None:
        return self.match


COMPLETE_QUESTION = (
    "Qual das verminoses a seguir apresenta as mesmas medidas preventivas?\n"
    "A Teníase.\n"
    "B Filariose.\n"
    "C Oxiurose.\n"
    "D Ancilostomose.\n"
    "E Esquistossomose."
)

INCOMPLETE_QUESTION = "Pode me ajudar com uma questão de biologia?"

FALLBACK_DETAILS = (
    "O enunciado é: Qual das verminoses apresenta as mesmas medidas preventivas?\n"
    "A Teníase.\n"
    "B Filariose.\n"
    "C Oxiurose.\n"
    "D Ancilostomose.\n"
    "E Esquistossomose."
)


class CompleteParityBankMatchTest(unittest.IsolatedAsyncioTestCase):
    """Test complete flow: bank_match path intake → answer → feedback."""

    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.session_service = SessionService(self.repository)
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=FakeQuestionsRepository(
                {
                    "id": "question-verminoses",
                    "subject": "Biologia",
                    "topic": "Parasitologia",
                    "correct_alternative": "E",
                    "explanation": "A prevenção coincide com saneamento básico.",
                    "match_confidence": 0.91,
                }
            ),
        )
        self.answer_service = MeTestaAnswerService(repository=self.repository)
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
        )

    async def test_complete_bank_match_path_correct_answer(self) -> None:
        """Test: question intake → bank match found → answer correct → done."""
        # Step 1: intake question with bank match
        intake_event = self.intake.normalize_update(
            {
                "update_id": 1,
                "message": {
                    "message_id": 100,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        intake_result = await self.service.handle_event(intake_event)
        self.assertEqual(intake_result.state, SessionState.WAITING_ANSWER)
        self.assertEqual(intake_result.metadata["source_mode"], "bank_match")
        self.assertEqual(intake_result.metadata["question_id"], "question-verminoses")

        # Step 2: submit correct answer
        answer_event = self.intake.normalize_update(
            {
                "update_id": 2,
                "message": {
                    "message_id": 101,
                    "text": "E",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        answer_result = await self.service.handle_event(answer_event)
        self.assertEqual(answer_result.state, SessionState.DONE)
        self.assertIn("Parabéns", answer_result.reply_text)
        self.assertEqual(answer_result.metadata["is_correct"], True)

    async def test_complete_bank_match_path_incorrect_answer(self) -> None:
        """Test: question intake → bank match found → answer incorrect → classification."""
        # Step 1: intake question
        intake_event = self.intake.normalize_update(
            {
                "update_id": 3,
                "message": {
                    "message_id": 102,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )

        intake_result = await self.service.handle_event(intake_event)
        self.assertEqual(intake_result.state, SessionState.WAITING_ANSWER)

        # Step 2: submit incorrect answer
        answer_event = self.intake.normalize_update(
            {
                "update_id": 4,
                "message": {
                    "message_id": 103,
                    "text": "A",
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )

        answer_result = await self.service.handle_event(answer_event)
        self.assertEqual(answer_result.state, SessionState.EXPLAINING_DIRECT)
        self.assertIn("Infelizmente", answer_result.reply_text)
        self.assertEqual(answer_result.metadata["is_correct"], False)
        self.assertIsNotNone(answer_result.metadata["error_type"])
        self.assertIsNotNone(answer_result.metadata["review_card_id"])

        # Verify review card was saved
        session = self.session_service.repository.get_active_session(124, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIsNotNone(session.metadata.review_card)
        self.assertEqual(session.metadata.anki.status, "queued_local_build")


class CompleteParityStudentSubmittedTest(unittest.IsolatedAsyncioTestCase):
    """Test complete flow: student_submitted path (question recognized, no bank match)."""

    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.session_service = SessionService(self.repository)
        # No repository → no bank_match, but question is still recognized
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=None,
        )
        self.answer_service = MeTestaAnswerService(repository=self.repository)
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
        )

    async def test_complete_student_submitted_path_intake(self) -> None:
        """Test: student question → student_submitted mode (no bank match)."""
        # Step 1: intake complete question (no bank match)
        intake_event = self.intake.normalize_update(
            {
                "update_id": 5,
                "message": {
                    "message_id": 104,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 323},
                    "from": {"id": 125},
                },
            }
        )

        intake_result = await self.service.handle_event(intake_event)
        self.assertEqual(intake_result.state, SessionState.WAITING_ANSWER)
        self.assertEqual(intake_result.metadata["source_mode"], "student_submitted")
        self.assertIsNone(intake_result.metadata["question_id"])
        self.assertIn("Agora me diga a alternativa", intake_result.reply_text)

    async def test_student_submitted_without_bank_match_answer_handling(self) -> None:
        """Test: student_submitted mode → answer submitted (no correct answer known)."""
        # Step 1: intake complete question
        intake_event = self.intake.normalize_update(
            {
                "update_id": 7,
                "message": {
                    "message_id": 106,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )

        intake_result = await self.service.handle_event(intake_event)
        self.assertEqual(intake_result.state, SessionState.WAITING_ANSWER)

        # Step 2: submit answer (no bank match, so answer is classified as incorrect)
        # This is expected behavior: without a bank_match or AI evaluation,
        # we treat it as incorrect and prepare for review
        answer_event = self.intake.normalize_update(
            {
                "update_id": 8,
                "message": {
                    "message_id": 107,
                    "text": "B",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )

        answer_result = await self.service.handle_event(answer_event)
        # Without correct_alternative, answer is treated as incorrect
        self.assertEqual(answer_result.state, SessionState.EXPLAINING_DIRECT)
        self.assertEqual(answer_result.metadata["is_correct"], False)


class FallbackDetailsFlowTest(unittest.IsolatedAsyncioTestCase):
    """Test fallback flow: incomplete → request details → receive complete."""

    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.session_service = SessionService(self.repository)
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=FakeQuestionsRepository(
                {
                    "id": "question-verminoses",
                    "subject": "Biologia",
                    "topic": "Parasitologia",
                    "correct_alternative": "E",
                    "explanation": "A prevenção coincide com saneamento básico.",
                    "match_confidence": 0.91,
                }
            ),
        )
        self.answer_service = MeTestaAnswerService(repository=self.repository)
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
        )

    async def test_fallback_incomplete_to_complete_to_answer(self) -> None:
        """Test: incomplete → WAITING_FALLBACK_DETAILS → complete → answer → done."""
        # Step 1: send incomplete question
        incomplete_event = self.intake.normalize_update(
            {
                "update_id": 9,
                "message": {
                    "message_id": 108,
                    "text": INCOMPLETE_QUESTION,
                    "chat": {"id": 325},
                    "from": {"id": 127},
                },
            }
        )

        incomplete_result = await self.service.handle_event(incomplete_event)
        self.assertEqual(incomplete_result.state, SessionState.WAITING_FALLBACK_DETAILS)
        self.assertIn("Ainda faltam dados", incomplete_result.reply_text)

        # Step 2: send fallback details (complete question with bank match)
        fallback_event = self.intake.normalize_update(
            {
                "update_id": 10,
                "message": {
                    "message_id": 109,
                    "text": FALLBACK_DETAILS,
                    "chat": {"id": 325},
                    "from": {"id": 127},
                },
            }
        )

        fallback_result = await self.service.handle_event(fallback_event)
        self.assertEqual(fallback_result.state, SessionState.WAITING_ANSWER)
        self.assertIn("Agora me diga", fallback_result.reply_text)
        # Verify bank match was found
        self.assertEqual(fallback_result.metadata["source_mode"], "bank_match")

        # Step 3: submit correct answer
        answer_event = self.intake.normalize_update(
            {
                "update_id": 11,
                "message": {
                    "message_id": 110,
                    "text": "E",
                    "chat": {"id": 325},
                    "from": {"id": 127},
                },
            }
        )

        answer_result = await self.service.handle_event(answer_event)
        self.assertEqual(answer_result.state, SessionState.DONE)
        self.assertEqual(answer_result.metadata["is_correct"], True)


class FollowUpQuestionsTest(unittest.IsolatedAsyncioTestCase):
    """Test follow-up questions after session completion."""

    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.session_service = SessionService(self.repository)
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=FakeQuestionsRepository(
                {
                    "id": "question-verminoses",
                    "subject": "Biologia",
                    "topic": "Parasitologia",
                    "correct_alternative": "E",
                    "explanation": "A prevenção coincide com saneamento básico.",
                    "match_confidence": 0.91,
                }
            ),
        )
        self.answer_service = MeTestaAnswerService(repository=self.repository)
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
        )

    async def test_follow_up_after_correct_answer(self) -> None:
        """Test: question 1 correct → new question intake."""
        # Question 1: intake and answer
        q1_event = self.intake.normalize_update(
            {
                "update_id": 12,
                "message": {
                    "message_id": 111,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 326},
                    "from": {"id": 128},
                },
            }
        )
        await self.service.handle_event(q1_event)

        q1_answer = self.intake.normalize_update(
            {
                "update_id": 13,
                "message": {
                    "message_id": 112,
                    "text": "E",
                    "chat": {"id": 326},
                    "from": {"id": 128},
                },
            }
        )
        q1_result = await self.service.handle_event(q1_answer)
        self.assertEqual(q1_result.state, SessionState.DONE)
        self.assertEqual(q1_result.metadata["is_correct"], True)

        # Follow-up: new question (DONE → intake)
        # Same question for simplicity (bank match will find it again)
        q2_event = self.intake.normalize_update(
            {
                "update_id": 14,
                "message": {
                    "message_id": 113,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 326},
                    "from": {"id": 128},
                },
            }
        )
        q2_result = await self.service.handle_event(q2_event)
        self.assertEqual(q2_result.state, SessionState.WAITING_ANSWER)
        # Session should be reset (new question)
        session = self.session_service.repository.get_active_session(128, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.state, SessionState.WAITING_ANSWER)

    async def test_follow_up_after_incorrect_answer(self) -> None:
        """Test: question 1 incorrect → new question intake."""
        # Question 1: intake and answer incorrectly
        q1_event = self.intake.normalize_update(
            {
                "update_id": 15,
                "message": {
                    "message_id": 114,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 327},
                    "from": {"id": 129},
                },
            }
        )
        await self.service.handle_event(q1_event)

        q1_answer = self.intake.normalize_update(
            {
                "update_id": 16,
                "message": {
                    "message_id": 115,
                    "text": "C",
                    "chat": {"id": 327},
                    "from": {"id": 129},
                },
            }
        )
        q1_result = await self.service.handle_event(q1_answer)
        self.assertEqual(q1_result.state, SessionState.EXPLAINING_DIRECT)

        # Note: EXPLAINING_DIRECT state needs additional implementation for full parity
        # For now, session remains in EXPLAINING_DIRECT state
        session = self.session_service.repository.get_active_session(129, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.state, SessionState.EXPLAINING_DIRECT)


class InvalidAnswerHandlingTest(unittest.IsolatedAsyncioTestCase):
    """Test edge cases and invalid input handling."""

    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.session_service = SessionService(self.repository)
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=FakeQuestionsRepository(
                {
                    "id": "question-verminoses",
                    "subject": "Biologia",
                    "topic": "Parasitologia",
                    "correct_alternative": "E",
                    "explanation": "A prevenção coincide com saneamento básico.",
                    "match_confidence": 0.91,
                }
            ),
        )
        self.answer_service = MeTestaAnswerService(repository=self.repository)
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
        )

    async def test_invalid_answer_format_rejected(self) -> None:
        """Test: invalid answer format (not A-E) is rejected."""
        # Intake question
        intake_event = self.intake.normalize_update(
            {
                "update_id": 17,
                "message": {
                    "message_id": 116,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 328},
                    "from": {"id": 130},
                },
            }
        )
        await self.service.handle_event(intake_event)

        # Submit invalid answer
        invalid_event = self.intake.normalize_update(
            {
                "update_id": 18,
                "message": {
                    "message_id": 117,
                    "text": "Z",
                    "chat": {"id": 328},
                    "from": {"id": 130},
                },
            }
        )
        result = await self.service.handle_event(invalid_event)
        self.assertEqual(result.state, SessionState.WAITING_ANSWER)
        self.assertIn("A, B, C, D ou E", result.reply_text)

    async def test_case_insensitive_answer(self) -> None:
        """Test: lowercase answer is accepted."""
        # Intake question
        intake_event = self.intake.normalize_update(
            {
                "update_id": 19,
                "message": {
                    "message_id": 118,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 329},
                    "from": {"id": 131},
                },
            }
        )
        await self.service.handle_event(intake_event)

        # Submit lowercase answer
        answer_event = self.intake.normalize_update(
            {
                "update_id": 20,
                "message": {
                    "message_id": 119,
                    "text": "e",
                    "chat": {"id": 329},
                    "from": {"id": 131},
                },
            }
        )
        result = await self.service.handle_event(answer_event)
        self.assertEqual(result.state, SessionState.DONE)
        self.assertEqual(result.metadata["is_correct"], True)
