from __future__ import annotations

from app.domain.models import SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import StudySessionsRepository, RaceLockError


class SessionService:
    def __init__(self, repository: StudySessionsRepository) -> None:
        self.repository = repository

    def get_or_create_active_session(self, telegram_id: int, chat_id: int, flow: SessionFlow) -> SessionRecord:
        current = self.repository.get_active_session(telegram_id, flow)
        if current is not None:
            return current

        created = SessionRecord(
            session_id=None,
            telegram_id=telegram_id,
            chat_id=chat_id,
            flow=flow,
            state=SessionState.IDLE,
            metadata=SessionMetadata(
                flow=flow,
                state=SessionState.IDLE,
                source_mode="student_content_only",
            ),
        )
        self.repository.save(created)
        return created

    def get_or_create_active_session_with_lock(self, telegram_id: int, chat_id: int, flow: SessionFlow) -> SessionRecord:
        """Get active session with pessimistic locking to prevent race conditions.

        M2-S2: Pessimistic locking ensures only one process can update a session at a time.
        If no active session exists, creates one (new sessions don't need lock).

        Raises RaceLockError if lock cannot be acquired.
        """
        try:
            # Try to acquire lock on existing session
            if hasattr(self.repository, 'get_active_session_with_lock'):
                locked = self.repository.get_active_session_with_lock(telegram_id, flow)
                if locked is not None:
                    return locked
        except RaceLockError:
            raise

        # If no active session, create new one (no lock needed)
        created = SessionRecord(
            session_id=None,
            telegram_id=telegram_id,
            chat_id=chat_id,
            flow=flow,
            state=SessionState.IDLE,
            metadata=SessionMetadata(
                flow=flow,
                state=SessionState.IDLE,
                source_mode="student_content_only",
            ),
        )
        self.repository.save(created)
        return created

    def save(self, session: SessionRecord) -> SessionRecord:
        if isinstance(session.metadata, SessionMetadata):
            session.metadata.flow = session.flow
            session.metadata.state = session.state
            session.metadata.source_mode = session.source_mode
            session.metadata.question_id = session.question_id
            session.metadata.question_snapshot = session.question_snapshot
            session.metadata.question_ref.question_id = session.question_id
        return self.repository.save(session)
