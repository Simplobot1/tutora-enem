"""Tests for snapshot + bank_match integrity validation.

M2-S2: Snapshot + bank_match maintains integrity through round-trips.
Tests that question snapshots and bank matches are not corrupted during persistence.
"""

import unittest

from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
from app.domain.session_metadata import QuestionRef, SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import SupabaseStudySessionsRepository
from tests.test_study_sessions_repository import FakeSupabaseClient


class SnapshotBankMatchIntegrityTest(unittest.TestCase):
    """Test M2-S2 AC #3: Snapshot + bank_match maintains integrity."""

    def test_snapshot_content_preserved_round_trip(self) -> None:
        """Test snapshot content is preserved across persistence."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        snapshot = QuestionSnapshot(
            source_mode="bank_match",
            source_truth="student_content_plus_bank_match",
            content="Uma célula vegetal difere de uma animal principalmente por...",
            alternatives=[
                QuestionAlternative(label="A", text="Possuir mitocôndria"),
                QuestionAlternative(label="B", text="Possuir parede celular"),
                QuestionAlternative(label="C", text="Possuir núcleo"),
                QuestionAlternative(label="D", text="Possuir membrana plasmática"),
                QuestionAlternative(label="E", text="Possuir ribossomo"),
            ],
            correct_alternative="B",
            explanation="A parede celular é característica das células vegetais.",
            subject="Biologia",
            topic="Citologia",
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1000,
            chat_id=2000,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=snapshot,
            ),
        )

        saved = repository.save(session)
        reloaded = repository.get_active_session(1000, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertIsNotNone(reloaded.question_snapshot)
        self.assertEqual(reloaded.question_snapshot.content, snapshot.content)
        self.assertEqual(reloaded.question_snapshot.source_mode, "bank_match")
        self.assertEqual(reloaded.question_snapshot.subject, "Biologia")
        self.assertEqual(reloaded.question_snapshot.topic, "Citologia")

    def test_alternatives_preserved_round_trip(self) -> None:
        """Test all alternatives are preserved without corruption."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        alternatives = [
            QuestionAlternative(label="A", text="Option A text"),
            QuestionAlternative(label="B", text="Option B text"),
            QuestionAlternative(label="C", text="Option C text"),
            QuestionAlternative(label="D", text="Option D text"),
            QuestionAlternative(label="E", text="Option E text"),
        ]

        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Test question",
            alternatives=alternatives,
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1001,
            chat_id=2001,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
                question_snapshot=snapshot,
            ),
        )

        repository.save(session)
        reloaded = repository.get_active_session(1001, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertIsNotNone(reloaded.question_snapshot)
        self.assertEqual(len(reloaded.question_snapshot.alternatives), 5)
        for i, alt in enumerate(reloaded.question_snapshot.alternatives):
            self.assertEqual(alt.label, alternatives[i].label)
            self.assertEqual(alt.text, alternatives[i].text)

    def test_correct_alternative_preserved(self) -> None:
        """Test correct_alternative is preserved during persistence."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        snapshot = QuestionSnapshot(
            source_mode="bank_match",
            source_truth="student_content_plus_bank_match",
            content="Question",
            alternatives=[
                QuestionAlternative(label="A", text="Wrong"),
                QuestionAlternative(label="B", text="Correct"),
            ],
            correct_alternative="B",
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1002,
            chat_id=2002,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=snapshot,
            ),
        )

        repository.save(session)
        reloaded = repository.get_active_session(1002, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.question_snapshot.correct_alternative, "B")

    def test_explanation_preserved(self) -> None:
        """Test explanation text is preserved."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        explanation = """Esta é uma explicação detalhada de por que a alternativa está correta.
        Ela pode ter múltiplas linhas e caracteres especiais como acentuação.
        Também pode ter números como 2 + 2 = 4."""

        snapshot = QuestionSnapshot(
            source_mode="bank_match",
            source_truth="student_content_plus_bank_match",
            content="Question",
            alternatives=[QuestionAlternative(label="A", text="Option")],
            explanation=explanation,
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1003,
            chat_id=2003,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=snapshot,
            ),
        )

        repository.save(session)
        reloaded = repository.get_active_session(1003, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.question_snapshot.explanation, explanation)

    def test_bank_match_metadata_preserved(self) -> None:
        """Test bank_match metadata is preserved."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        snapshot = QuestionSnapshot(
            source_mode="bank_match",
            source_truth="student_content_plus_bank_match",
            content="Question",
            alternatives=[QuestionAlternative(label="A", text="Option")],
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1004,
            chat_id=2004,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            source_mode="bank_match",
            question_id="q-123",
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=snapshot,
                question_id="q-123",
                question_ref=QuestionRef(
                    question_id="q-123",
                    snapshot_id="snap-456",
                    bank_match_confidence=0.95,
                ),
            ),
        )

        repository.save(session)
        reloaded = repository.get_active_session(1004, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.source_mode, "bank_match")
        self.assertEqual(reloaded.question_id, "q-123")
        self.assertEqual(reloaded.metadata.question_ref.question_id, "q-123")
        self.assertEqual(reloaded.metadata.question_ref.bank_match_confidence, 0.95)

    def test_student_submitted_snapshot_preserved(self) -> None:
        """Test student_submitted snapshots are preserved correctly."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Pergunta feita pelo estudante",
            alternatives=[
                QuestionAlternative(label="A", text="Resposta 1"),
                QuestionAlternative(label="B", text="Resposta 2"),
            ],
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1005,
            chat_id=2005,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            source_mode="student_submitted",
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
                question_snapshot=snapshot,
            ),
        )

        repository.save(session)
        reloaded = repository.get_active_session(1005, SessionFlow.ME_TESTA)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.source_mode, "student_submitted")
        self.assertEqual(reloaded.question_snapshot.source_mode, "student_submitted")
        self.assertEqual(reloaded.question_snapshot.source_truth, "student_content_only")

    def test_snapshot_and_chat_id_both_preserved(self) -> None:
        """Test both snapshot integrity AND chat_id are preserved together (M2-S2 requirement)."""
        client = FakeSupabaseClient()
        repository = SupabaseStudySessionsRepository(client)

        original_chat_id = 3000
        snapshot = QuestionSnapshot(
            source_mode="bank_match",
            source_truth="student_content_plus_bank_match",
            content="Full question text",
            alternatives=[QuestionAlternative(label="A", text="Option")],
            correct_alternative="A",
            explanation="Full explanation",
            subject="Subject",
            topic="Topic",
        )

        session = SessionRecord(
            session_id=None,
            telegram_id=1006,
            chat_id=original_chat_id,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            question_snapshot=snapshot,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="bank_match",
                question_snapshot=snapshot,
            ),
        )

        repository.save(session)

        # Multiple round-trips to verify durability
        for _ in range(3):
            reloaded = repository.get_active_session(1006, SessionFlow.ME_TESTA)
            self.assertIsNotNone(reloaded)
            assert reloaded is not None
            # Both must be preserved
            self.assertEqual(reloaded.chat_id, original_chat_id)
            self.assertEqual(reloaded.question_snapshot.content, "Full question text")
            self.assertEqual(reloaded.question_snapshot.correct_alternative, "A")


if __name__ == "__main__":
    unittest.main()
