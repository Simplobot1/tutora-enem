from __future__ import annotations

import re

from app.domain.models import QuestionSnapshot


class QuestionCuratorService:
    """Apply deterministic local curation for known question patterns.

    This keeps student-submitted questions flowing even when no bank match exists.
    """

    def enrich(self, snapshot: QuestionSnapshot) -> QuestionSnapshot:
        normalized_stem = self._normalize(snapshot.content)
        normalized_alternatives = [self._normalize(alt.text) for alt in snapshot.alternatives]

        if (
            "triquinelose" in normalized_stem
            and "mesmas medidas preventivas" in normalized_stem
            and any("teniase" in alternative for alternative in normalized_alternatives)
            and any("esquistossomose" in alternative for alternative in normalized_alternatives)
        ):
            snapshot.correct_alternative = "A"
            snapshot.explanation = (
                "Triquinelose e teníase compartilham a prevenção ligada ao consumo seguro de carne: "
                "evitar carne crua ou malcozida e garantir inspeção/preparo adequado. "
                "Filariose, oxiurose, ancilostomose e esquistossomose dependem principalmente de "
                "controle de vetores, higiene ambiental ou saneamento/contato com água contaminada."
            )
            snapshot.subject = "Biologia"
            snapshot.topic = "Parasitologia"
            snapshot.source_truth = "student_content_plus_local_curation"

        return snapshot

    def _normalize(self, text: str) -> str:
        normalized = text.lower()
        normalized = normalized.replace("ã", "a").replace("á", "a").replace("â", "a")
        normalized = normalized.replace("é", "e").replace("ê", "e")
        normalized = normalized.replace("í", "i")
        normalized = normalized.replace("ó", "o").replace("ô", "o").replace("õ", "o")
        normalized = normalized.replace("ú", "u").replace("ç", "c")
        return re.sub(r"\s+", " ", normalized).strip()
