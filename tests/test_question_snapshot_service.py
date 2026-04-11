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

    def test_build_from_text_accepts_trailing_alternative_labels(self) -> None:
        snapshot = self.service.build_from_text(
            "Uma função f(x) = 2x² - 8x + 6. Quais são os valores de x para os quais f(x) = 0?\n\n"
            "x = 1 e x = 3\n"
            "A\n\n"
            "x = 2 e x = 4\n"
            "B\n\n"
            "x = -1 e x = -3\",\n"
            "C\n\n"
            "x = 0 e x = 4\n"
            "D\n\n"
            "x = 2 e x = 6\n"
            "E"
        )
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.content, "Uma função f(x) = 2x² - 8x + 6. Quais são os valores de x para os quais f(x) = 0?")
        self.assertEqual(
            [(alt.label, alt.text) for alt in snapshot.alternatives],
            [
                ("A", "x = 1 e x = 3"),
                ("B", "x = 2 e x = 4"),
                ("C", "x = -1 e x = -3"),
                ("D", "x = 0 e x = 4"),
                ("E", "x = 2 e x = 6"),
            ],
        )
