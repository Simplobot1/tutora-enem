from __future__ import annotations

from typing import Any

from app.domain.session_metadata import QuestionRef, SessionMetadata
from app.domain.models import InboundEvent, QuestionAlternative, QuestionSnapshot, ServiceResult
from app.domain.states import SessionFlow, SessionState
from app.repositories.questions_repository import QuestionsRepository
from app.repositories.submitted_questions_repository import SubmittedQuestionsRepository
from app.services.ocr_cache import OcrCache
from app.services.ocr_service import OcrService
from app.services.question_curator_service import QuestionCuratorService
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService


class MeTestaEntryService:
    def __init__(
        self,
        session_service: SessionService,
        question_snapshot_service: QuestionSnapshotService,
        questions_repository: QuestionsRepository | None = None,
        question_curator_service: QuestionCuratorService | None = None,
        submitted_questions_repository: SubmittedQuestionsRepository | None = None,
        ocr_service: OcrService | None = None,
        ocr_cache: OcrCache | None = None,
    ) -> None:
        self.session_service = session_service
        self.question_snapshot_service = question_snapshot_service
        self.questions_repository = questions_repository
        self.question_curator_service = question_curator_service or QuestionCuratorService()
        self.submitted_questions_repository = submitted_questions_repository
        self.ocr_service = ocr_service
        self.ocr_cache = ocr_cache or OcrCache()

    async def handle_question_intake(self, event: InboundEvent) -> ServiceResult:
        session = self.session_service.get_or_create_active_session(
            telegram_id=event.telegram_id,
            chat_id=event.chat_id,
            flow=SessionFlow.ME_TESTA,
        )
        if not isinstance(session.metadata, SessionMetadata):
            raise TypeError("session.metadata must be SessionMetadata")

        # Handle image mode: extract question via OCR
        if event.input_mode == "image" and self.ocr_service is not None:
            return await self._handle_image_intake(event, session)

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
                reply_text=(
                    "Ainda não consegui montar a questão inteira com o que chegou aqui.\n\n"
                    "Me manda no mesmo texto o enunciado e as alternativas A-E que eu organizo com você."
                ),
                metadata={
                    "flow": session.flow.value,
                    "session_id": session.session_id,
                    "source_mode": session.source_mode,
                    "question_id": session.question_id,
                },
            )

        return await self._process_snapshot(event, session, snapshot)

    async def _handle_image_intake(self, event: InboundEvent, session: Any) -> ServiceResult:
        """
        Handle image input mode: extract question via OCR using Claude Vision.

        Returns ServiceResult with error message if OCR fails, or continues to normal flow.
        """
        file_id = event.attachment.file_id
        if not file_id:
            return ServiceResult(
                state=session.state,
                reply_text="Não consegui processar a imagem. Tira outra ou manda o texto?",
            )

        # Check cache first
        cached_result = self.ocr_cache.get(file_id)
        if cached_result is not None:
            snapshot = self._build_snapshot_from_ocr(cached_result)
            return await self._process_snapshot(event, session, snapshot)

        # Call OCR service
        ocr_result = await self.ocr_service.extract_question(file_id)
        if ocr_result is None:
            # AC7: Friendly error message, no persistence
            return ServiceResult(
                state=session.state,
                reply_text="Não consegui ler a foto. Tira outra ou manda o texto?",
            )

        # Cache the result
        self.ocr_cache.set(file_id, ocr_result)

        # Build snapshot from OCR result
        snapshot = self._build_snapshot_from_ocr(ocr_result)

        # Continue with normal flow, but store OCR metadata
        return await self._process_snapshot(event, session, snapshot, ocr_result=ocr_result)

    def _build_snapshot_from_ocr(self, ocr_result: Any) -> QuestionSnapshot:
        """Build QuestionSnapshot from OCR result."""
        return QuestionSnapshot(
            source_mode="ocr_photo",
            source_truth="ocr_vision",
            content=ocr_result.content,
            alternatives=ocr_result.alternatives,
            correct_alternative=None,  # OCR doesn't know the correct answer
        )

    async def _process_snapshot(
        self,
        event: InboundEvent,
        session: Any,
        snapshot: QuestionSnapshot,
        ocr_result: Any | None = None,
    ) -> ServiceResult:
        """
        Process question snapshot (common logic for text and OCR).
        Continues with bank_match → student_submitted flow.
        """
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
            snapshot.alternatives = self._merge_bank_alternatives(snapshot.alternatives, match.get("alternatives") or [])
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
            snapshot = self.question_curator_service.enrich(snapshot)
            if self.submitted_questions_repository is not None:
                snapshot_id = self.submitted_questions_repository.create_from_snapshot(
                    session,
                    snapshot,
                    source="ocr_photo" if ocr_result else "text",
                    ocr_raw_text=ocr_result.ocr_raw_text if ocr_result else None,
                    ocr_confidence=ocr_result.ocr_confidence if ocr_result else None,
                )
                session.metadata.question_ref.snapshot_id = snapshot_id

        # OCR without bank match must get gabarito FIRST (has no correct_alternative)
        if ocr_result is not None and match is None:
            session.state = SessionState.WAITING_GABARITO
            session.metadata.question_ref = QuestionRef()
            text_for_log = event.text or event.caption or "(image)"
            session.metadata.last_user_message = {"text": text_for_log, "message_id": event.message_id}
            self.session_service.save(session)

            alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in snapshot.alternatives)
            reply = "\n".join(
                [
                    "Boa, organizei a questão com a foto que você mandou.",
                    "",
                    snapshot.content,
                    "",
                    alternatives_text,
                    "",
                    "Qual é o gabarito dessa questão? (me manda no formato `gabarito: A`)",
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
                },
            )

        session.state = session.state.__class__.WAITING_ANSWER
        text_for_log = event.text or event.caption or "(image)"
        session.metadata.last_user_message = {"text": text_for_log, "message_id": event.message_id, "chat_id": event.chat_id}
        self.session_service.save(session)

        alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in snapshot.alternatives)
        reply = "\n".join(
            [
                "Boa, organizei a questão com o que você me mandou.",
                "",
                snapshot.content,
                "",
                alternatives_text,
                "",
                "Agora me conta qual alternativa você marcou.",
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

    def _merge_bank_alternatives(
        self,
        submitted_alternatives: list[QuestionAlternative],
        bank_alternatives: list[dict[str, Any]],
    ) -> list[QuestionAlternative]:
        if not bank_alternatives:
            return submitted_alternatives

        submitted_by_label = {alternative.label: alternative for alternative in submitted_alternatives}
        merged: list[QuestionAlternative] = []
        for item in bank_alternatives:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip().upper()
            if not label:
                continue
            fallback = submitted_by_label.get(label)
            text = str(item.get("text") or (fallback.text if fallback is not None else "")).strip()
            explanation = str(
                item.get("explanation")
                or item.get("rationale")
                or item.get("why_wrong")
                or item.get("feedback")
                or ""
            ).strip()
            if text:
                merged.append(QuestionAlternative(label=label, text=text, explanation=explanation))

        return merged if len(merged) >= 4 else submitted_alternatives
