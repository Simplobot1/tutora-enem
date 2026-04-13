from __future__ import annotations

from app.domain.models import SessionRecord


class AlternativeExplanationService:
    def ensure_alternative_explanations(self, session: SessionRecord) -> None:
        snapshot = session.question_snapshot
        if snapshot is None or not snapshot.alternatives:
            return

        correct_answer = snapshot.correct_alternative or ""
        correct_text = ""
        for alternative in snapshot.alternatives:
            if alternative.label == correct_answer:
                correct_text = alternative.text
                break

        for alternative in snapshot.alternatives:
            if alternative.explanation:
                continue
            if alternative.label == correct_answer:
                alternative.explanation = (
                    snapshot.explanation
                    or "Esta é a alternativa correta de acordo com o gabarito confirmado."
                )
                continue
            alternative.explanation = self._build_incorrect_alternative_explanation(
                alternative_text=alternative.text,
                correct_label=correct_answer,
                correct_text=correct_text,
            )

    def _build_incorrect_alternative_explanation(
        self,
        *,
        alternative_text: str,
        correct_label: str,
        correct_text: str,
    ) -> str:
        correct_reference = (
            f"A alternativa {correct_label} ({correct_text}) é a correta."
            if correct_label and correct_text
            else "Compare com a alternativa correta indicada no gabarito."
        )
        return (
            f"Incorreta: {alternative_text} não corresponde ao gabarito confirmado. "
            f"{correct_reference}"
        )
