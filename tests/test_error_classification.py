"""Tests for error classification (M2-S3).

Tests that errors are correctly classified into:
- Conceitual (misconception)
- Interpretação (misreading)
- Atenção (careless mistake)
"""

import unittest

from app.domain.error_classification import ErrorClassification, ErrorType


class ErrorClassificationTest(unittest.TestCase):
    """Test M2-S3: Error classification."""

    def test_classify_conceitual_error(self) -> None:
        """Test that misconception is classified as CONCEITUAL."""
        classification = ErrorClassification.classify(
            student_answer="B",
            correct_answer="D",
            question_content="Qual é a função da mitocôndria?",
            explanation="A mitocôndria produz energia (ATP), não armazena água.",
        )

        self.assertEqual(classification.error_type, ErrorType.CONCEITUAL)
        self.assertIn("conceito", classification.reasoning.lower())
        self.assertEqual(classification.severity, "high")

    def test_classify_interpretacao_error(self) -> None:
        """Test that misreading is classified as INTERPRETAÇÃO."""
        classification = ErrorClassification.classify(
            student_answer="C",
            correct_answer="D",
            question_content="Qual é a capital de São Paulo?",
            explanation="A resposta é São Paulo (cidade).",
        )

        # Adjacent alternatives suggest misreading
        self.assertEqual(classification.error_type, ErrorType.INTERPRETACAO)
        self.assertEqual(classification.severity, "medium")

    def test_classify_atencao_error(self) -> None:
        """Test default to ATENÇÃO for careless mistakes."""
        classification = ErrorClassification.classify(
            student_answer="C",
            correct_answer="A",  # Not adjacent (distance = 2)
            question_content="What is 2+2?",
            explanation="The answer is 4.",
        )

        self.assertEqual(classification.error_type, ErrorType.ATENCAO)
        self.assertEqual(classification.severity, "low")

    def test_classification_includes_suggested_focus(self) -> None:
        """Test that classification includes focus suggestion."""
        classification = ErrorClassification.classify(
            student_answer="A",
            correct_answer="D",
            question_content="Question about concepts",
            explanation="This requires understanding the fundamental concept",
        )

        self.assertIsNotNone(classification.suggested_focus)
        self.assertTrue(len(classification.suggested_focus) > 0)

    def test_classification_has_reasoning(self) -> None:
        """Test that classification includes reasoning."""
        classification = ErrorClassification.classify(
            student_answer="B",
            correct_answer="C",
            question_content="Any question",
            explanation="Any explanation",
        )

        self.assertIsNotNone(classification.reasoning)
        self.assertTrue(len(classification.reasoning) > 0)


if __name__ == "__main__":
    unittest.main()
