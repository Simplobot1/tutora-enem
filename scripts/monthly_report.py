#!/usr/bin/env python3
"""
Script standalone para gerar e enviar relatório mensal de progresso.

Uso:
    python scripts/monthly_report.py --telegram-id <ID> [--dias 30]

Variáveis de ambiente necessárias:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    TELEGRAM_BOT_TOKEN          (opcional — sem token, imprime o relatório no stdout)
    MONTHLY_GOAL_QUESTIONS      (opcional — padrão 100)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Garante que o root do projeto está no path quando executado diretamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.clients.supabase import SupabaseClientFactory
from app.services.monthly_report_service import MonthlyReportService, format_report


def build_report(telegram_id: int, dias: int) -> str:
    client = SupabaseClientFactory(
        url=os.getenv("SUPABASE_URL", ""),
        service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    ).create()
    service = MonthlyReportService(client)
    report = service.generate(telegram_id=telegram_id, dias=dias)
    return format_report(report)


async def send_via_telegram(chat_id: int, text: str) -> None:
    import httpx

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(text)
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        if response.is_error:
            print(f"Erro ao enviar Telegram: {response.text}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera relatório mensal Tutora ENEM")
    parser.add_argument("--telegram-id", type=int, required=True, help="telegram_id da aluna")
    parser.add_argument("--dias", type=int, default=30, help="Janela de dias (padrão: 30)")
    args = parser.parse_args()

    report_text = build_report(telegram_id=args.telegram_id, dias=args.dias)
    asyncio.run(send_via_telegram(chat_id=args.telegram_id, text=report_text))


if __name__ == "__main__":
    main()
