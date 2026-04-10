import unittest
from uuid import uuid4

from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
from app.domain.session_metadata import QuestionRef, SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import SupabaseStudySessionsRepository, RaceLockError


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTableQuery:
    def __init__(self, client, name: str):
        self.client = client
        self.name = name
        self.filters: list[tuple[str, object]] = []
        self.limit_value: int | None = None

    def select(self, _fields: str):
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def insert(self, payload):
        self.client.pending_insert = payload
        return self

    def update(self, payload):
        self.client.pending_update = payload
        return self

    def execute(self):
        if self.client.pending_insert is not None:
            # Generate unique ID for each insert
            unique_id = f"session-db-{len(self.client.rows) + 1}"
            self.client.rows.append({"id": unique_id, **self.client.pending_insert})
            self.client.pending_insert = None
            return FakeResponse([self.client.rows[-1]])
        if self.client.pending_update is not None:
            row_id = dict(self.filters).get("id")
            for row in self.client.rows:
                if row["id"] == row_id:
                    row.update(self.client.pending_update)
                    self.client.pending_update = None
                    return FakeResponse([row])
            self.client.pending_update = None
            return FakeResponse([])

        rows = list(self.client.rows)
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return FakeResponse(rows)


class FakeRpcQuery:
    def __init__(self, client: "FakeSupabaseClient", function_name: str, params: dict):
        self.client = client
        self.function_name = function_name
        self.params = params

    def execute(self):
        if self.function_name == "get_active_session_with_lock":
            # Simulate pessimistic locking with lock metadata injection
            p_telegram_id = self.params.get("p_telegram_id")
            p_flow = self.params.get("p_flow")
            p_lock_id = self.params.get("p_lock_id")
            p_lock_timestamp = self.params.get("p_lock_timestamp")

            for row in self.client.rows:
                if (
                    row.get("telegram_id") == p_telegram_id
                    and row.get("status") == "active"
                    and (row.get("metadata") or {}).get("flow") == p_flow
                ):
                    # Inject lock metadata
                    row_copy = dict(row)
                    metadata = dict(row_copy.get("metadata") or {})
                    metadata["pessimistic_lock_id"] = str(p_lock_id)
                    metadata["lock_timestamp"] = p_lock_timestamp
                    row_copy["metadata"] = metadata
                    return FakeResponse([row_copy])
            return FakeResponse([])
        return FakeResponse([])


class FakeSupabaseClient:
    def __init__(self):
        self.rows: list[dict] = []
        self.pending_insert = None
        self.pending_update = None

    def table(self, name: str):
        return FakeTableQuery(self, name)

    def rpc(self, function_name: str, params: dict):
        return FakeRpcQuery(self, function_name, params)


class SupabaseStudySessionsRepositoryTest(unittest.TestCase):
    def test_round_trip_preserves_chat_id_and_bank_match_snapshot(self) -> None:
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        session = SessionRecord(
            session_id=None,
            telegram_id=123,
            chat_id=999,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            source_mode="bank_match",
            question_id="question-123",
            question_snapshot=QuestionSnapshot(
                source_mode="bank_match",
                source_truth="student_content_plus_bank_match",
                content="Enunciado completo",
                alternatives=[QuestionAlternative(label="A", text="Opção A")],
                correct_alternative="B",
                explanation="Explicação do banco",
                subject="Biologia",
                topic="Parasitologia",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=QuestionSnapshot(
                    source_mode="bank_match",
                    source_truth="student_content_plus_bank_match",
                    content="Enunciado completo",
                    alternatives=[QuestionAlternative(label="A", text="Opção A")],
                    correct_alternative="B",
                    explanation="Explicação do banco",
                    subject="Biologia",
                    topic="Parasitologia",
                ),
                question_id="question-123",
                question_ref=QuestionRef(question_id="question-123", bank_match_confidence=0.91),
                last_user_message={"text": "Questão", "message_id": 100, "chat_id": 999},
            ),
        )

        saved = repository.save(session)
        reloaded = repository.get_active_session(123, SessionFlow.ME_TESTA)

        self.assertEqual(saved.session_id, "session-db-1")
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.chat_id, 999)
        self.assertEqual(reloaded.question_snapshot.correct_alternative, "B")
        self.assertEqual(reloaded.question_snapshot.explanation, "Explicação do banco")
        self.assertEqual(reloaded.metadata.question_ref.bank_match_confidence, 0.91)

    def test_get_active_session_with_pessimistic_lock(self) -> None:
        """Test M2-S2: Pessimistic locking acquires lock and sets lock_id/timestamp."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        session = SessionRecord(
            session_id=None,
            telegram_id=456,
            chat_id=111,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        saved = repository.save(session)
        locked_session = repository.get_active_session_with_lock(456, SessionFlow.ME_TESTA)

        self.assertIsNotNone(locked_session)
        assert locked_session is not None
        self.assertIsNotNone(locked_session.pessimistic_lock_id)
        self.assertIsNotNone(locked_session.lock_timestamp)
        self.assertEqual(locked_session.chat_id, 111)

    def test_lock_metadata_preserved_in_save(self) -> None:
        """Test M2-S2: Lock metadata is preserved when saving a locked session."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)
        lock_id = str(uuid4())

        session = SessionRecord(
            session_id=None,
            telegram_id=789,
            chat_id=222,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            pessimistic_lock_id=lock_id,
            lock_timestamp="2026-04-09T10:00:00Z",
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        saved = repository.save(session)
        reloaded = repository.get_active_session(789, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        # Verify lock metadata was persisted and can be reloaded
        self.assertEqual(reloaded.pessimistic_lock_id, lock_id)
        self.assertEqual(reloaded.lock_timestamp, "2026-04-09T10:00:00Z")

    def test_multiple_sessions_different_flows_isolated(self) -> None:
        """Test M2-S2: Sessions with different flows don't interfere (race condition prevention)."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        # Create sessions for different flows
        me_testa_session = SessionRecord(
            session_id=None,
            telegram_id=999,
            chat_id=333,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        socratico_session = SessionRecord(
            session_id=None,
            telegram_id=999,
            chat_id=444,
            flow=SessionFlow.SOCRATICO,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.SOCRATICO,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        repository.save(me_testa_session)
        repository.save(socratico_session)

        # Verify each flow has its own session
        me_testa = repository.get_active_session(999, SessionFlow.ME_TESTA)
        socratico = repository.get_active_session(999, SessionFlow.SOCRATICO)

        self.assertIsNotNone(me_testa)
        self.assertIsNotNone(socratico)
        assert me_testa is not None
        assert socratico is not None
        self.assertEqual(me_testa.chat_id, 333)
        self.assertEqual(socratico.chat_id, 444)
        self.assertNotEqual(me_testa.session_id, socratico.session_id)

    def test_race_condition_mitigation_chat_id_not_corrupted(self) -> None:
        """Test M2-S2: Round-trip preserves chat_id without race condition corruption."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        # Initial session with specific chat_id
        original_chat_id = 555
        session = SessionRecord(
            session_id=None,
            telegram_id=111,
            chat_id=original_chat_id,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_content_only",
            ),
        )

        saved = repository.save(session)
        self.assertIsNotNone(saved.session_id)

        # Simulate multiple round-trips (potential race condition scenario)
        for _ in range(5):
            reloaded = repository.get_active_session(111, SessionFlow.ME_TESTA)
            self.assertIsNotNone(reloaded)
            assert reloaded is not None
            # chat_id should never change
            self.assertEqual(reloaded.chat_id, original_chat_id)

            # Save again with modification
            reloaded.state = SessionState.EVALUATING_ANSWER
            repository.save(reloaded)
