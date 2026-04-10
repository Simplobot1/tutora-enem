#!/usr/bin/env python3
"""Build pending APKG files from queued sessions (M4-S1).

M4-S1: Reads sessions with anki_status = queued_local_build and generates .apkg files.

Fluxo:
  study_sessions.metadata.anki.status = queued_local_build
    -> busca review_card
    -> chama ApkgBuilderService para gerar .apkg
    -> atualiza metadata para built

Usage:
    python scripts/build_pending_apkgs.py [--limit 20] [--output-dir /path]
    python scripts/build_pending_apkgs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        print(f"[ERROR] Variável obrigatória ausente: {key}")
        sys.exit(1)
    return value


def _build_supabase():
    from supabase import create_client

    return create_client(_require_env("SUPABASE_URL"), _require_env("SUPABASE_SERVICE_ROLE_KEY"))


def _anki_metadata(metadata: dict) -> dict:
    anki = metadata.get("anki")
    return anki if isinstance(anki, dict) else {}


def _question_ref(metadata: dict) -> dict:
    question_ref = metadata.get("question_ref")
    return question_ref if isinstance(question_ref, dict) else {}


def _snapshot_id(metadata: dict) -> str:
    question_ref = _question_ref(metadata)
    return str(question_ref.get("snapshot_id") or "").strip()


def _review_card(metadata: dict) -> dict:
    review_card = metadata.get("review_card")
    return review_card if isinstance(review_card, dict) else {}


def _resolve_builder_mode(metadata: dict) -> str:
    anki = _anki_metadata(metadata)
    builder_mode = str(anki.get("builder_mode") or "").strip()
    if builder_mode in {"question_id", "review_card"}:
        return builder_mode
    question_id = _question_ref(metadata).get("question_id") or metadata.get("question_id")
    if question_id:
        return "question_id"
    review_card = _review_card(metadata)
    if review_card.get("front") and review_card.get("back"):
        return "review_card"
    return ""


def _is_queued(metadata: dict) -> bool:
    anki = _anki_metadata(metadata)
    return str(anki.get("status") or metadata.get("anki_status") or "").strip() == "queued_local_build"


def _is_eligible(metadata: dict) -> bool:
    mode = _resolve_builder_mode(metadata)
    if mode == "question_id":
        return bool(_question_ref(metadata).get("question_id") or metadata.get("question_id"))
    if mode == "review_card":
        review_card = _review_card(metadata)
        return bool(review_card.get("front") and review_card.get("back"))
    return False


def fetch_pending_sessions(sb, limit: int) -> list[dict]:
    result = (
        sb.table("study_sessions")
        .select("id,telegram_id,metadata")
        .execute()
    )
    rows = result.data or []
    pending = []
    for row in rows:
        metadata = row.get("metadata") or {}
        if not _is_queued(metadata):
            continue
        if not row.get("telegram_id"):
            continue
        if not _is_eligible(metadata):
            continue
        pending.append(row)
        if len(pending) >= limit:
            break
    return pending


def update_session(sb, session_id: str, metadata: dict) -> None:
    sb.table("study_sessions").update({"metadata": metadata}).eq("id", session_id).execute()


def update_submitted_question(sb, metadata: dict, *, sent_to_anki: bool, apkg_generated: bool, apkg_path: str | None) -> None:
    snapshot_id = _snapshot_id(metadata)
    if not snapshot_id:
        return
    payload = {
        "sent_to_anki": sent_to_anki,
        "apkg_generated": apkg_generated,
        "apkg_path": apkg_path,
    }
    sb.table("submitted_questions").update(payload).eq("id", snapshot_id).execute()


def run_builder(metadata: dict, telegram_id: int) -> dict:
    mode = _resolve_builder_mode(metadata)
    cmd = [
        "python3",
        "scripts/apkg_builder.py",
        "--telegram-id",
        str(telegram_id),
        "--out",
        f"materiais/flashcards/telegram_{telegram_id}",
        "--json",
    ]
    if mode == "question_id":
        question_id = _question_ref(metadata).get("question_id") or metadata.get("question_id")
        cmd.extend(["--question-id", str(question_id)])
    elif mode == "review_card":
        cmd.extend(
            [
                "--review-card-json",
                json.dumps(_review_card(metadata), ensure_ascii=True),
                "--no-db-update",
            ]
        )
    else:
        return {"ok": False, "error": "builder_mode_not_supported", "returncode": 1}
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    payload = None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if payload is None:
        payload = {
            "ok": False,
            "error": result.stderr.strip() or result.stdout.strip() or f"builder_exit_{result.returncode}",
        }
    payload["returncode"] = result.returncode
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera decks .apkg pendentes do bot")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de sessões pendentes por execução")
    args = parser.parse_args()

    sb = _build_supabase()
    pending = fetch_pending_sessions(sb, args.limit)
    if not pending:
        print("[INFO] Nenhuma sessão pendente de .apkg.")
        return 0

    for row in pending:
        session_id = row["id"]
        telegram_id = row["telegram_id"]
        metadata = row.get("metadata") or {}
        mode = _resolve_builder_mode(metadata)
        question_id = _question_ref(metadata).get("question_id") or metadata.get("question_id")
        review_card = _review_card(metadata)
        if mode == "question_id":
            print(f"[INFO] Gerando .apkg | session={session_id[:8]} question={str(question_id)[:8]} telegram={telegram_id}")
        else:
            review_card_id = review_card.get("review_card_id", "sem_id")
            print(f"[INFO] Gerando .apkg | session={session_id[:8]} review_card={str(review_card_id)[:12]} telegram={telegram_id}")
        payload = run_builder(metadata, telegram_id)
        updated = dict(metadata)
        updated_anki = dict(_anki_metadata(metadata))
        if payload.get("ok") and payload.get("apkg_path"):
            updated_anki.update(
                {
                    "builder_mode": mode or updated_anki.get("builder_mode") or "question_id",
                    "ready": True,
                    "status": "prepared",
                    "apkg_path": payload.get("apkg_path"),
                    "error": None,
                }
            )
            updated.update(
                {
                    "anki": updated_anki,
                    "anki_ready": True,
                    "anki_status": "prepared",
                    "apkg_path": payload.get("apkg_path"),
                    "anki_error": None,
                    "anki_card_id": payload.get("anki_card_id"),
                    "flashcard_id": payload.get("flashcard_id"),
                    "review_hint": "Deck .apkg preparado para importação manual no Anki.",
                }
            )
            print(f"[OK] Deck preparado: {payload.get('apkg_path')}")
            update_submitted_question(
                sb,
                updated,
                sent_to_anki=True,
                apkg_generated=True,
                apkg_path=payload.get("apkg_path"),
            )
        else:
            updated_anki.update(
                {
                    "builder_mode": mode or updated_anki.get("builder_mode") or "question_id",
                    "ready": False,
                    "status": "generation_failed",
                    "apkg_path": None,
                    "error": payload.get("error") or f"builder_exit_{payload.get('returncode')}",
                }
            )
            updated.update(
                {
                    "anki": updated_anki,
                    "anki_ready": False,
                    "anki_status": "generation_failed",
                    "apkg_path": None,
                    "review_hint": "Erro registrado para revisão, mas a geração local do deck .apkg falhou.",
                    "anki_error": payload.get("error") or f"builder_exit_{payload.get('returncode')}",
                }
            )
            print(f"[WARN] Falha ao gerar deck para session={session_id[:8]}")
            update_submitted_question(
                sb,
                updated,
                sent_to_anki=True,
                apkg_generated=False,
                apkg_path=None,
            )
        update_session(sb, session_id, updated)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
