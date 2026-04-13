import unittest

from app.adapters.telegram_api import NullTelegramGateway
from app.clients.llm import LLMClient
from app.domain.states import SessionFlow, SessionState
from app.repositories.submitted_questions_repository import InMemorySubmittedQuestionsRepository
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
from app.services.intake_service import IntakeService
from app.services.me_testa_answer_service import MeTestaAnswerService
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_service import MeTestaService
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService
from app.services.socratico_service import SocraticoService


QUESTION_92 = (
    "QUESTÃO 92\n"
    "A carne de javaporco é consumida, principalmente na\n"
    "forma de churrasco, nas regiões Sul e Sudeste. O javaporco é um\n"
    "híbrido de javali com porco que pode chegar a 200 quilogramas\n"
    "(kg). O consumo da carne dessa variedade selvagem de suíno\n"
    "assim como o contato com a saliva e o sangue do animal, não\n"
    "são recomendáveis por causa da possibilidade de transmitir\n"
    "agentes causadores de doenças. Entre as possíveis doenças\n"
    "que podem ser transmitidas por esse animal, a triquinelose\n"
    "representa uma grande preocupação. Essa doença é causada\n"
    "por larvas do verme Trichinela sp. e transmitida pelo consumo\n"
    "de carne crua ou malcozida de animais, incluindo javaporcos.\n"
    "Disponível em: www.revistapesquisa.fapesp.br.\n"
    "Acesso em: 18 set. 2022.\n"
    "Qual das verminoses a seguir apresenta as mesmas medidas\n"
    "preventivas contra a triquinelose?\n"
    "A Teníase.\n"
    "B Filariose.\n"
    "C Oxiurose.\n"
    "D Ancilostomose.\n"
    "E Esquistossomose."
)


class FakeApkgBuilder:
    def __init__(self) -> None:
        self.calls: list[str | None] = []
        self.snapshots = []

    def build_apkg_from_session(self, session) -> str:
        self.calls.append(session.session_id)
        self.snapshots.append(session.question_snapshot)
        return f"/tmp/{session.session_id}.apkg"


class StudentSubmittedRetryFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.intake = IntakeService()
        self.gateway = NullTelegramGateway()
        self.repository = InMemoryStudySessionsRepository()
        self.submitted_questions_repository = InMemorySubmittedQuestionsRepository()
        self.session_service = SessionService(self.repository)
        self.entry_service = MeTestaEntryService(
            session_service=self.session_service,
            question_snapshot_service=QuestionSnapshotService(),
            submitted_questions_repository=self.submitted_questions_repository,
        )
        self.apkg_builder = FakeApkgBuilder()
        self.socratico_service = SocraticoService(
            apkg_builder=self.apkg_builder,
            submitted_questions_repository=self.submitted_questions_repository,
        )
        self.answer_service = MeTestaAnswerService(
            repository=self.repository,
            socratico_service=self.socratico_service,
            submitted_questions_repository=self.submitted_questions_repository,
        )
        self.service = MeTestaService(
            session_service=self.session_service,
            telegram_gateway=self.gateway,
            llm_client=LLMClient(),
            entry_service=self.entry_service,
            answer_service=self.answer_service,
            socratico_service=self.socratico_service,
        )

    async def test_student_submitted_known_question_accepts_correct_answer_without_gabarito(self) -> None:
        intake_event = self.intake.normalize_update(
            {
                "update_id": 1,
                "message": {
                    "message_id": 100,
                    "text": QUESTION_92,
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )

        intake_result = await self.service.handle_event(intake_event)

        self.assertEqual(intake_result.state, SessionState.WAITING_ANSWER)
        session = self.session_service.repository.get_active_session(123, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.question_snapshot.correct_alternative, "A")
        snapshot_id = session.metadata.question_ref.snapshot_id
        self.assertIsNotNone(snapshot_id)
        assert snapshot_id is not None
        self.assertEqual(self.submitted_questions_repository.rows[snapshot_id]["answered_correct"], None)
        self.assertIn("Agora me conta qual alternativa você marcou", intake_result.reply_text)

        answer_event = self.intake.normalize_update(
            {
                "update_id": 2,
                "message": {
                    "message_id": 101,
                    "text": "A",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }
        )
        answer_result = await self.service.handle_event(answer_event)

        self.assertEqual(answer_result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertTrue(answer_result.metadata["is_correct"])
        self.assertIn("questão comentada", answer_result.reply_text.lower())
        self.assertIn("A) Teníase.** — ✅ correta", answer_result.reply_text)
        self.assertIn("B) Filariose.** — ❌ incorreta", answer_result.reply_text)
        self.assertTrue(self.submitted_questions_repository.rows[snapshot_id]["answered_correct"])
        self.assertFalse(self.submitted_questions_repository.rows[snapshot_id]["sent_to_anki"])
        alternatives = self.submitted_questions_repository.rows[snapshot_id]["alternatives"]
        self.assertTrue(all(alternative["explanation"] for alternative in alternatives))
        self.assertIn("Triquinelose e teníase", alternatives[0]["explanation"])
        self.assertIn("não corresponde ao gabarito confirmado", alternatives[1]["explanation"])

    async def test_student_submitted_wrong_then_wrong_again_generates_apkg(self) -> None:
        intake_event = self.intake.normalize_update(
            {
                "update_id": 3,
                "message": {
                    "message_id": 102,
                    "text": QUESTION_92,
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )
        await self.service.handle_event(intake_event)

        first_wrong_event = self.intake.normalize_update(
            {
                "update_id": 4,
                "message": {
                    "message_id": 103,
                    "text": "E",
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )
        first_wrong_result = await self.service.handle_event(first_wrong_event)

        self.assertEqual(first_wrong_result.state, SessionState.WAITING_SOCRATIC_Q1)
        self.assertIn("responde só com a, b, c, d ou e", first_wrong_result.reply_text.lower())
        session = self.session_service.repository.get_active_session(124, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        assert session is not None
        snapshot_id = session.metadata.question_ref.snapshot_id
        assert snapshot_id is not None

        second_wrong_event = self.intake.normalize_update(
            {
                "update_id": 5,
                "message": {
                    "message_id": 104,
                    "text": "C",
                    "chat": {"id": 322},
                    "from": {"id": 124},
                },
            }
        )
        second_wrong_result = await self.service.handle_event(second_wrong_event)

        self.assertEqual(second_wrong_result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertFalse(second_wrong_result.metadata["is_correct"])
        self.assertTrue(second_wrong_result.metadata["apkg_path"].endswith(".apkg"))
        self.assertIn("segunda tentativa", second_wrong_result.reply_text.lower())
        self.assertIn("segue abaixo o arquivo", second_wrong_result.reply_text.lower())
        self.assertEqual(len(self.apkg_builder.calls), 1)
        snapshot = self.apkg_builder.snapshots[0]
        self.assertTrue(all(alternative.explanation for alternative in snapshot.alternatives))
        self.assertIn("Triquinelose e teníase", snapshot.alternatives[0].explanation)
        self.assertIn("não corresponde ao gabarito confirmado", snapshot.alternatives[1].explanation)
        self.assertFalse(self.submitted_questions_repository.rows[snapshot_id]["answered_correct"])
        self.assertTrue(self.submitted_questions_repository.rows[snapshot_id]["sent_to_anki"])
        self.assertTrue(self.submitted_questions_repository.rows[snapshot_id]["apkg_generated"])

        session = self.session_service.repository.get_active_session(124, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.state, SessionState.WAITING_FOLLOWUP_CHAT)

    async def test_student_submitted_wrong_then_correct_on_retry_finishes_without_apkg(self) -> None:
        intake_event = self.intake.normalize_update(
            {
                "update_id": 6,
                "message": {
                    "message_id": 105,
                    "text": QUESTION_92,
                    "chat": {"id": 323},
                    "from": {"id": 125},
                },
            }
        )
        await self.service.handle_event(intake_event)

        first_wrong_event = self.intake.normalize_update(
            {
                "update_id": 7,
                "message": {
                    "message_id": 106,
                    "text": "B",
                    "chat": {"id": 323},
                    "from": {"id": 125},
                },
            }
        )
        await self.service.handle_event(first_wrong_event)

        retry_correct_event = self.intake.normalize_update(
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
        retry_result = await self.service.handle_event(retry_correct_event)

        self.assertEqual(retry_result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertTrue(retry_result.metadata["is_correct"])
        self.assertEqual(self.apkg_builder.calls, [])
        self.assertIn("virada no seu raciocínio", retry_result.reply_text.lower())
        session = self.session_service.repository.get_active_session(125, SessionFlow.ME_TESTA)  # type: ignore[attr-defined]
        assert session is not None
        snapshot_id = session.metadata.question_ref.snapshot_id
        assert snapshot_id is not None
        self.assertTrue(self.submitted_questions_repository.rows[snapshot_id]["answered_correct"])
        self.assertFalse(self.submitted_questions_repository.rows[snapshot_id]["sent_to_anki"])

    async def test_student_can_chat_with_tutora_after_second_error(self) -> None:
        intake_event = self.intake.normalize_update(
            {
                "update_id": 9,
                "message": {
                    "message_id": 108,
                    "text": QUESTION_92,
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(intake_event)

        first_wrong_event = self.intake.normalize_update(
            {
                "update_id": 10,
                "message": {
                    "message_id": 109,
                    "text": "E",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(first_wrong_event)

        second_wrong_event = self.intake.normalize_update(
            {
                "update_id": 11,
                "message": {
                    "message_id": 110,
                    "text": "C",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        await self.service.handle_event(second_wrong_event)

        followup_event = self.intake.normalize_update(
            {
                "update_id": 12,
                "message": {
                    "message_id": 111,
                    "text": "qual foi o racional?",
                    "chat": {"id": 324},
                    "from": {"id": 126},
                },
            }
        )
        followup_result = await self.service.handle_event(followup_event)

        self.assertEqual(followup_result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertIn("boa pergunta", followup_result.reply_text.lower())
        self.assertIn("teníase", followup_result.reply_text.lower())
