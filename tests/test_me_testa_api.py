import asyncio
from dataclasses import dataclass
import unittest

import httpx

from app.api.runtime import RuntimeServices, set_runtime_services_override
from app.domain.models import InboundEvent, ServiceResult
from app.domain.states import SessionState
from app.main import app


@dataclass(slots=True)
class StubEntryService:
    seen_event: InboundEvent | None = None

    async def handle_question_intake(self, event: InboundEvent) -> ServiceResult:
        self.seen_event = event
        return ServiceResult(
            state=SessionState.WAITING_ANSWER,
            reply_text="stubbed",
            metadata={
                "session_id": "session-test-1",
                "source_mode": "student_submitted",
                "question_id": None,
            },
        )


@dataclass(slots=True)
class StubRuntimeFactory:
    entry_service: StubEntryService

    def build(self) -> RuntimeServices:
        return RuntimeServices(
            intake_service=object(),
            session_service=object(),
            entry_service=self.entry_service,
            me_testa_service=object(),
        )


class MeTestaApiTest(unittest.TestCase):
    def test_me_testa_intake_route_initializes_session(self) -> None:
        stub_entry_service = StubEntryService()
        set_runtime_services_override(StubRuntimeFactory(stub_entry_service).build)
        try:
            response = asyncio.run(
                self._request(
                    {
                        "telegram_id": 123,
                        "chat_id": 321,
                        "message_id": 100,
                        "text": (
                            "Qual das verminoses a seguir apresenta as mesmas medidas preventivas?\n"
                            "A Teníase.\n"
                            "B Filariose.\n"
                            "C Oxiurose.\n"
                            "D Ancilostomose.\n"
                            "E Esquistossomose."
                        ),
                    }
                )
            )
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["result"]["state"], "WAITING_ANSWER")
        self.assertEqual(body["result"]["metadata"]["session_id"], "session-test-1")
        self.assertEqual(body["result"]["metadata"]["source_mode"], "student_submitted")
        self.assertIsNotNone(stub_entry_service.seen_event)
        assert stub_entry_service.seen_event is not None
        self.assertEqual(stub_entry_service.seen_event.telegram_id, 123)
        self.assertEqual(stub_entry_service.seen_event.chat_id, 321)

    def test_me_testa_intake_route_accepts_caption_only_payload(self) -> None:
        stub_entry_service = StubEntryService()
        set_runtime_services_override(StubRuntimeFactory(stub_entry_service).build)
        try:
            response = asyncio.run(
                self._request(
                    {
                        "telegram_id": 123,
                        "chat_id": 321,
                        "message_id": 101,
                        "caption": "Questão enviada na legenda\nA um\nB dois\nC três\nD quatro\nE cinco",
                        "input_mode": "image",
                    }
                )
            )
        finally:
            set_runtime_services_override(None)

        self.assertEqual(response.status_code, 200)
        assert stub_entry_service.seen_event is not None
        self.assertEqual(stub_entry_service.seen_event.caption.splitlines()[0], "Questão enviada na legenda")
        self.assertEqual(stub_entry_service.seen_event.input_mode, "image")

    async def _request(self, payload: dict[str, object]) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/me-testa/intake", json=payload)
