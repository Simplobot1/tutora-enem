from __future__ import annotations

from app.domain.session_metadata import QuestionRef, SessionMetadata
from app.domain.models import InboundEvent, ServiceResult
from app.domain.states import SessionFlow, SessionState
from app.repositories.questions_repository import QuestionsRepository
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService


class MeTestaEntryService:
    def __init__(
        self,
        session_service: SessionService,
        question_snapshot_service: QuestionSnapshotService,
        questions_repository: QuestionsRepository | None = None,
    ) -> None:
        self.session_service = session_service
        self.question_snapshot_service = question_snapshot_service
        self.questions_repository = questions_repository

    async def handle_question_intake(self, event: InboundEvent) -> ServiceResult:
        session = self.session_service.get_or_create_active_session(
            telegram_id=event.telegram_id,
            chat_id=event.chat_id,
            flow=SessionFlow.ME_TESTA,
        )
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")
        text = (event.text or event.caption).strip()
        snapshot = self.question_snapshot_service.build_from_text(text)

        if snapshot is None:
            session.source_mode = "student_submitted"
            session.question_id = None
            session.metadata.question_ref = QuestionRef()
            session.state = SessionState.WAITING_FALLBACK_DETAILS
            session.metadata.last_user_message = {"text": text, "message_id": event.message_id}
            self.session_service.save(session)
            return ServiceResult(
                state=session.state,
                reply_text="Ainda faltam dados para eu montar a questão. Me envie enunciado e alternativas A-E no mesmo texto.",
                metadata={
                    "flow": session.flow.value,
                    "session_id": session.session_id,
                    "source_mode": session.source_mode,
                    "question_id": session.question_id,
                },
            )

        match = None
        if self.questions_repository is not None:
            match = self.questions_repository.find_best_match(
                stem=snapshot.content,
                alternatives=[alt.text for alt in snapshot.alternatives],
            )

        session.question_snapshot = snapshot
        session.question_id = None
        session.metadata.question_ref = QuestionRef()
        if match is not None:
            snapshot.source_mode = "bank_match"
            snapshot.source_truth = "student_content_plus_bank_match"
            snapshot.correct_alternative = match.get("correct_alternative")
            snapshot.explanation = match.get("explanation") or ""
            snapshot.subject = match.get("subject") or snapshot.subject
            snapshot.topic = match.get("topic") or snapshot.topic
            session.source_mode = "bank_match"
            session.question_id = match.get("id")
            session.metadata.question_ref = QuestionRef(
                question_id=session.question_id,
                bank_match_confidence=match.get("match_confidence"),
            )
        else:
            snapshot.source_mode = "student_submitted"
            snapshot.source_truth = "student_content_only"
            session.source_mode = "student_submitted"

        session.state = SessionState.WAITING_ANSWER
        session.metadata.last_user_message = {"text": text, "message_id": event.message_id, "chat_id": event.chat_id}
        self.session_service.save(session)

        alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in snapshot.alternatives)
        reply = "\n".join(
            [
                "Consegui organizar a questão com o que você enviou.",
                "",
                snapshot.content,
                "",
                alternatives_text,
                "",
                "Agora me diga a alternativa que você marcou.",
            ]
        )
        return ServiceResult(
            state=session.state,
            reply_text=reply,
            metadata={
                "flow": session.flow.value,
                "session_id": session.session_id,
                "source_mode": session.source_mode,
                "question_id": session.question_id,
                "bank_match_confidence": session.metadata.question_ref.bank_match_confidence,
                "alternatives_count": len(snapshot.alternatives),
            },
        )
