from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.runtime import resolve_runtime_services
from app.clients.supabase import SupabaseClientFactory
from app.config import settings
from app.services.monthly_report_service import MonthlyReportService, format_report
from app.services.profile_service import ProfileService, format_profile


router = APIRouter(prefix="/webhooks", tags=["telegram"])

_RELATORIO_COMMANDS = {"/relatorio"}
_PERFIL_COMMANDS = {"/perfil"}
_ADMIN_COMMANDS = {"/admin"}
_SUPORTE_COMMANDS = {"/suporte"}
_SOBRE_COMMANDS = {"/sobre"}
_ME_TESTA_COMMANDS = {
    "/nova",
    "/novo",
    "/reset",
    "/start",
}


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


def _command_name(text: str) -> str:
    parts = text.split(maxsplit=1)
    if not parts:
        return ""
    command = parts[0].strip().lower()
    if "@" in command:
        command = command.split("@", 1)[0]
    return command


SUPORTE_TEXT = "Precisa de ajuda? Me chama por aqui: simplobot3@gmail.com"

SOBRE_TEXT = "\n".join(
    [
        "A Tutora ajuda você a estudar para o ENEM com questões, correção e revisão.",
        "",
        "O que ela faz:",
        "- Organiza questões enviadas por texto ou foto",
        "- Corrige sua resposta e explica o raciocínio",
        "- Comenta as alternativas para você entender o erro",
        "- Ajuda a revisar com perfil de estudos e relatório",
        "- Prepara revisões para o Anki quando faz sentido",
        "",
        "A ideia é estudar com clareza: entender por que errou, reforçar o que acertou e seguir para a próxima questão.",
    ]
)


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
    command = _command_name(text)
    if command in _RELATORIO_COMMANDS:
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

    # Fast-path: /perfil command
    if command in _PERFIL_COMMANDS:
        chat_id: int = message.get("chat", {}).get("id", 0)
        telegram_id: int = message.get("from", {}).get("id", chat_id)

        supabase_client = SupabaseClientFactory(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        ).create()
        profile_service = ProfileService(supabase_client)
        stats = profile_service.generate(telegram_id=telegram_id)
        profile_text = format_profile(stats)

        services = resolve_runtime_services()
        # Handle both single message and list of 2 messages
        if isinstance(profile_text, list):
            for msg in profile_text:
                await services.telegram_gateway.send_text(chat_id, msg)
        else:
            await services.telegram_gateway.send_text(chat_id, profile_text)
        return {"ok": True, "action": "perfil_sent"}

    # Fast-path: /admin command
    if command in _ADMIN_COMMANDS:
        chat_id: int = message.get("chat", {}).get("id", 0)
        services = resolve_runtime_services()
        await services.telegram_gateway.send_text(
            chat_id,
            "Admin ainda não está disponível por aqui.",
        )
        return {"ok": True, "action": "admin_unavailable"}

    if command in _SUPORTE_COMMANDS:
        chat_id: int = message.get("chat", {}).get("id", 0)
        services = resolve_runtime_services()
        await services.telegram_gateway.send_text(chat_id, SUPORTE_TEXT)
        return {"ok": True, "action": "suporte_sent"}

    if command in _SOBRE_COMMANDS:
        chat_id: int = message.get("chat", {}).get("id", 0)
        services = resolve_runtime_services()
        await services.telegram_gateway.send_text(chat_id, SOBRE_TEXT)
        return {"ok": True, "action": "sobre_sent"}

    if command.startswith("/") and command not in _ME_TESTA_COMMANDS:
        chat_id: int = message.get("chat", {}).get("id", 0)
        services = resolve_runtime_services()
        await services.telegram_gateway.send_text(
            chat_id,
            "Não reconheci esse comando. Para reiniciar a questão, use /nova.",
        )
        return {"ok": True, "action": "unknown_command", "command": command}

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
