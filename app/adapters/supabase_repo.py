from __future__ import annotations

from typing import Protocol

from app.domain.models import SessionRecord
from app.domain.states import SessionFlow, SessionState


class SessionRepository(Protocol):
    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        ...

    def save_session(self, session: SessionRecord) -> None:
        ...


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[tuple[int, SessionFlow], SessionRecord] = {}

    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        session = self._sessions.get((telegram_id, flow))
        if session is None:
            return None
        if session.state == SessionState.DONE:
            return None
        return session

    def save_session(self, session: SessionRecord) -> None:
        self._sessions[(session.telegram_id, session.flow)] = session

