from __future__ import annotations

import re
from typing import Any


class QuestionsRepository:
    def __init__(self, client: Any | None) -> None:
        self.client = client

    def find_best_match(self, stem: str, alternatives: list[str] | None = None, limit: int = 8) -> dict[str, Any] | None:
        if self.client is None or not stem.strip():
            return None

        try:
            search_terms = self._extract_search_terms(stem)
            if not search_terms:
                return None
            query = self.client.table("questions").select(
                "id,content,alternatives,correct_alternative,explanation,subject,topic,year"
            )
            for term in search_terms[:2]:
                query = query.ilike("content", f"%{term}%")
            response = query.limit(limit).execute()
        except Exception:
            return None

        rows = getattr(response, "data", None) or []
        best_match: dict[str, Any] | None = None
        best_confidence = 0.0
        for row in rows:
            confidence = self._score_candidate(stem, alternatives or [], row)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {**row, "match_confidence": round(confidence, 4)}
        if best_match is None or best_confidence < 0.55:
            return None
        return best_match

    def _extract_search_terms(self, stem: str) -> list[str]:
        tokens = sorted(
            {token for token in self._tokenize(stem) if len(token) >= 5},
            key=len,
            reverse=True,
        )
        return tokens[:4]

    def _score_candidate(self, stem: str, alternatives: list[str], candidate: dict[str, Any]) -> float:
        stem_tokens = set(self._tokenize(stem))
        candidate_tokens = set(self._tokenize(candidate.get("content", "")))
        if not stem_tokens or not candidate_tokens:
            return 0.0

        stem_overlap = len(stem_tokens & candidate_tokens) / len(stem_tokens)
        submitted_alt_tokens = set(self._tokenize(" ".join(alternatives)))
        candidate_alt_tokens = set(
            self._tokenize(
                " ".join(
                    alt.get("text", "")
                    for alt in (candidate.get("alternatives") or [])
                    if isinstance(alt, dict)
                )
            )
        )
        alternatives_overlap = 0.0
        if submitted_alt_tokens and candidate_alt_tokens:
            alternatives_overlap = len(submitted_alt_tokens & candidate_alt_tokens) / len(submitted_alt_tokens)
        return (0.75 * stem_overlap) + (0.25 * alternatives_overlap)

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zà-ÿ0-9]+", text.lower())
