from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.session_metadata import AnkiMetadata, QuestionRef, ReviewCard, SessionMetadata
from app.domain.states import SessionFlow, SessionState


@dataclass(slots=True)
class Attachment:
    file_id: str = ""
    mime_type: str = ""
    file_name: str = ""


@dataclass(slots=True)
class InboundEvent:
    update_id: int | None
    telegram_id: int
    chat_id: int
    message_id: int | None
    input_mode: str
    text: str = ""
    caption: str = ""
    callback_data: str = ""
    attachment: Attachment = field(default_factory=Attachment)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QuestionAlternative:
    label: str
    text: str


@dataclass(slots=True)
class QuestionSnapshot:
    source_mode: str
    source_truth: str
    content: str
    alternatives: list[QuestionAlternative] = field(default_factory=list)
    correct_alternative: str | None = None
    explanation: str = ""
    subject: str = ""
    topic: str = ""


@dataclass(slots=True)
class SessionRecord:
    session_id: str | None
    telegram_id: int
    chat_id: int
    flow: SessionFlow
    state: SessionState
    mood: str | None = None
    source_mode: str = "student_content_only"
    question_snapshot: QuestionSnapshot | None = None
    question_id: str | None = None
    metadata: SessionMetadata | dict[str, Any] = field(default_factory=dict)
    pessimistic_lock_id: str | None = None
    lock_timestamp: str | None = None

    @classmethod
    def from_persisted_row(cls, row: dict[str, Any]) -> "SessionRecord":
        metadata = row.get("metadata") or {}
        flow = SessionFlow(metadata.get("flow", SessionFlow.ME_TESTA.value))
        state = SessionState(metadata.get("state", SessionState.IDLE.value))
        snapshot_data = metadata.get("question_snapshot") or None
        snapshot = None
        if snapshot_data:
            snapshot = QuestionSnapshot(
                source_mode=snapshot_data.get("source_mode", "student_submitted"),
                source_truth=snapshot_data.get("source_truth", "student_content_only"),
                content=snapshot_data.get("content", ""),
                alternatives=[
                    QuestionAlternative(label=alt.get("label", ""), text=alt.get("text", ""))
                    for alt in snapshot_data.get("alternatives", [])
                ],
                correct_alternative=snapshot_data.get("correct_alternative"),
                explanation=snapshot_data.get("explanation", ""),
                subject=snapshot_data.get("subject", ""),
                topic=snapshot_data.get("topic", ""),
            )
        metadata_obj = SessionMetadata(
            flow=flow,
            state=state,
            source_mode=metadata.get("source_mode", "student_content_only"),
            question_snapshot=snapshot,
            question_id=metadata.get("question_id"),
            question_ref=QuestionRef(
                question_id=(metadata.get("question_ref") or {}).get("question_id"),
                snapshot_id=(metadata.get("question_ref") or {}).get("snapshot_id"),
                bank_match_confidence=(metadata.get("question_ref") or {}).get("bank_match_confidence"),
            ),
            review_card=ReviewCard(
                review_card_id=(metadata.get("review_card") or {}).get("review_card_id"),
                front=(metadata.get("review_card") or {}).get("front", ""),
                back=(metadata.get("review_card") or {}).get("back", ""),
            ),
            anki=AnkiMetadata(
                status=(metadata.get("anki") or {}).get("status"),
            ),
        )
        return cls(
            session_id=row.get("id"),
            telegram_id=row.get("telegram_id"),
            chat_id=metadata.get("chat_id", row.get("chat_id")),
            flow=flow,
            state=state,
            mood=row.get("mood"),
            source_mode=metadata.get("source_mode", "student_content_only"),
            question_snapshot=snapshot,
            question_id=metadata.get("question_id"),
            metadata=metadata_obj,
            pessimistic_lock_id=metadata.get("pessimistic_lock_id"),
            lock_timestamp=metadata.get("lock_timestamp"),
        )


@dataclass(slots=True)
class ServiceResult:
    state: SessionState
    reply_text: str
    should_reply: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
