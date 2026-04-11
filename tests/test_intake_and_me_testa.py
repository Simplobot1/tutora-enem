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

    def test_intake_normalizes_callback_query(self) -> None:
        event = self.intake.normalize_update(
            {
                "update_id": 20,
                "callback_query": {
                    "id": "cb-1",
                    "data": "mood:cansada",
                    "from": {"id": 123},
                    "message": {"message_id": 99, "chat": {"id": 321}},
                },
            }
        )

        self.assertEqual(event.telegram_id, 123)
        self.assertEqual(event.chat_id, 321)
        self.assertEqual(event.input_mode, "callback")
        self.assertEqual(event.callback_data, "mood:cansada")

    async def test_greeting_opens_check_in_with_buttons(self) -> None:
        event = self.intake.normalize_update(
            {
                "update_id": 21,
                "message": {
                    "message_id": 110,
                    "text": "oi",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(event)

        self.assertEqual(result.state, SessionState.IDLE)
        self.assertIn("ajustar o ritmo", result.reply_text.lower())
        self.assertEqual(len(self.gateway.messages), 1)
        self.assertIsNotNone(self.gateway.messages[0].reply_markup)
        markup = self.gateway.messages[0].reply_markup
        assert markup is not None
        self.assertEqual(markup["inline_keyboard"][0][0]["text"], "😴 Cansada")
        self.assertEqual(markup["inline_keyboard"][0][0]["callback_data"], "mood:cansada")
        self.assertEqual(markup["inline_keyboard"][1][0]["text"], "💭 Ansiosa")
        self.assertEqual(markup["inline_keyboard"][1][0]["callback_data"], "mood:ansiosa")

    async def test_mood_callback_updates_session_instead_of_falling_into_intake(self) -> None:
        greet_event = self.intake.normalize_update(
            {
                "update_id": 22,
                "message": {
                    "message_id": 111,
                    "text": "oi",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        await self.service.handle_event(greet_event)

        callback_event = self.intake.normalize_update(
            {
                "update_id": 23,
                "callback_query": {
                    "id": "cb-2",
                    "data": "mood:cansada",
                    "from": {"id": 123},
                    "message": {"message_id": 112, "chat": {"id": 321}},
                },
            }
        )

        result = await self.service.handle_event(callback_event)

        self.assertEqual(result.state, SessionState.IDLE)
        self.assertIn("mais cansada", result.reply_text.lower())
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.mood, "cansada")

    async def test_greeting_resets_stale_fallback_session_and_reopens_mood_check_in(self) -> None:
        incomplete_event = self.intake.normalize_update(
            {
                "update_id": 24,
                "message": {
                    "message_id": 113,
                    "text": "Pode me ajudar com uma questão de biologia?",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        incomplete_result = await self.service.handle_event(incomplete_event)
        self.assertEqual(incomplete_result.state, SessionState.WAITING_FALLBACK_DETAILS)

        greet_event = self.intake.normalize_update(
            {
                "update_id": 25,
                "message": {
                    "message_id": 114,
                    "text": "oi",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(greet_event)

        self.assertEqual(result.state, SessionState.IDLE)
        self.assertIn("ajustar o ritmo", result.reply_text.lower())
        self.assertEqual(len(self.gateway.messages), 2)
        self.assertIsNotNone(self.gateway.messages[-1].reply_markup)
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.state, SessionState.IDLE)
        self.assertIsNone(session.question_snapshot)
        self.assertIsNone(session.question_id)

    async def test_mood_callback_resets_stale_answer_state_before_new_question(self) -> None:
        question_event = self.intake.normalize_update(
            {
                "update_id": 26,
                "message": {
                    "message_id": 115,
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
        question_result = await self.service.handle_event(question_event)
        self.assertEqual(question_result.state, SessionState.WAITING_ANSWER)

        greet_event = self.intake.normalize_update(
            {
                "update_id": 27,
                "message": {
                    "message_id": 116,
                    "text": "oi",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        await self.service.handle_event(greet_event)

        callback_event = self.intake.normalize_update(
            {
                "update_id": 28,
                "callback_query": {
                    "id": "cb-3",
                    "data": "mood:normal",
                    "from": {"id": 123},
                    "message": {"message_id": 117, "chat": {"id": 321}},
                },
            }
        )
        callback_result = await self.service.handle_event(callback_event)
        self.assertEqual(callback_result.state, SessionState.IDLE)

        next_question_event = self.intake.normalize_update(
            {
                "update_id": 29,
                "message": {
                    "message_id": 118,
                    "text": (
                        "Em uma prova, qual alternativa está correta?\n"
                        "A Uma.\n"
                        "B Duas.\n"
                        "C Três.\n"
                        "D Quatro.\n"
                        "E Cinco."
                    ),
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        next_question_result = await self.service.handle_event(next_question_event)

        self.assertEqual(next_question_result.state, SessionState.WAITING_ANSWER)
        self.assertIn("Agora me conta qual alternativa você marcou", next_question_result.reply_text)

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
        self.assertIn("Agora me conta qual alternativa você marcou", result.reply_text)
        self.assertEqual(result.metadata["source_mode"], "student_submitted")
        self.assertIsNone(result.metadata["question_id"])
        self.assertEqual(len(self.gateway.messages), 1)
        self.assertIn("Agora me conta qual alternativa você marcou", self.gateway.messages[0].text)

    async def test_complete_question_replaces_stale_waiting_answer_session(self) -> None:
        previous_question_event = self.intake.normalize_update(
            {
                "update_id": 31,
                "message": {
                    "message_id": 119,
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
        previous_result = await self.service.handle_event(previous_question_event)
        self.assertEqual(previous_result.state, SessionState.WAITING_ANSWER)

        math_question_event = self.intake.normalize_update(
            {
                "update_id": 32,
                "message": {
                    "message_id": 120,
                    "text": (
                        "Uma função f(x) = 2x² - 8x + 6. Quais são os valores de x para os quais f(x) = 0?\n\n"
                        "x = 1 e x = 3\n"
                        "A\n\n"
                        "x = 2 e x = 4\n"
                        "B\n\n"
                        "x = -1 e x = -3\n"
                        "C\n\n"
                        "x = 0 e x = 4\n"
                        "D\n\n"
                        "x = 2 e x = 6\n"
                        "E"
                    ),
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(math_question_event)
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]

        self.assertEqual(result.state, SessionState.WAITING_ANSWER)
        self.assertIn("Uma função f(x)", result.reply_text)
        self.assertIn("A) x = 1 e x = 3", result.reply_text)
        self.assertIsNotNone(session)
        assert session is not None
        assert session.question_snapshot is not None
        self.assertIn("Uma função f(x)", session.question_snapshot.content)
        self.assertEqual(session.question_snapshot.alternatives[0].label, "A")
        self.assertEqual(session.question_snapshot.alternatives[0].text, "x = 1 e x = 3")

    async def test_manual_restart_command_resets_stale_question(self) -> None:
        previous_question_event = self.intake.normalize_update(
            {
                "update_id": 33,
                "message": {
                    "message_id": 121,
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
        await self.service.handle_event(previous_question_event)

        restart_event = self.intake.normalize_update(
            {
                "update_id": 34,
                "message": {
                    "message_id": 122,
                    "text": "/nova",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        result = await self.service.handle_event(restart_event)
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]

        self.assertEqual(result.state, SessionState.IDLE)
        self.assertIn("Zerei a questão anterior", result.reply_text)
        self.assertEqual(result.metadata["entrypoint"], "manual_restart")
        self.assertIsNotNone(session)
        assert session is not None
        self.assertIsNone(session.question_snapshot)
        self.assertIsNone(session.question_id)

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
        self.assertIn("Ainda não consegui montar a questão inteira", result.reply_text)
        self.assertEqual(len(self.gateway.messages), 1)
        self.assertIn("Ainda não consegui montar a questão inteira", self.gateway.messages[0].text)

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
                    "alternatives": [
                        {"label": "A", "text": "Teníase.", "explanation": "Teníase tem prevenção ligada à carne, não ao saneamento hídrico."},
                        {"label": "B", "text": "Filariose.", "explanation": "Filariose depende do controle de vetores."},
                        {"label": "C", "text": "Oxiurose.", "explanation": "Oxiurose está mais ligada à higiene pessoal e transmissão fecal-oral."},
                        {"label": "D", "text": "Ancilostomose.", "explanation": "Ancilostomose envolve contato com solo contaminado."},
                        {"label": "E", "text": "Esquistossomose.", "explanation": "Esquistossomose compartilha medidas de saneamento básico."},
                    ],
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
        self.assertEqual(session.question_snapshot.alternatives[0].explanation, "Teníase tem prevenção ligada à carne, não ao saneamento hídrico.")
        self.assertEqual(session.question_snapshot.alternatives[4].explanation, "Esquistossomose compartilha medidas de saneamento básico.")
        self.assertEqual(session.metadata.question_ref.question_id, "question-123")
        self.assertEqual(len(self.gateway.messages), 1)
        self.assertIn("Agora me conta qual alternativa você marcou", self.gateway.messages[0].text)
