"""Error classification domain for M2-S3.

M2-S3: Classifies errors into Conceitual, Interpretação, Atenção.
Based on CLAUDE.md: "Classificação de Erros: todo erro deve ser classificado em: **Conceitual**, **Interpretação** ou **Atenção**."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorType(StrEnum):
    """Error classification types per project rules."""
    CONCEITUAL = "conceitual"  # Misconception about concept
    INTERPRETACAO = "interpretacao"  # Misread question or alternatives
    ATENCAO = "atencao"  # Careless mistake / attention slip


@dataclass(slots=True)
class ErrorClassification:
    """Classification of a student's error on a question."""
    error_type: ErrorType | None
    reasoning: str
    severity: str  # low, medium, high
    suggested_focus: str | None = None

    @classmethod
    def classify(
        cls,
        student_answer: str,
        correct_answer: str,
        question_content: str,
        explanation: str,
    ) -> ErrorClassification:
        """Classify error based on student answer vs correct answer.

        Heuristics:
        - If explanation contains key conceptual terms → Conceitual (misconception)
        - If adjacent alternatives (A/B, C/D, etc) → Interpretação (misread)
        - Otherwise → Atenção (careless slip)
        """
        student_answer_upper = (student_answer or "").strip().upper()
        correct_answer_upper = (correct_answer or "").strip().upper()

        # Check if explanationhints at conceptual error
        # Keywords suggest the explanation is about concepts/understanding
        concept_keywords = ["conceito", "função", "entender", "significado", "produz", "armazena", "diferença"]
        explanation_lower = explanation.lower()
        has_concept_keyword = any(kw in explanation_lower for kw in concept_keywords)

        if has_concept_keyword:
            return cls(
                error_type=ErrorType.CONCEITUAL,
                reasoning="Resposta sugere conceito errado ou falta de entendimento",
                severity="high",
                suggested_focus="Revisar conceito fundamental",
            )

        # If answer confuses similar alternatives (adjacent in alphabet)
        if error_suggests_misreading(student_answer_upper, correct_answer_upper):
            return cls(
                error_type=ErrorType.INTERPRETACAO,
                reasoning="Pode ter confundido alternativas ou não leu com atenção",
                severity="medium",
                suggested_focus="Ler com mais cuidado",
            )

        # Default to attention error (careless)
        return cls(
            error_type=ErrorType.ATENCAO,
            reasoning="Erro de atenção ou deslize",
            severity="low",
            suggested_focus="Revisar com mais atenção",
        )


def error_suggests_misreading(student_answer: str, correct_answer: str) -> bool:
    """Heuristic: does error suggest misreading/confusion?

    Returns True if answers are adjacent (A/B, B/C, C/D, D/E),
    which commonly suggests misreading or confusion.
    """
    if student_answer in "ABCDE" and correct_answer in "ABCDE":
        answer_map = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
        if student_answer in answer_map and correct_answer in answer_map:
            dist = abs(answer_map[student_answer] - answer_map[correct_answer])
            return dist == 1  # Adjacent = likely misreading
    return False
