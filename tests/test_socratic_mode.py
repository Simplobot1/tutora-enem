"""M3-S1: Socratic Mode Tests

Test Socratic questioning flow for incorrect answers:
- Mood check-in (tired → direct, else → socratic)
- Two-question guidance before explanation
- Integration with error classification
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
from app.services.socratico_service import SocraticoService


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


class SocraticModeNotTiredTest(unittest.IsolatedAsyncioTestCase):
    """Test Socratic flow for student who is NOT tired (default path)."""

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
        self.socratico_service = SocraticoService()
        self.answer_service = MeTestaAnswerService(
            repository=self.repository,
            socratico_service=self.socratico_service,
        )
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
            socratico_service=self.socratico_service,
        )

    async def test_socratic_flow_q1_then_q2_then_done(self) -> None:
        """Test: incorrect answer → Q1 → Q2 → explanation → DONE."""
        # Step 1: Intake question
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
        await self.service.handle_event(intake_event)

        # Step 2: Submit incorrect answer → Q1
        wrong_answer_event = self.intake.normalize_update(
            {
                "update_id": 2,
                "message": {
                    "message_id": 101,
                    "text": "A",  # Wrong answer
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        q1_result = await self.service.handle_event(wrong_answer_event)

        # Should receive Q1
        self.assertEqual(q1_result.state, SessionState.WAITING_SOCRATIC_Q1)
        self.assertIn("refletir", q1_result.reply_text.lower())
        self.assertIn("palavra-chave", q1_result.reply_text.lower())

        # Verify error was classified and review_card was prepared
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIsNotNone(session.metadata.review_card)

        # Step 3: Respond to Q1 → Q2
        q1_response_event = self.intake.normalize_update(
            {
                "update_id": 3,
                "message": {
                    "message_id": 102,
                    "text": "A palavra-chave é prevenção",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        q2_result = await self.service.handle_event(q1_response_event)

        # Should receive Q2
        self.assertEqual(q2_result.state, SessionState.WAITING_SOCRATIC_Q2)
        self.assertIn("alternativa", q2_result.reply_text.lower())

        # Step 4: Respond to Q2 → Explanation
        q2_response_event = self.intake.normalize_update(
            {
                "update_id": 4,
                "message": {
                    "message_id": 103,
                    "text": "Acho que é E",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        explanation_result = await self.service.handle_event(q2_response_event)

        # Should provide explanation and go to DONE
        self.assertEqual(explanation_result.state, SessionState.DONE)
        self.assertIn("resposta correta", explanation_result.reply_text.lower())
        self.assertIn("E", explanation_result.reply_text)


class SocraticModeTiredTest(unittest.IsolatedAsyncioTestCase):
    """Test direct explanation path for tired student."""

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
        self.socratico_service = SocraticoService()
        self.answer_service = MeTestaAnswerService(
            repository=self.repository,
            socratico_service=self.socratico_service,
        )
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
            socratico_service=self.socratico_service,
        )

    async def test_direct_explanation_when_tired(self) -> None:
        """Test: mood='cansada' → incorrect answer → direct explanation → DONE."""
        # Step 1: Intake question
        intake_event = self.intake.normalize_update(
            {
                "update_id": 5,
                "message": {
                    "message_id": 104,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )
        await self.service.handle_event(intake_event)

        # Step 2: Set mood to "cansada" on session
        session = self.session_service.repository.get_active_session(124, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        session.mood = "cansada"
        self.session_service.save(session)

        # Step 3: Submit incorrect answer → should get DIRECT explanation (skip Q1/Q2)
        wrong_answer_event = self.intake.normalize_update(
            {
                "update_id": 6,
                "message": {
                    "message_id": 105,
                    "text": "B",
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )
        result = await self.service.handle_event(wrong_answer_event)

        # Should skip Socratic and go directly to DONE
        self.assertEqual(result.state, SessionState.DONE)
        self.assertIn("resposta correta", result.reply_text.lower())
        self.assertIn("E", result.reply_text)
        # Should not see Q1 markers
        self.assertNotIn("refletir", result.reply_text.lower())


class SocraticIntegrationTest(unittest.IsolatedAsyncioTestCase):
    """Test Socratic integration with me-testa answer service."""

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
        self.socratico_service = SocraticoService()
        self.answer_service = MeTestaAnswerService(
            repository=self.repository,
            socratico_service=self.socratico_service,
        )
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
            socratico_service=self.socratico_service,
        )

    async def test_error_classification_preserved_in_socratic(self) -> None:
        """Test: error is classified and review_card saved during Socratic flow."""
        # Intake and answer
        intake_event = self.intake.normalize_update(
            {
                "update_id": 7,
                "message": {
                    "message_id": 106,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 323},
                    "from": {"id": 125},
                },
            }
        )
        await self.service.handle_event(intake_event)

        wrong_answer_event = self.intake.normalize_update(
            {
                "update_id": 8,
                "message": {
                    "message_id": 107,
                    "text": "A",
                    "chat": {"id": 323},
                    "from": {"id": 125},
                },
            }
        )
        q1_result = await self.service.handle_event(wrong_answer_event)

        # Verify Q1 state
        self.assertEqual(q1_result.state, SessionState.WAITING_SOCRATIC_Q1)

        # Verify error classification was performed
        session = self.session_service.repository.get_active_session(125, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIsNotNone(session.metadata.review_card)
        self.assertIsNotNone(session.metadata.review_card.review_card_id)
        self.assertIsNotNone(session.metadata.anki)
        self.assertEqual(session.metadata.anki.status, "queued_local_build")

    async def test_follow_up_question_after_socratic_done(self) -> None:
        """Test: after Socratic flow completes (DONE), can submit new question."""
        # Complete a socratic flow
        intake_event = self.intake.normalize_update(
            {
                "update_id": 9,
                "message": {
                    "message_id": 108,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(intake_event)

        # Wrong answer → Q1
        wrong_answer_event = self.intake.normalize_update(
            {
                "update_id": 10,
                "message": {
                    "message_id": 109,
                    "text": "C",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(wrong_answer_event)

        # Q1 response → Q2
        q1_response_event = self.intake.normalize_update(
            {
                "update_id": 11,
                "message": {
                    "message_id": 110,
                    "text": "resposta1",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(q1_response_event)

        # Q2 response → DONE
        q2_response_event = self.intake.normalize_update(
            {
                "update_id": 12,
                "message": {
                    "message_id": 111,
                    "text": "resposta2",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        done_result = await self.service.handle_event(q2_response_event)
        self.assertEqual(done_result.state, SessionState.DONE)

        # New question (DONE → new intake)
        new_question_event = self.intake.normalize_update(
            {
                "update_id": 13,
                "message": {
                    "message_id": 112,
                    "text": COMPLETE_QUESTION,
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        new_intake_result = await self.service.handle_event(new_question_event)
        self.assertEqual(new_intake_result.state, SessionState.WAITING_ANSWER)


class SocraticServiceDirectTest(unittest.IsolatedAsyncioTestCase):
    """Test SocraticoService methods directly (without full integration)."""

    def setUp(self) -> None:
        self.service = SocraticoService()
        self.repository = InMemoryStudySessionsRepository()

    async def test_q1_generation(self) -> None:
        """Test first Socratic question generation."""
        from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
        from app.domain.session_metadata import SessionMetadata

        session = SessionRecord(
            session_id="test-1",
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=QuestionSnapshot(
                source_mode="bank_match",
                source_truth="student_content_plus_bank_match",
                content="O que é mitocôndria?",
                alternatives=[
                    QuestionAlternative(label="A", text="Organela de reprodução"),
                    QuestionAlternative(label="B", text="Organela de respiração"),
                    QuestionAlternative(label="C", text="Organela de digestão"),
                    QuestionAlternative(label="D", text="Organela de transporte"),
                    QuestionAlternative(label="E", text="Organela de armazenamento"),
                ],
                correct_alternative="B",
                explanation="Mitocôndria é a organela responsável pela respiração celular.",
                subject="Biologia",
                topic="Citologia",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
            ),
        )

        result = await self.service.generate_q1(session)

        self.assertEqual(result.state, SessionState.WAITING_SOCRATIC_Q1)
        self.assertIn("refletir", result.reply_text.lower())

    async def test_direct_explanation_path(self) -> None:
        """Test skipping to direct explanation."""
        from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
        from app.domain.session_metadata import SessionMetadata

        session = SessionRecord(
            session_id="test-2",
            telegram_id=124,
            chat_id=322,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            mood="cansada",
            question_snapshot=QuestionSnapshot(
                source_mode="bank_match",
                source_truth="student_content_plus_bank_match",
                content="O que é mitocôndria?",
                alternatives=[
                    QuestionAlternative(label="A", text="Organela A"),
                    QuestionAlternative(label="B", text="Organela B"),
                    QuestionAlternative(label="C", text="Organela C"),
                    QuestionAlternative(label="D", text="Organela D"),
                    QuestionAlternative(label="E", text="Organela E"),
                ],
                correct_alternative="B",
                explanation="Explicação",
                subject="Biologia",
                topic="Citologia",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
            ),
        )

        result = await self.service.skip_to_direct_explanation(session)

        self.assertEqual(result.state, SessionState.DONE)
        self.assertIn("B", result.reply_text)
        self.assertIn("Explicação", result.reply_text)
