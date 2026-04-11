from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.runtime import resolve_runtime_services
from app.clients.supabase import SupabaseClientFactory
from app.config import settings
from app.services.monthly_report_service import MonthlyReportService, format_report


router = APIRouter(prefix="/webhooks", tags=["telegram"])

_RELATORIO_COMMANDS = {"/relatorio", "/relatorio@"}


def _parse_relatorio_dias(text: str) -> int:
    """Extract --dias N from /relatorio command text, default 30."""
    parts = text.split()
    for i, part in enumerate(parts):
        if part == "--dias" and i + 1 < len(parts):
            try:
                return max(1, min(365, int(parts[i + 1])))
            except ValueError:
                pass
    return 30


@router.post("/telegram", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, object]:
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook secret")

    payload = await request.json()

    # Fast-path: /relatorio command
    message = payload.get("message") or {}
    text = (message.get("text") or "").strip()
    if text.startswith(tuple(_RELATORIO_COMMANDS)):
        chat_id: int = message.get("chat", {}).get("id", 0)
        telegram_id: int = message.get("from", {}).get("id", chat_id)
        dias = _parse_relatorio_dias(text)

        supabase_client = SupabaseClientFactory(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        ).create()
        report_service = MonthlyReportService(supabase_client)
        report = report_service.generate(telegram_id=telegram_id, dias=dias)
        report_text = format_report(report)

        services = resolve_runtime_services()
        await services.telegram_gateway.send_text(chat_id, report_text)
        return {"ok": True, "action": "relatorio_sent", "dias": dias}

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
