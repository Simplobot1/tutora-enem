from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.domain.states import SessionFlow, SessionState

if TYPE_CHECKING:
    from app.domain.models import QuestionSnapshot


@dataclass(slots=True)
class QuestionRef:
    question_id: str | None = None
    snapshot_id: str | None = None
    bank_match_confidence: float | None = None


@dataclass(slots=True)
class ReviewCard:
    review_card_id: str | None = None
    front: str = ""
    back: str = ""


@dataclass(slots=True)
class AnkiMetadata:
    status: str | None = None
    builder_mode: str | None = None
    apkg_path: str | None = None


@dataclass(slots=True)
class SessionMetadata:
    flow: SessionFlow
    state: SessionState
    source_mode: str
    question_snapshot: "QuestionSnapshot | None" = None
    question_id: str | None = None
    question_ref: QuestionRef = field(default_factory=QuestionRef)
    review_card: ReviewCard = field(default_factory=ReviewCard)
    anki: AnkiMetadata = field(default_factory=AnkiMetadata)
    last_user_message: dict[str, Any] = field(default_factory=dict)
    llm_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow": self.flow.value,
            "state": self.state.value,
            "source_mode": self.source_mode,
            "question_snapshot": None if self.question_snapshot is None else {
                "source_mode": self.question_snapshot.source_mode,
                "source_truth": self.question_snapshot.source_truth,
                "content": self.question_snapshot.content,
                "correct_alternative": self.question_snapshot.correct_alternative,
                "explanation": self.question_snapshot.explanation,
                "subject": self.question_snapshot.subject,
                "topic": self.question_snapshot.topic,
                "alternatives": [
                    {"label": alt.label, "text": alt.text}
                    for alt in self.question_snapshot.alternatives
                ],
            },
            "chat_id": self.last_user_message.get("chat_id"),
            "question_id": self.question_id,
            "question_ref": {
                "question_id": self.question_ref.question_id,
                "snapshot_id": self.question_ref.snapshot_id,
                "bank_match_confidence": self.question_ref.bank_match_confidence,
            },
            "review_card": {
                "review_card_id": self.review_card.review_card_id,
                "front": self.review_card.front,
                "back": self.review_card.back,
            },
            "anki": {
                "status": self.anki.status,
                "builder_mode": self.anki.builder_mode,
                "apkg_path": self.anki.apkg_path,
            },
            "last_user_message": self.last_user_message,
            "llm_trace": self.llm_trace,
        }
