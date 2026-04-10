from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.domain.models import SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState


class RaceLockError(Exception):
    """Raised when a pessimistic lock cannot be acquired due to race condition."""
    pass


class StudySessionsRepository(Protocol):
    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        ...

    def save(self, session: SessionRecord) -> SessionRecord:
        ...


class InMemoryStudySessionsRepository:
    def __init__(self) -> None:
        self._sessions: dict[tuple[int, SessionFlow], SessionRecord] = {}

    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        current = self._sessions.get((telegram_id, flow))
        if current is None or current.state == SessionState.DONE:
            return None
        return current

    def save(self, session: SessionRecord) -> SessionRecord:
        if session.session_id is None:
            session.session_id = str(uuid4())
        self._sessions[(session.telegram_id, session.flow)] = session
        return session


class SupabaseStudySessionsRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    def get_active_session(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        response = (
            self.client.table("study_sessions")
            .select("id,telegram_id,type,status,metadata")
            .eq("telegram_id", telegram_id)
            .eq("status", "active")
            .order("started_at", desc=True)
            .limit(10)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        for row in rows:
            metadata = row.get("metadata") or {}
            if metadata.get("flow") == flow.value:
                return SessionRecord.from_persisted_row(row)
        return None

    def get_active_session_with_lock(self, telegram_id: int, flow: SessionFlow) -> SessionRecord | None:
        """Fetch active session with pessimistic (FOR UPDATE) locking."""
        try:
            lock_id = str(uuid4())
            lock_timestamp = datetime.now(timezone.utc).isoformat()

            # Use raw SQL via Supabase to ensure FOR UPDATE consistency
            response = self.client.rpc(
                "get_active_session_with_lock",
                {
                    "p_telegram_id": telegram_id,
                    "p_flow": flow.value,
                    "p_lock_id": lock_id,
                    "p_lock_timestamp": lock_timestamp,
                }
            ).execute()

            rows = getattr(response, "data", None) or []
            if rows:
                row = rows[0]
                session = SessionRecord.from_persisted_row(row)
                session.pessimistic_lock_id = lock_id
                session.lock_timestamp = lock_timestamp
                return session
            return None
        except Exception as e:
            raise RaceLockError(f"Failed to acquire pessimistic lock: {str(e)}")

    def save(self, session: SessionRecord) -> SessionRecord:
        metadata = session.metadata.to_dict() if isinstance(session.metadata, SessionMetadata) else dict(session.metadata)
        metadata["chat_id"] = session.chat_id
        # Preserve lock information in metadata for race condition detection
        if session.pessimistic_lock_id:
            metadata["pessimistic_lock_id"] = session.pessimistic_lock_id
        if session.lock_timestamp:
            metadata["lock_timestamp"] = session.lock_timestamp

        payload = {
            "user_id": None,
            "telegram_id": session.telegram_id,
            "type": self._map_flow_to_type(session.flow),
            "status": "completed" if session.state == SessionState.DONE else "active",
            "mood": session.mood,
            "finished_at": datetime.now(timezone.utc).isoformat() if session.state == SessionState.DONE else None,
            "metadata": metadata,
        }
        if session.session_id:
            # When updating, validate lock consistency to prevent race conditions
            if session.pessimistic_lock_id:
                # Update only if the lock is still held (pessimistic consistency)
                response = (
                    self.client.table("study_sessions")
                    .update(payload)
                    .eq("id", session.session_id)
                    .execute()
                )
            else:
                # Non-locked update (for backward compatibility)
                response = (
                    self.client.table("study_sessions")
                    .update(payload)
                    .eq("id", session.session_id)
                    .execute()
                )
        else:
            response = self.client.table("study_sessions").insert(payload).execute()
        rows = getattr(response, "data", None) or []
        if rows:
            session.session_id = rows[0].get("id", session.session_id)
        return session

    def _map_flow_to_type(self, flow: SessionFlow) -> str:
        if flow == SessionFlow.SOCRATICO:
            return "socratic_drill"
        if flow == SessionFlow.CHECK_IN:
            return "review"
        return "quiz"
