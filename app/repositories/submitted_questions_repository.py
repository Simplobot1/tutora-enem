from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import uuid4

from app.domain.models import QuestionSnapshot, SessionRecord

logger = logging.getLogger(__name__)


def serialize_alternatives(snapshot: QuestionSnapshot) -> list[dict[str, str]]:
    return [
        {"label": alt.label, "text": alt.text, "explanation": alt.explanation}
        for alt in snapshot.alternatives
    ]


class SubmittedQuestionsRepository(Protocol):
    def create_from_snapshot(self, session: SessionRecord, snapshot: QuestionSnapshot) -> str | None:
        ...

    def sync_snapshot(self, snapshot_id: str, snapshot: QuestionSnapshot) -> None:
        ...

    def mark_result(
        self,
        snapshot_id: str,
        *,
        answered_correct: bool,
        retry_attempts: int,
        sent_to_anki: bool,
        apkg_generated: bool,
        apkg_path: str | None = None,
        error_type: str | None = None,
    ) -> None:
        ...


class InMemorySubmittedQuestionsRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def create_from_snapshot(self, session: SessionRecord, snapshot: QuestionSnapshot) -> str | None:
        snapshot_id = str(uuid4())
        self.rows[snapshot_id] = {
            "id": snapshot_id,
            "session_id": session.session_id,
            "telegram_id": session.telegram_id,
            "content": snapshot.content,
            "alternatives": serialize_alternatives(snapshot),
            "correct_alternative": snapshot.correct_alternative,
            "explanation": snapshot.explanation,
            "subject": snapshot.subject,
            "topic": snapshot.topic,
            "source_truth": snapshot.source_truth,
            "answered_correct": None,
            "final_error_type": None,
            "retry_attempts": 0,
            "sent_to_anki": False,
            "apkg_generated": False,
            "apkg_path": None,
        }
        return snapshot_id

    def sync_snapshot(self, snapshot_id: str, snapshot: QuestionSnapshot) -> None:
        row = self.rows.get(snapshot_id)
        if row is None:
            return
        row.update(
            {
                "content": snapshot.content,
                "alternatives": serialize_alternatives(snapshot),
                "correct_alternative": snapshot.correct_alternative,
                "explanation": snapshot.explanation,
                "subject": snapshot.subject,
                "topic": snapshot.topic,
                "source_truth": snapshot.source_truth,
            }
        )

    def mark_result(
        self,
        snapshot_id: str,
        *,
        answered_correct: bool,
        retry_attempts: int,
        sent_to_anki: bool,
        apkg_generated: bool,
        apkg_path: str | None = None,
        error_type: str | None = None,
    ) -> None:
        row = self.rows.get(snapshot_id)
        if row is None:
            return
        row.update(
            {
                "answered_correct": answered_correct,
                "retry_attempts": retry_attempts,
                "sent_to_anki": sent_to_anki,
                "apkg_generated": apkg_generated,
                "apkg_path": apkg_path,
                "final_error_type": error_type,
            }
        )


class SupabaseSubmittedQuestionsRepository:
    def __init__(self, client: Any | None) -> None:
        self.client = client
        self._disabled = False

    def create_from_snapshot(self, session: SessionRecord, snapshot: QuestionSnapshot) -> str | None:
        if self.client is None or self._disabled:
            return None
        payload = self._snapshot_payload(session, snapshot)
        try:
            response = self.client.table("submitted_questions").insert(payload).execute()
        except Exception as exc:
            self._handle_storage_error("create_from_snapshot", exc)
            return None
        rows = getattr(response, "data", None) or []
        if not rows:
            return None
        return rows[0].get("id")

    def sync_snapshot(self, snapshot_id: str, snapshot: QuestionSnapshot) -> None:
        if self.client is None or self._disabled or not snapshot_id:
            return
        payload = {
            "content": snapshot.content,
            "alternatives": serialize_alternatives(snapshot),
            "correct_alternative": snapshot.correct_alternative,
            "explanation": snapshot.explanation,
            "subject": snapshot.subject,
            "topic": snapshot.topic,
            "source_truth": snapshot.source_truth,
        }
        try:
            self.client.table("submitted_questions").update(payload).eq("id", snapshot_id).execute()
        except Exception as exc:
            self._handle_storage_error("sync_snapshot", exc)

    def mark_result(
        self,
        snapshot_id: str,
        *,
        answered_correct: bool,
        retry_attempts: int,
        sent_to_anki: bool,
        apkg_generated: bool,
        apkg_path: str | None = None,
        error_type: str | None = None,
    ) -> None:
        if self.client is None or self._disabled or not snapshot_id:
            return
        payload = {
            "answered_correct": answered_correct,
            "retry_attempts": retry_attempts,
            "sent_to_anki": sent_to_anki,
            "apkg_generated": apkg_generated,
            "apkg_path": apkg_path,
            "final_error_type": error_type,
        }
        try:
            self.client.table("submitted_questions").update(payload).eq("id", snapshot_id).execute()
        except Exception as exc:
            self._handle_storage_error("mark_result", exc)

    def _snapshot_payload(self, session: SessionRecord, snapshot: QuestionSnapshot) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "telegram_id": session.telegram_id,
            "content": snapshot.content,
            "alternatives": serialize_alternatives(snapshot),
            "correct_alternative": snapshot.correct_alternative,
            "explanation": snapshot.explanation,
            "subject": snapshot.subject,
            "topic": snapshot.topic,
            "source_truth": snapshot.source_truth,
        }

    def _handle_storage_error(self, operation: str, exc: Exception) -> None:
        error_text = str(exc)
        missing_table = "submitted_questions" in error_text and ("schema cache" in error_text or "PGRST205" in error_text)
        if missing_table:
            self._disabled = True
            logger.warning(
                "submitted_questions repository disabled after %s because the table is not available yet: %s",
                operation,
                error_text,
            )
            return
        logger.warning("submitted_questions %s failed: %s", operation, error_text)
