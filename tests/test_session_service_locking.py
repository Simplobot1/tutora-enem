"""Tests for SessionService with pessimistic locking.

M2-S2: Pessimistic locking + race condition mitigation.
Tests that SessionService correctly uses pessimistic locking to prevent race conditions.
"""

import unittest

from app.domain.models import SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import SupabaseStudySessionsRepository, RaceLockError
from app.services.session_service import SessionService
from tests.test_study_sessions_repository import FakeSupabaseClient


class SessionServiceLockingTest(unittest.TestCase):
    def test_get_or_create_active_session_with_lock_acquires_lock(self) -> None:
        """Test M2-S2: SessionService.get_or_create_active_session_with_lock acquires lock."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        service = SessionService(repository)

        # Create initial session
        session = service.get_or_create_active_session(
            telegram_id=123,
            chat_id=456,
            flow=SessionFlow.ME_TESTA,
        )
        self.assertIsNotNone(session.session_id)

        # Get with lock
        locked = service.get_or_create_active_session_with_lock(
            telegram_id=123,
            chat_id=456,
            flow=SessionFlow.ME_TESTA,
        )

        self.assertIsNotNone(locked)
        self.assertIsNotNone(locked.pessimistic_lock_id)
        self.assertIsNotNone(locked.lock_timestamp)

    def test_get_or_create_creates_new_session_if_none_exists(self) -> None:
        """Test M2-S2: Creating new session doesn't require lock."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        service = SessionService(repository)

        # No existing session, should create new one
        session = service.get_or_create_active_session_with_lock(
            telegram_id=789,
            chat_id=101,
            flow=SessionFlow.SOCRATICO,
        )

        self.assertIsNotNone(session)
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.telegram_id, 789)
        self.assertEqual(session.chat_id, 101)
        self.assertEqual(session.flow, SessionFlow.SOCRATICO)

    def test_round_trip_with_lock_preserves_chat_id(self) -> None:
        """Test M2-S2: Round-trip with lock preserves chat_id."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        service = SessionService(repository)

        # Create session
        original_chat_id = 999
        session = service.get_or_create_active_session(
            telegram_id=111,
            chat_id=original_chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        # Update with lock
        locked = service.get_or_create_active_session_with_lock(
            telegram_id=111,
            chat_id=original_chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        self.assertEqual(locked.chat_id, original_chat_id)

        # Modify and save
        locked.state = SessionState.EVALUATING_ANSWER
        service.save(locked)

        # Reload and verify chat_id still preserved
        reloaded = service.get_or_create_active_session(
            telegram_id=111,
            chat_id=original_chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        self.assertEqual(reloaded.chat_id, original_chat_id)
        self.assertEqual(reloaded.state, SessionState.EVALUATING_ANSWER)

    def test_multiple_consecutive_locks_same_session(self) -> None:
        """Test M2-S2: Multiple consecutive locks on same session work correctly."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        service = SessionService(repository)

        # Create initial session
        session = service.get_or_create_active_session(
            telegram_id=222,
            chat_id=333,
            flow=SessionFlow.ME_TESTA,
        )

        # Simulate multiple sequential operations with locks
        for i in range(3):
            locked = service.get_or_create_active_session_with_lock(
                telegram_id=222,
                chat_id=333,
                flow=SessionFlow.ME_TESTA,
            )

            self.assertIsNotNone(locked.pessimistic_lock_id)
            # Modify and save (change state to verify updates persist)
            if i == 0:
                locked.state = SessionState.IDLE
            elif i == 1:
                locked.state = SessionState.WAITING_ANSWER
            else:
                locked.state = SessionState.EVALUATING_ANSWER
            service.save(locked)

        # Verify final state
        final = service.get_or_create_active_session(
            telegram_id=222,
            chat_id=333,
            flow=SessionFlow.ME_TESTA,
        )

        self.assertEqual(final.chat_id, 333)
        self.assertEqual(final.state, SessionState.EVALUATING_ANSWER)


if __name__ == "__main__":
    unittest.main()
