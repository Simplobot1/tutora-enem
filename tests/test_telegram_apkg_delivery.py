import tempfile
import unittest
from pathlib import Path

from app.adapters.telegram_api import NullTelegramGateway
from app.clients.llm import LLMClient
from app.domain.session_metadata import AnkiMetadata, SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
from app.services.intake_service import IntakeService
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_service import MeTestaService
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService


class TelegramApkgDeliveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_followup_chat_sends_apkg_as_document_when_available(self) -> None:
        gateway = NullTelegramGateway()
        session_service = SessionService(InMemoryStudySessionsRepository())
        service = MeTestaService(
            session_service=session_service,
            telegram_gateway=gateway,
            llm_client=LLMClient(),
            entry_service=MeTestaEntryService(
                session_service=session_service,
                question_snapshot_service=QuestionSnapshotService(),
            ),
        )
        intake = IntakeService()

        session = session_service.get_or_create_active_session(
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
        )
        session.state = SessionState.WAITING_FOLLOWUP_CHAT

        with tempfile.TemporaryDirectory() as temp_dir:
            apkg_path = Path(temp_dir) / "deck.apkg"
            apkg_path.write_bytes(b"anki")
            session.metadata = SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_FOLLOWUP_CHAT,
                source_mode="student_submitted",
                anki=AnkiMetadata(status="prepared", builder_mode="review_card", apkg_path=str(apkg_path)),
            )
            session_service.save(session)

            event = intake.normalize_update(
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 100,
                        "text": "me manda o apkg",
                        "chat": {"id": 321},
                        "from": {"id": 123},
                    },
                }
            )

            result = await service.handle_event(event)

        self.assertEqual(result.state, SessionState.WAITING_FOLLOWUP_CHAT)
        self.assertEqual(len(gateway.documents), 1)
        self.assertEqual(gateway.documents[0].file_path, str(apkg_path))
        self.assertIn("anki", gateway.documents[0].caption.lower())
