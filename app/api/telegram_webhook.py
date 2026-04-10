from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.runtime import resolve_runtime_services
from app.config import settings


router = APIRouter(prefix="/webhooks", tags=["telegram"])


@router.post("/telegram", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, object]:
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook secret")

    payload = await request.json()
    services = resolve_runtime_services()
    intake_service = services.intake_service
    me_testa_service = services.me_testa_service
    inbound_event = intake_service.normalize_update(payload)
    result = await me_testa_service.handle_event(inbound_event)
    return {
        "ok": True,
        "event": asdict(inbound_event),
        "result": asdict(result),
    }
