from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, model_validator

from app.api.runtime import resolve_runtime_services
from app.domain.models import Attachment, InboundEvent
from app.domain.states import SessionFlow, SessionState


router = APIRouter(prefix="/me-testa", tags=["me_testa"])


class MeTestaIntakeRequest(BaseModel):
    telegram_id: int
    chat_id: int
    text: str = ""
    message_id: int | None = None
    update_id: int | None = None
    caption: str = ""
    input_mode: str = "text"

    @model_validator(mode="after")
    def validate_content(self) -> "MeTestaIntakeRequest":
        if not (self.text or self.caption).strip():
            raise ValueError("either text or caption must be provided")
        return self


class MeTestaAnswerRequest(BaseModel):
    telegram_id: int
    chat_id: int
    answer: str
    message_id: int | None = None
    update_id: int | None = None

    @model_validator(mode="after")
    def validate_answer(self) -> "MeTestaAnswerRequest":
        if not self.answer.strip():
            raise ValueError("answer must be provided")
        return self


@router.post("/intake", status_code=status.HTTP_200_OK)
async def me_testa_intake(payload: MeTestaIntakeRequest) -> dict[str, object]:
    services = resolve_runtime_services()
    event = InboundEvent(
        update_id=payload.update_id,
        telegram_id=payload.telegram_id,
        chat_id=payload.chat_id,
        message_id=payload.message_id,
        input_mode=payload.input_mode,
        text=payload.text,
        caption=payload.caption,
        attachment=Attachment(),
        raw_payload=payload.model_dump(),
    )
    result = await services.entry_service.handle_question_intake(event)
    return {
        "ok": True,
        "event": asdict(event),
        "result": asdict(result),
    }


@router.post("/answer", status_code=status.HTTP_200_OK)
async def me_testa_answer(payload: MeTestaAnswerRequest) -> dict[str, object]:
    services = resolve_runtime_services()
    answer_service = getattr(services.me_testa_service, "answer_service", None)
    if answer_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Me-testa answer service is not configured.",
        )
    session = services.session_service.repository.get_active_session(
        payload.telegram_id,
        SessionFlow.ME_TESTA,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active me-testa session found for this telegram_id.",
        )

    answer_text = payload.answer.strip()
    if session.state == SessionState.WAITING_GABARITO:
        result = await answer_service.process_gabarito(
            session=session,
            gabarito_input=answer_text,
        )
    else:
        result = await answer_service.process_answer(
            telegram_id=payload.telegram_id,
            student_answer=answer_text,
            session=session,
        )

    event = InboundEvent(
        update_id=payload.update_id,
        telegram_id=payload.telegram_id,
        chat_id=payload.chat_id,
        message_id=payload.message_id,
        input_mode="text",
        text=answer_text,
        attachment=Attachment(),
        raw_payload=payload.model_dump(),
    )
    return {
        "ok": True,
        "event": asdict(event),
        "result": asdict(result),
    }
