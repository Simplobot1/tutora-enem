from __future__ import annotations

import re

from app.domain.models import QuestionAlternative, QuestionSnapshot


class QuestionSnapshotService:
    def build_from_text(self, text: str) -> QuestionSnapshot | None:
        normalized = " ".join(text.split())
        if len(normalized) < 24:
            return None

        alternatives = self._parse_alternatives(text)
        if len(alternatives) < 4:
            return None

        stem = self._parse_stem(text).strip()
        if len(stem) < 20:
            return None

        return QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content=stem,
            alternatives=alternatives,
            correct_alternative=None,
            explanation="",
        )

    def _parse_stem(self, text: str) -> str:
        parts = re.split(r"(?:^|[\n\r])\s*[A-E](?:\)|\.|:|-)?\s+", text, maxsplit=1, flags=re.MULTILINE)
        return " ".join((parts[0] if parts else text).split())

    def _parse_alternatives(self, text: str) -> list[QuestionAlternative]:
        pattern = r"(?:^|[\n\r])\s*([A-E])(?:\)|\.|:|-)?\s+(.*?)(?=(?:^|[\n\r])\s*[A-E](?:\)|\.|:|-)?\s+|\Z)"
        matches = list(re.finditer(pattern, text, re.MULTILINE | re.DOTALL))
        alternatives: list[QuestionAlternative] = []
        seen: set[str] = set()
        for match in matches:
            label = match.group(1).upper()
            option_text = " ".join(match.group(2).split())
            if label in seen or not option_text:
                continue
            seen.add(label)
            alternatives.append(QuestionAlternative(label=label, text=option_text))
        return alternatives
