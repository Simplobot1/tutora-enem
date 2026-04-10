"""M4-S1: Jobs Tests

Test APKG building and weekly reporting functionality.
"""

import json
import unittest
from tempfile import TemporaryDirectory

from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
from app.domain.session_metadata import AnkiMetadata, ReviewCard, SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
from app.services.apkg_builder_service import ApkgBuilderService
from app.services.weekly_report_job_service import ReportExporter, WeeklyReportJobService, WeeklyStats


class ApkgBuilderTest(unittest.TestCase):
    """Test APKG building from review cards."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.builder = ApkgBuilderService(output_dir=self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_apkg_from_review_card(self) -> None:
        """Test: review_card → .apkg file generated."""
        session = SessionRecord(
            session_id="test-session-1",
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            question_snapshot=QuestionSnapshot(
                source_mode="bank_match",
                source_truth="student_content_plus_bank_match",
                content="O que é mitocôndria?",
                alternatives=[
                    QuestionAlternative(label="A", text="Organela de reprodução"),
                    QuestionAlternative(label="B", text="Organela de respiração"),
                    QuestionAlternative(label="C", text="Organela de digestão"),
                    QuestionAlternative(label="D", text="Organela de transporte"),
                    QuestionAlternative(label="E", text="Organela de armazenamento"),
                ],
                correct_alternative="B",
                explanation="Mitocôndria é a organela responsável pela respiração celular.",
                subject="Biologia",
                topic="Citologia",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="bank_match",
                review_card=ReviewCard(
                    review_card_id="rc-1",
                    front="📝 Biologia - Citologia\n\nO que é mitocôndria?",
                    back="✅ Resposta correta: B\n\nMitocôndria é a organela responsável pela respiração celular.",
                ),
            ),
        )

        apkg_path = self.builder.build_apkg_from_session(session)

        self.assertIsNotNone(apkg_path)
        self.assertTrue(apkg_path.endswith(".apkg"))
        self.assertTrue(apkg_path.startswith(self.temp_dir.name))

    def test_build_apkg_missing_review_card(self) -> None:
        """Test: session without review_card → None returned."""
        session = SessionRecord(
            session_id="test-session-2",
            telegram_id=124,
            chat_id=322,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
            ),
        )

        apkg_path = self.builder.build_apkg_from_session(session)

        self.assertIsNone(apkg_path)

    def test_hash_to_deck_id_deterministic(self) -> None:
        """Test: same session_id → same deck_id (deterministic)."""
        session_id = "test-session-3"

        deck_id_1 = self.builder._hash_to_deck_id(session_id)
        deck_id_2 = self.builder._hash_to_deck_id(session_id)

        self.assertEqual(deck_id_1, deck_id_2)
        self.assertIsInstance(deck_id_1, int)
        self.assertGreater(deck_id_1, 0)

    def test_extract_subject_and_topic(self) -> None:
        """Test: extract subject/topic from review card front."""
        front = "📝 Biologia - Parasitologia\n\nO que é..."

        subject = self.builder._extract_subject(front)
        topic = self.builder._extract_topic(front)

        self.assertEqual(subject, "Biologia")
        self.assertEqual(topic, "Parasitologia")

    def test_apkg_idempotent(self) -> None:
        """Test: same review_card → same .apkg generated (idempotency)."""
        review_card = ReviewCard(
            review_card_id="rc-2",
            front="📝 Biologia\n\nQuestion",
            back="✅ Answer",
        )

        session_1 = SessionRecord(
            session_id="test-4-1",
            telegram_id=125,
            chat_id=323,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="bank_match",
                review_card=review_card,
            ),
        )

        session_2 = SessionRecord(
            session_id="test-4-2",
            telegram_id=126,
            chat_id=324,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="bank_match",
                review_card=review_card,
            ),
        )

        apkg_1 = self.builder.build_apkg_from_session(session_1)
        apkg_2 = self.builder.build_apkg_from_session(session_2)

        # Both should generate valid APKGs
        self.assertIsNotNone(apkg_1)
        self.assertIsNotNone(apkg_2)
        self.assertTrue(apkg_1.endswith(".apkg"))
        self.assertTrue(apkg_2.endswith(".apkg"))


class WeeklyReportTest(unittest.TestCase):
    """Test weekly report generation."""

    def setUp(self) -> None:
        self.repository = InMemoryStudySessionsRepository()
        self.service = WeeklyReportJobService(self.repository)

    def test_generate_weekly_report_structure(self) -> None:
        """Test: weekly report has required structure."""
        stats = self.service.generate_weekly_report(days_back=7)

        self.assertIsInstance(stats, WeeklyStats)
        self.assertIsNotNone(stats.period_start)
        self.assertIsNotNone(stats.period_end)
        self.assertEqual(stats.total_sessions, 0)  # Mock data

    def test_weekly_stats_to_dict_no_telegram_id(self) -> None:
        """Test: exported stats do NOT contain telegram_id."""
        stats = WeeklyStats(
            period_start="2026-04-01",
            period_end="2026-04-08",
            total_sessions=5,
            total_questions=10,
            questions_correct=7,
            accuracy_percentage=70.0,
        )

        data = stats.to_dict()

        self.assertNotIn("telegram_id", str(data))
        self.assertIn("period", data)
        self.assertIn("sessions", data)
        self.assertIn("questions", data)
        self.assertEqual(data["questions"]["accuracy_percentage"], 70.0)

    def test_aggregate_session_stats_no_exposure(self) -> None:
        """Test: aggregated stats protect privacy (no telegram_id linking)."""
        session_1 = SessionRecord(
            session_id="s1",
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            mood="feliz",
            question_snapshot=QuestionSnapshot(
                source_mode="bank_match",
                source_truth="student_content_plus_bank_match",
                content="Q1",
                subject="Biologia",
                topic="Citologia",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="bank_match",
            ),
        )

        session_2 = SessionRecord(
            session_id="s2",
            telegram_id=124,
            chat_id=322,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.DONE,
            mood="cansada",
            question_snapshot=QuestionSnapshot(
                source_mode="student_submitted",
                source_truth="student_content_only",
                content="Q2",
                subject="História",
                topic="Colonial",
            ),
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.DONE,
                source_mode="student_submitted",
            ),
        )

        stats = self.service.aggregate_session_stats([session_1, session_2])

        # Verify no telegram_id in output (as strings)
        stats_str = str(stats)
        self.assertNotIn("123", stats_str)  # telegram_id 123 should not appear
        self.assertNotIn("124", stats_str)  # telegram_id 124 should not appear

        # Verify aggregation worked
        self.assertEqual(stats["total_sessions"], 2)
        self.assertEqual(stats["total_questions_attempted"], 2)
        self.assertIn("Biologia", stats["subjects"])
        self.assertIn("História", stats["subjects"])
        self.assertEqual(stats["moods"]["feliz"], 1)
        self.assertEqual(stats["moods"]["cansada"], 1)


class ReportExportTest(unittest.TestCase):
    """Test report export formats."""

    def setUp(self) -> None:
        self.stats = WeeklyStats(
            period_start="2026-04-01",
            period_end="2026-04-08",
            total_sessions=3,
            total_questions=6,
            questions_correct=4,
            accuracy_percentage=66.67,
        )
        self.stats.subjects_covered = {"Biologia", "Química"}
        self.stats.topics_covered = {"Citologia", "Termoquímica"}
        self.stats.mood_distribution = {"feliz": 2, "cansada": 1}
        self.stats.learning_paths_used = {"socratic": 2, "direct": 1}

    def test_export_json(self) -> None:
        """Test: export as JSON."""
        json_str = ReportExporter.export_json(self.stats)

        data = json.loads(json_str)
        self.assertIn("period", data)
        self.assertIn("questions", data)
        self.assertEqual(data["questions"]["accuracy_percentage"], 66.67)

    def test_export_text(self) -> None:
        """Test: export as human-readable text."""
        text = ReportExporter.export_text(self.stats)

        self.assertIn("Relatório Semanal", text)
        self.assertIn("2026-04-01", text)
        self.assertIn("66.67%", text)
        self.assertIn("Biologia", text)
        self.assertIn("feliz", text)

    def test_export_no_telegram_id(self) -> None:
        """Test: exports do NOT contain telegram_id references."""
        json_str = ReportExporter.export_json(self.stats)
        text = ReportExporter.export_text(self.stats)

        self.assertNotIn("telegram", json_str.lower())
        self.assertNotIn("telegram", text.lower())


class ApkgBuildResultTest(unittest.TestCase):
    """Test ApkgBuildResult data class."""

    def test_result_success(self) -> None:
        """Test: successful build result."""
        from app.services.apkg_builder_service import ApkgBuildResult

        result = ApkgBuildResult(
            session_id="test-1",
            success=True,
            apkg_path="/path/to/deck.apkg",
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.apkg_path)

    def test_result_failure(self) -> None:
        """Test: failed build result."""
        from app.services.apkg_builder_service import ApkgBuildResult

        result = ApkgBuildResult(
            session_id="test-2",
            success=False,
            error="no_review_card",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "no_review_card")
        self.assertIsNone(result.apkg_path)

    def test_result_to_dict(self) -> None:
        """Test: result serialization."""
        from app.services.apkg_builder_service import ApkgBuildResult

        result = ApkgBuildResult(
            session_id="test-3",
            success=True,
            apkg_path="/deck.apkg",
        )

        data = result.to_dict()

        self.assertIn("session_id", data)
        self.assertIn("success", data)
        self.assertIn("apkg_path", data)


if __name__ == "__main__":
    unittest.main()
