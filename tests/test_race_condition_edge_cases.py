"""Additional race condition edge case tests.

M2-S2: Race condition mitigation edge cases.
Additional tests to reach 31+ test coverage requirement.
"""

import unittest
from uuid import uuid4

from app.domain.models import SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import SupabaseStudySessionsRepository
from tests.test_study_sessions_repository import FakeSupabaseClient


class RaceConditionEdgeCasesTest(unittest.TestCase):
    """Additional edge case tests for race condition mitigation."""

    def test_completed_session_not_locked(self) -> None:
        """Test that completed (DONE) sessions are not returned as active."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        session = SessionRecord(
            session_id=None,
            telegram_id=2000,
            chat_id=3000,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="student_content_only",
            ),
        )

        repository.save(session)

        # Completed session should not be returned as active
        active = repository.get_active_session(2000, SessionFlow.ME_TESTA)
        self.assertIsNone(active)

    def test_lock_id_changes_on_reacquisition(self) -> None:
        """Test that lock_id changes when re-acquiring lock."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        session = SessionRecord(
            session_id=None,
            telegram_id=2001,
            chat_id=3001,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        repository.save(session)

        # First lock
        locked1 = repository.get_active_session_with_lock(2001, SessionFlow.ME_TESTA)
        self.assertIsNotNone(locked1)
        assert locked1 is not None
        lock_id_1 = locked1.pessimistic_lock_id

        # Save and re-acquire (simulating next request)
        repository.save(locked1)
        locked2 = repository.get_active_session_with_lock(2001, SessionFlow.ME_TESTA)
        self.assertIsNotNone(locked2)
        assert locked2 is not None
        lock_id_2 = locked2.pessimistic_lock_id

        # Lock IDs should be different (new lock acquired)
        self.assertNotEqual(lock_id_1, lock_id_2)

    def test_different_telegram_users_isolated(self) -> None:
        """Test that sessions for different telegram users are isolated."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        # User 1 session
        session1 = SessionRecord(
            session_id=None,
            telegram_id=2002,
            chat_id=3002,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        # User 2 session
        session2 = SessionRecord(
            session_id=None,
            telegram_id=2003,
            chat_id=3003,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        repository.save(session1)
        repository.save(session2)

        # Get sessions for each user
        s1 = repository.get_active_session(2002, SessionFlow.ME_TESTA)
        s2 = repository.get_active_session(2003, SessionFlow.ME_TESTA)

        self.assertIsNotNone(s1)
        self.assertIsNotNone(s2)
        assert s1 is not None
        assert s2 is not None

        # Sessions should be different
        self.assertNotEqual(s1.session_id, s2.session_id)
        self.assertNotEqual(s1.chat_id, s2.chat_id)
        self.assertEqual(s1.telegram_id, 2002)
        self.assertEqual(s2.telegram_id, 2003)

    def test_lock_timestamp_reflects_acquisition_time(self) -> None:
        """Test that lock_timestamp is set when lock is acquired."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        session = SessionRecord(
            session_id=None,
            telegram_id=2004,
            chat_id=3004,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        repository.save(session)
        locked = repository.get_active_session_with_lock(2004, SessionFlow.ME_TESTA)

        self.assertIsNotNone(locked)
        assert locked is not None
        self.assertIsNotNone(locked.lock_timestamp)
        # Verify it's a valid ISO format timestamp
        self.assertIn("T", locked.lock_timestamp)
        # Timestamp should be ISO format (with timezone)
        self.assertTrue(
            locked.lock_timestamp.endswith("Z") or "+" in locked.lock_timestamp,
            f"Invalid timestamp format: {locked.lock_timestamp}"
        )

    def test_lock_metadata_survives_multiple_saves(self) -> None:
        """Test lock metadata is preserved across multiple save operations."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        session = SessionRecord(
            session_id=None,
            telegram_id=2005,
            chat_id=3005,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        repository.save(session)
        locked = repository.get_active_session_with_lock(2005, SessionFlow.ME_TESTA)

        self.assertIsNotNone(locked)
        assert locked is not None
        original_lock_id = locked.pessimistic_lock_id

        # Save multiple times
        for _ in range(3):
            repository.save(locked)

        # Reload and verify lock_id is still in metadata
        reloaded = repository.get_active_session(2005, SessionFlow.ME_TESTA)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        # Lock ID should have been preserved in metadata
        self.assertEqual(reloaded.pessimistic_lock_id, original_lock_id)


if __name__ == "__main__":
    unittest.main()
