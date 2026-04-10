import unittest

from app.services.question_snapshot_service import QuestionSnapshotService


class QuestionSnapshotServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = QuestionSnapshotService()

    def test_build_from_text_returns_snapshot_for_complete_question(self) -> None:
        snapshot = self.service.build_from_text(
            "Qual das verminoses a seguir apresenta as mesmas medidas preventivas?\n"
            "A Teníase.\nB Filariose.\nC Oxiurose.\nD Ancilostomose.\nE Esquistossomose."
        )
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.source_mode, "student_submitted")
        self.assertEqual(len(snapshot.alternatives), 5)
        self.assertIsNone(snapshot.correct_alternative)
        self.assertEqual(snapshot.explanation, "")

    def test_build_from_text_rejects_incomplete_input(self) -> None:
        snapshot = self.service.build_from_text("Pode me ajudar em biologia?")
        self.assertIsNone(snapshot)

    def test_build_from_text_accepts_variant_alternative_markers(self) -> None:
        snapshot = self.service.build_from_text(
            "Leia a questão abaixo e marque a correta.\n"
            "A) opção um\n"
            "B: opção dois\n"
            "C - opção três\n"
            "D. opção quatro\n"
            "E) opção cinco"
        )
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual([alt.label for alt in snapshot.alternatives], ["A", "B", "C", "D", "E"])
