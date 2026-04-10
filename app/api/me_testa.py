from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, status
from pydantic import BaseModel, model_validator

from app.api.runtime import resolve_runtime_services
from app.domain.models import Attachment, InboundEvent


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
