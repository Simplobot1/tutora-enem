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
        lines = text.splitlines()
        start_index, _ = self._find_alternative_block(lines)
        stem_lines = lines[:start_index] if start_index is not None else lines
        return " ".join(" ".join(stem_lines).split())

    def _parse_alternatives(self, text: str) -> list[QuestionAlternative]:
        lines = text.splitlines()
        start_index, end_index = self._find_alternative_block(lines)
        if start_index is None or end_index is None:
            return []

        trailing_label_alternatives = self._parse_trailing_label_alternatives(lines[start_index:end_index])
        if trailing_label_alternatives:
            return trailing_label_alternatives

        alternatives: list[QuestionAlternative] = []
        seen: set[str] = set()

        current_label: str | None = None
        current_text: list[str] = []

        for line in lines[start_index:end_index]:
            match = re.match(r"^\s*([A-E])(?:\)|\.|:|-)?\s+(.+)$", line)
            if match:
                if current_label is not None:
                    option_text = " ".join(" ".join(current_text).split())
                    if current_label not in seen and option_text:
                        seen.add(current_label)
                        alternatives.append(QuestionAlternative(label=current_label, text=option_text))
                current_label = match.group(1).upper()
                current_text = [match.group(2)]
                continue

            if current_label is not None and line.strip():
                current_text.append(line.strip())

        if current_label is not None:
            option_text = " ".join(" ".join(current_text).split())
            label = current_label.upper()
            if label not in seen and option_text:
                seen.add(label)
                alternatives.append(QuestionAlternative(label=label, text=option_text))

        return alternatives

    def _parse_trailing_label_alternatives(self, lines: list[str]) -> list[QuestionAlternative]:
        alternatives: list[QuestionAlternative] = []
        seen: set[str] = set()
        pending_text: list[str] = []

        for line in lines:
            stripped = line.strip().strip('",')
            if not stripped:
                continue

            match = re.match(r"^([A-E])(?:\)|\.|:|-)?$", stripped)
            if match:
                label = match.group(1).upper()
                option_text = " ".join(" ".join(pending_text).split()).strip('",')
                if label not in seen and option_text:
                    seen.add(label)
                    alternatives.append(QuestionAlternative(label=label, text=option_text))
                pending_text = []
                continue

            pending_text.append(stripped)

        if len(alternatives) >= 4:
            return alternatives
        return []

    def _find_alternative_block(self, lines: list[str]) -> tuple[int | None, int | None]:
        matches: list[tuple[int, str, bool]] = []
        for index, line in enumerate(lines):
            match = re.match(r"^\s*([A-E])(?:\)|\.|:|-)?\s+(.+)$", line)
            if match is not None:
                matches.append((index, match.group(1).upper(), False))
                continue

            trailing_match = re.match(r"^\s*([A-E])(?:\)|\.|:|-)?\s*$", line)
            if trailing_match is not None:
                matches.append((index, trailing_match.group(1).upper(), True))

        if not matches:
            return None, None

        best_start: int | None = None
        best_end: int | None = None
        best_length = 0

        for offset in range(len(matches)):
            index, label, is_trailing_label = matches[offset]
            if label != "A":
                continue
            current_end = index + 1
            expected_ord = ord("A")
            length = 0
            for next_index, next_label, _ in matches[offset:]:
                if ord(next_label) != expected_ord:
                    if length >= 4:
                        break
                    if next_label != "A":
                        length = 0
                        break
                length += 1
                current_end = next_index + 1
                expected_ord += 1
                if expected_ord > ord("E"):
                    break
            if length >= 4 and length >= best_length:
                best_start = self._alternative_start_index(lines, index) if is_trailing_label else index
                best_end = current_end
                best_length = length

        return best_start, best_end

    def _alternative_start_index(self, lines: list[str], label_index: int) -> int:
        previous_index = label_index - 1
        while previous_index >= 0 and not lines[previous_index].strip():
            previous_index -= 1
        if previous_index < 0:
            return label_index

        previous = lines[previous_index].strip()
        if re.match(r"^[A-E](?:\)|\.|:|-)?(?:\s+.+)?$", previous):
            return label_index
        return previous_index
