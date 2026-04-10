import asyncio
from dataclasses import dataclass
import unittest

import httpx

from app.api.runtime import RuntimeServices, set_runtime_services_override
from app.domain.models import ServiceResult
from app.domain.states import SessionState
from app.main import app


@dataclass(slots=True)
class StubMeTestaService:
    async def handle_event(self, event) -> ServiceResult:
        return ServiceResult(state=SessionState.WAITING_ANSWER, reply_text="ok", metadata={"echo": event.telegram_id})


def build_test_runtime() -> RuntimeServices:
    return RuntimeServices(
        intake_service=object(),
        session_service=object(),
        entry_service=object(),
        me_testa_service=StubMeTestaService(),
        telegram_gateway=object(),
    )


class HealthApiTest(unittest.TestCase):
    def test_healthcheck(self) -> None:
        set_runtime_services_override(build_test_runtime)
        try:
            response = asyncio.run(self._request())
        finally:
            set_runtime_services_override(None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def _request(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health")
