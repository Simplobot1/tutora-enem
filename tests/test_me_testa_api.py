import asyncio
from dataclasses import dataclass
import unittest

import httpx

from app.api.runtime import RuntimeServices, set_runtime_services_override
from app.domain.models import InboundEvent, ServiceResult, SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
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
            telegram_gateway=object(),
        )


class StubSessionRepository:
    def __init__(self, session: SessionRecord | None) -> None:
        self.session = session

    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        if self.session is None:
            return None
        if self.session.telegram_id != telegram_id or flow != SessionFlow.ME_TESTA:
            return None
        return self.session


@dataclass(slots=True)
class StubSessionService:
    repository: StubSessionRepository


@dataclass(slots=True)
class StubAnswerService:
    seen_answer: str | None = None
    seen_session_id: str | None = None

    async def process_answer(
        self,
        telegram_id: int,
        student_answer: str,
        session: SessionRecord,
    ) -> ServiceResult:
        self.seen_answer = student_answer
        self.seen_session_id = session.session_id
        return ServiceResult(
            state=SessionState.WAITING_FOLLOWUP_CHAT,
            reply_text="corrigido via API",
            metadata={
                "session_id": session.session_id,
                "is_correct": True,
                "source_mode": session.source_mode,
            },
        )


@dataclass(slots=True)
class StubMeTestaService:
    answer_service: StubAnswerService | None


def build_answer_runtime(
    session: SessionRecord | None,
    answer_service: StubAnswerService | None,
) -> RuntimeServices:
    return RuntimeServices(
        intake_service=object(),
        session_service=StubSessionService(StubSessionRepository(session)),
        entry_service=object(),
        me_testa_service=StubMeTestaService(answer_service=answer_service),
        telegram_gateway=object(),
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

    def test_me_testa_answer_route_processes_bank_match_session(self) -> None:
        session = SessionRecord(
            session_id="session-bank-1",
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            source_mode="bank_match",
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
            ),
        )
        answer_service = StubAnswerService()
        set_runtime_services_override(lambda: build_answer_runtime(session, answer_service))
        try:
            response = asyncio.run(
                self._request_answer(
                    {
                        "telegram_id": 123,
                        "chat_id": 321,
                        "message_id": 102,
                        "answer": "E",
                    }
                )
            )
        finally:
            set_runtime_services_override(None)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["result"]["state"], "WAITING_FOLLOWUP_CHAT")
        self.assertEqual(body["result"]["metadata"]["source_mode"], "bank_match")
        self.assertEqual(answer_service.seen_answer, "E")
        self.assertEqual(answer_service.seen_session_id, "session-bank-1")

    def test_me_testa_answer_route_returns_404_without_active_session(self) -> None:
        set_runtime_services_override(lambda: build_answer_runtime(None, StubAnswerService()))
        try:
            response = asyncio.run(
                self._request_answer(
                    {
                        "telegram_id": 999,
                        "chat_id": 321,
                        "answer": "A",
                    }
                )
            )
        finally:
            set_runtime_services_override(None)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "No active me-testa session found for this telegram_id.",
        )

    async def _request(self, payload: dict[str, object]) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/me-testa/intake", json=payload)

    async def _request_answer(self, payload: dict[str, object]) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/me-testa/answer", json=payload)
