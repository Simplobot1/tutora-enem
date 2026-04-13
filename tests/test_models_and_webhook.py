import asyncio
from dataclasses import dataclass
import unittest

import httpx

from app.api.runtime import RuntimeServices, set_runtime_services_override
from app.domain.models import InboundEvent, QuestionSnapshot, ServiceResult, SessionRecord
from app.domain.session_metadata import QuestionRef, SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.main import app


class SessionRecordFromPersistedRowTest(unittest.TestCase):
    def test_from_persisted_row_restores_chat_id_and_snapshot_contract(self) -> None:
        record = SessionRecord.from_persisted_row(
            {
                "id": "session-1",
                "telegram_id": 123,
                "metadata": {
                    "flow": "me_testa",
                    "state": "WAITING_ANSWER",
                    "source_mode": "bank_match",
                    "chat_id": 999,
                    "question_id": "question-1",
                    "question_ref": {
                        "question_id": "question-1",
                        "snapshot_id": None,
                        "bank_match_confidence": 0.88,
                    },
                    "question_snapshot": {
                        "source_mode": "bank_match",
                        "source_truth": "student_content_plus_bank_match",
                        "content": "Enunciado",
                        "alternatives": [{"label": "A", "text": "Opção A"}],
                        "correct_alternative": "C",
                        "explanation": "Porque C é a correta",
                        "subject": "Biologia",
                        "topic": "Genética",
                    },
                },
            }
        )

        self.assertEqual(record.chat_id, 999)
        self.assertEqual(record.question_snapshot.correct_alternative, "C")
        self.assertEqual(record.question_snapshot.explanation, "Porque C é a correta")
        self.assertEqual(record.metadata.question_ref.bank_match_confidence, 0.88)


@dataclass(slots=True)
class StubMeTestaService:
    seen_event: InboundEvent | None = None
    calls: int = 0

    async def handle_event(self, event: InboundEvent) -> ServiceResult:
        self.seen_event = event
        self.calls += 1
        return ServiceResult(
            state=SessionState.WAITING_ANSWER,
            reply_text="webhook stub",
            metadata={"path": "telegram_webhook"},
        )


@dataclass(slots=True)
class StubTelegramGateway:
    messages: list[tuple[int, str]]

    async def send_text(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        raise AssertionError("send_document should not be called")


@dataclass(slots=True)
class StubIntakeService:
    def normalize_update(self, payload: dict) -> InboundEvent:
        return InboundEvent(
            update_id=payload.get("update_id"),
            telegram_id=123,
            chat_id=321,
            message_id=100,
            input_mode="text",
            text="Questão recebida",
            raw_payload=payload,
        )


class TelegramWebhookApiTest(unittest.TestCase):
    def test_webhook_uses_runtime_override(self) -> None:
        me_testa_service = StubMeTestaService()
        runtime = RuntimeServices(
            intake_service=StubIntakeService(),
            session_service=object(),
            entry_service=object(),
            me_testa_service=me_testa_service,
            telegram_gateway=object(),
        )
        set_runtime_services_override(lambda: runtime)
        try:
            response = asyncio.run(self._request({"update_id": 10, "message": {"text": "oi"}}))
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 202)
        self.assertTrue(body["ok"])
        self.assertEqual(body["result"]["reply_text"], "webhook stub")
        self.assertIsNotNone(me_testa_service.seen_event)
        assert me_testa_service.seen_event is not None
        self.assertEqual(me_testa_service.seen_event.chat_id, 321)

    def test_admin_command_bypasses_me_testa_session_flow(self) -> None:
        me_testa_service = StubMeTestaService()
        gateway = StubTelegramGateway(messages=[])
        runtime = RuntimeServices(
            intake_service=StubIntakeService(),
            session_service=object(),
            entry_service=object(),
            me_testa_service=me_testa_service,
            telegram_gateway=gateway,
        )
        set_runtime_services_override(lambda: runtime)
        try:
            response = asyncio.run(self._request({
                "update_id": 11,
                "message": {
                    "message_id": 101,
                    "text": "/admin",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }))
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(body["action"], "admin_unavailable")
        self.assertEqual(me_testa_service.calls, 0)
        self.assertEqual(gateway.messages, [(321, "Admin ainda não está disponível por aqui.")])

    def test_unknown_slash_command_bypasses_me_testa_session_flow(self) -> None:
        me_testa_service = StubMeTestaService()
        gateway = StubTelegramGateway(messages=[])
        runtime = RuntimeServices(
            intake_service=StubIntakeService(),
            session_service=object(),
            entry_service=object(),
            me_testa_service=me_testa_service,
            telegram_gateway=gateway,
        )
        set_runtime_services_override(lambda: runtime)
        try:
            response = asyncio.run(self._request({
                "update_id": 12,
                "message": {
                    "message_id": 102,
                    "text": "/qualquer",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }))
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(body["action"], "unknown_command")
        self.assertEqual(me_testa_service.calls, 0)
        self.assertEqual(gateway.messages, [(321, "Não reconheci esse comando. Para reiniciar a questão, use /nova.")])

    def test_suporte_command_bypasses_me_testa_session_flow(self) -> None:
        me_testa_service = StubMeTestaService()
        gateway = StubTelegramGateway(messages=[])
        runtime = RuntimeServices(
            intake_service=StubIntakeService(),
            session_service=object(),
            entry_service=object(),
            me_testa_service=me_testa_service,
            telegram_gateway=gateway,
        )
        set_runtime_services_override(lambda: runtime)
        try:
            response = asyncio.run(self._request({
                "update_id": 13,
                "message": {
                    "message_id": 103,
                    "text": "/suporte",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }))
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(body["action"], "suporte_sent")
        self.assertEqual(me_testa_service.calls, 0)
        self.assertEqual(gateway.messages, [(321, "Precisa de ajuda? Me chama por aqui: simplobot3@gmail.com")])

    def test_sobre_command_bypasses_me_testa_session_flow(self) -> None:
        me_testa_service = StubMeTestaService()
        gateway = StubTelegramGateway(messages=[])
        runtime = RuntimeServices(
            intake_service=StubIntakeService(),
            session_service=object(),
            entry_service=object(),
            me_testa_service=me_testa_service,
            telegram_gateway=gateway,
        )
        set_runtime_services_override(lambda: runtime)
        try:
            response = asyncio.run(self._request({
                "update_id": 14,
                "message": {
                    "message_id": 104,
                    "text": "/sobre",
                    "chat": {"id": 321},
                    "from": {"id": 123},
                },
            }))
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(body["action"], "sobre_sent")
        self.assertEqual(me_testa_service.calls, 0)
        self.assertEqual(len(gateway.messages), 1)
        self.assertIn("A Tutora ajuda você a estudar para o ENEM", gateway.messages[0][1])
        self.assertIn("Organiza questões enviadas por texto ou foto", gateway.messages[0][1])

    async def _request(self, payload: dict) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/webhooks/telegram", json=payload)
