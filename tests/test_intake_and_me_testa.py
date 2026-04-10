import unittest

from app.adapters.telegram_api import NullTelegramGateway
from app.clients.llm import LLMClient
from app.domain.states import SessionFlow, SessionState
from app.repositories.questions_repository import QuestionsRepository
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
from app.services.intake_service import IntakeService
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


class IntakeAndMeTestaTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.session_service = SessionService(InMemoryStudySessionsRepository())
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
        )
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
        )

    def test_intake_normalizes_text_message(self) -> None:
        event = self.intake.normalize_update(
            {
                "update_id": 10,
                "message": {
                    "message_id": 99,
                    "text": "oi",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        self.assertEqual(event.telegram_id, 123)
        self.assertEqual(event.chat_id, 321)
        self.assertEqual(event.input_mode, "text")

    async def test_me_testa_moves_to_waiting_answer_for_complete_question(self) -> None:
        event = self.intake.normalize_update(
            {
                "update_id": 11,
                "message": {
                    "message_id": 100,
                    "text": (
                        "Qual das verminoses a seguir apresenta as mesmas medidas preventivas?\n"
                        "A Teníase.\n"
                        "B Filariose.\n"
                        "C Oxiurose.\n"
                        "D Ancilostomose.\n"
                        "E Esquistossomose."
                    ),
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(event)

        self.assertEqual(result.state, SessionState.WAITING_ANSWER)
        self.assertIn("Agora me diga a alternativa", result.reply_text)
        self.assertEqual(result.metadata["source_mode"], "student_submitted")
        self.assertIsNone(result.metadata["question_id"])

    async def test_me_testa_requests_more_context_for_incomplete_question(self) -> None:
        event = self.intake.normalize_update(
            {
                "update_id": 12,
                "message": {
                    "message_id": 101,
                    "text": "Pode me ajudar com uma questão de biologia?",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(event)

        self.assertEqual(result.state, SessionState.WAITING_FALLBACK_DETAILS)
        self.assertIn("Ainda faltam dados", result.reply_text)

    async def test_me_testa_marks_bank_match_without_losing_snapshot(self) -> None:
        entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            questions_repository=FakeQuestionsRepository(
                {
                    "id": "question-123",
                    "subject": "Biologia",
                    "topic": "Parasitologia",
                    "correct_alternative": "E",
                    "explanation": "A prevenção coincide com saneamento básico.",
                    "match_confidence": 0.91,
                }
            ),
        )
        service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=entry_service,
        )
        event = self.intake.normalize_update(
            {
                "update_id": 13,
                "message": {
                    "message_id": 102,
                    "text": (
                        "Qual das verminoses a seguir apresenta as mesmas medidas preventivas?\n"
                        "A Teníase.\n"
                        "B Filariose.\n"
                        "C Oxiurose.\n"
                        "D Ancilostomose.\n"
                        "E Esquistossomose."
                    ),
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await service.handle_event(event)
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]

        self.assertEqual(result.state, SessionState.WAITING_ANSWER)
        self.assertEqual(result.metadata["source_mode"], "bank_match")
        self.assertEqual(result.metadata["question_id"], "question-123")
        self.assertEqual(result.metadata["bank_match_confidence"], 0.91)
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.question_snapshot.source_mode, "bank_match")
        self.assertEqual(session.question_snapshot.correct_alternative, "E")
        self.assertEqual(session.question_snapshot.explanation, "A prevenção coincide com saneamento básico.")
        self.assertEqual(session.metadata.question_ref.question_id, "question-123")
