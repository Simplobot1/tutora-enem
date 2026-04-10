#!/usr/bin/env python3
"""
apkg_builder.py — Gera flashcard Anki (.apkg) a partir de uma questão do Supabase.

Fluxo:
  question_id → busca questão no Supabase
             → monta card (frente = enunciado resumido, verso = gabarito + explicação)
             → gera .apkg via genanki
             → salva em materiais/flashcards/
             → atualiza anki_card_id na tabela flashcards (para o user_id fornecido)

  review_card → usa front/back finais já persistidos
              → gera .apkg sem consultar public.questions
              → salva em materiais/flashcards/

Uso:
  python scripts/apkg_builder.py --question-id <uuid> --user-id <uuid>
  python scripts/apkg_builder.py --question-id <uuid> --telegram-id <id-telegram>
  python scripts/apkg_builder.py --question-id <uuid> --telegram-id <id-telegram> --out materiais/flashcards/

Env vars necessárias (.env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  ANTHROPIC_API_KEY   (para gerar explicação quando ausente no banco)
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"[ERROR] Variável de ambiente obrigatória ausente: {key}")
        sys.exit(1)
    return val


def _build_supabase():
    from supabase import create_client
    return create_client(_require_env("SUPABASE_URL"), _require_env("SUPABASE_SERVICE_ROLE_KEY"))


def _build_anthropic():
    import anthropic
    return anthropic.Anthropic(api_key=_require_env("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# Supabase queries
# ---------------------------------------------------------------------------

def fetch_question(sb, question_id: str) -> dict:
    """Busca questão pelo UUID. Lança ValueError se não encontrada."""
    result = sb.table("questions").select("*").eq("id", question_id).execute()
    if not result.data:
        raise ValueError(f"Questão não encontrada: {question_id}")
    return result.data[0]


def upsert_flashcard(
    sb,
    *,
    user_id: Optional[str],
    telegram_id: Optional[int],
    question_id: str,
    front: str,
    back: str,
    anki_card_id: int,
) -> str:
    """
    Cria ou atualiza registro na tabela flashcards.
    Retorna o UUID do flashcard.
    """
    if not user_id and telegram_id is None:
        raise ValueError("Informe user_id ou telegram_id para persistir o flashcard.")

    query = sb.table("flashcards").select("id")
    if user_id:
        query = query.eq("user_id", user_id)
    else:
        query = query.eq("telegram_id", telegram_id)
    existing = query.eq("question_id", question_id).execute()

    if existing.data:
        flashcard_id = existing.data[0]["id"]
        sb.table("flashcards").update({
            "front": front,
            "back": back,
            "anki_card_id": anki_card_id,
        }).eq("id", flashcard_id).execute()
        return flashcard_id
    else:
        payload = {
            "question_id": question_id,
            "front": front,
            "back": back,
            "anki_card_id": anki_card_id,
        }
        if user_id:
            payload["user_id"] = user_id
        if telegram_id is not None:
            payload["telegram_id"] = telegram_id
        result = sb.table("flashcards").insert(payload).execute()
        return result.data[0]["id"]


def parse_review_card(raw: str) -> dict[str, Any]:
    try:
        review_card = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"review_card inválido: {exc}") from exc
    if not isinstance(review_card, dict):
        raise ValueError("review_card inválido: payload precisa ser um objeto JSON.")
    front = str(review_card.get("front") or "").strip()
    back = str(review_card.get("back") or "").strip()
    if not front or not back:
        raise ValueError("review_card inválido: campos front e back são obrigatórios.")
    return review_card


# ---------------------------------------------------------------------------
# Explanation generation (Claude)
# ---------------------------------------------------------------------------

def generate_explanation(anthropic_client, question: dict) -> str:
    """
    Pede ao Claude uma explicação pedagógica da questão.
    Usado quando o campo `explanation` está vazio no banco.
    """
    alts = question.get("alternatives", [])
    alt_text = "\n".join(f"  {a['label']}) {a['text']}" for a in alts)
    correct = question.get("correct_alternative", "?")

    prompt = (
        f"Você é uma tutora do ENEM chamada Aria. "
        f"Explique de forma clara e direta (máximo 3 parágrafos) "
        f"por que a alternativa {correct} é a correta nesta questão.\n\n"
        f"QUESTÃO:\n{question['content']}\n\n"
        f"ALTERNATIVAS:\n{alt_text}\n\n"
        f"GABARITO: {correct}\n\n"
        f"Explique o conceito envolvido e por que as outras alternativas estão erradas."
    )

    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


# ---------------------------------------------------------------------------
# Card content builders
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int = 300) -> str:
    """Trunca texto longo para a frente do card."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def build_front(question: dict) -> str:
    """
    Frente do card: enunciado resumido + alternativas.
    Formatado em HTML simples (Anki suporta HTML nos campos).
    """
    content = _truncate(question["content"], 400)
    alts = question.get("alternatives", [])
    alt_html = "".join(
        f"<li><b>{a['label']})</b> {a['text']}</li>"
        for a in alts
    )

    subject = question.get("subject", "")
    topic = question.get("topic", "")
    year = question.get("year", "")
    meta = " · ".join(filter(None, [str(year), subject, topic]))

    return (
        f"<div style='font-size:13px;color:#888;margin-bottom:8px'>{meta}</div>"
        f"<div style='font-size:15px'>{content}</div>"
        f"<br><ol type='A' style='font-size:14px'>{alt_html}</ol>"
    )


def build_back(question: dict, explanation: str) -> str:
    """
    Verso do card: gabarito + explicação.
    """
    correct = question.get("correct_alternative", "?")
    alts = question.get("alternatives", [])
    correct_text = next(
        (a["text"] for a in alts if a["label"] == correct),
        ""
    )
    return (
        f"<div style='font-size:18px;font-weight:bold;color:#2a7a2a'>"
        f"Gabarito: {correct}"
        f"</div>"
        f"<div style='font-size:14px;margin-top:4px'>{correct_text}</div>"
        f"<hr>"
        f"<div style='font-size:14px;margin-top:8px'>{explanation}</div>"
    )


def build_front_from_review_card(review_card: dict[str, Any]) -> str:
    return str(review_card.get("front") or "").strip()


def build_back_from_review_card(review_card: dict[str, Any]) -> str:
    return str(review_card.get("back") or "").strip()


# ---------------------------------------------------------------------------
# .apkg generation via genanki
# ---------------------------------------------------------------------------

def _stable_int_id(seed: str) -> int:
    """Gera um ID inteiro estável (positivo, < 2^31) a partir de uma string."""
    return int(hashlib.md5(seed.encode()).hexdigest(), 16) % (2**31)


def generate_apkg(card_key: str, front_html: str, back_html: str, out_dir: Path) -> tuple[Path, int]:
    """
    Cria o arquivo .apkg e retorna (caminho, anki_card_id).

    O deck_id e model_id são derivados de seeds fixas para que re-execuções
    gerem IDs consistentes (Anki detecta duplicatas por note ID).
    """
    import genanki

    deck_id = _stable_int_id("tutora-enem-deck-v1")
    model_id = _stable_int_id("tutora-enem-model-v1")
    note_id = _stable_int_id(f"note-{card_key}")

    model = genanki.Model(
        model_id,
        "Tutora ENEM",
        fields=[
            {"name": "Frente"},
            {"name": "Verso"},
        ],
        templates=[{
            "name": "Card 1",
            "qfmt": "{{Frente}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Verso}}',
        }],
        css=(
            ".card { font-family: 'Helvetica Neue', sans-serif; "
            "font-size: 15px; text-align: left; color: #222; "
            "background: #fff; padding: 16px; max-width: 600px; margin: auto; }"
        ),
    )

    note = genanki.Note(
        model=model,
        fields=[front_html, back_html],
        guid=genanki.guid_for(str(note_id)),
    )

    deck = genanki.Deck(deck_id, "Tutora ENEM")
    deck.add_note(note)

    out_dir.mkdir(parents=True, exist_ok=True)
    safe_key = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in card_key)[:32]
    apkg_path = out_dir / f"enem_{safe_key[:8]}.apkg"

    package = genanki.Package(deck)
    package.write_to_file(str(apkg_path))

    return apkg_path, note_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera flashcard .apkg a partir de uma questão do Supabase ou de um review_card final"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--question-id", help="UUID da questão no Supabase")
    source.add_argument(
        "--review-card-json",
        help="Payload JSON final do review_card com review_card_id/front/back",
    )
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument(
        "--user-id",
        help="UUID do usuário em public.users (para atualizar tabela flashcards)",
    )
    identity.add_argument(
        "--telegram-id",
        type=int,
        help="Telegram ID da aluna (para atualizar tabela flashcards do bot)",
    )
    parser.add_argument(
        "--out", default="materiais/flashcards",
        help="Diretório de saída para o .apkg (padrão: materiais/flashcards/)",
    )
    parser.add_argument(
        "--no-db-update", action="store_true",
        help="Não atualiza tabela flashcards no Supabase",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Imprime um resumo final em JSON para automação",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    question_id: Optional[str] = None
    review_card_id: Optional[str] = None
    flashcard_id: Optional[str] = None
    sb = None

    if args.question_id:
        # Clients
        sb = _build_supabase()
        anthropic_client = _build_anthropic()

        # Busca questão
        print(f"[INFO] Buscando questão: {args.question_id}")
        try:
            question = fetch_question(sb, args.question_id)
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            sys.exit(1)

        subject = question.get("subject", "")
        topic = question.get("topic", "")
        year = question.get("year", "")
        num = question.get("number", "?")
        print(f"[INFO] Questão {num} | {year} | {subject} — {topic}")

        explanation = (question.get("explanation") or "").strip()
        if not explanation:
            print("[INFO] Sem explicação no banco — gerando com Claude...")
            try:
                explanation = generate_explanation(anthropic_client, question)
            except Exception as exc:
                print(f"[WARN] Geração de explicação falhou: {exc}")
                explanation = "Consulte o gabarito oficial para a explicação completa."

        front = build_front(question)
        back = build_back(question, explanation)
        question_id = args.question_id
        card_key = args.question_id
    else:
        try:
            review_card = parse_review_card(args.review_card_json)
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            sys.exit(1)
        review_card_id = str(review_card.get("review_card_id") or "").strip() or f"review_card_{_stable_int_id(json.dumps(review_card, sort_keys=True, ensure_ascii=True))}"
        print(f"[INFO] Gerando concept card final: {review_card_id}")
        front = build_front_from_review_card(review_card)
        back = build_back_from_review_card(review_card)
        card_key = review_card_id

    print(f"[INFO] Gerando .apkg em: {out_dir}/")
    apkg_path, anki_card_id = generate_apkg(card_key, front, back, out_dir)
    print(f"[OK] Arquivo gerado: {apkg_path}")

    if args.question_id and not args.no_db_update:
        owner_label = f"user={args.user_id[:8]}..." if args.user_id else f"telegram_id={args.telegram_id}"
        print(f"[INFO] Atualizando tabela flashcards ({owner_label})...")
        try:
            flashcard_id = upsert_flashcard(
                sb,
                user_id=args.user_id,
                telegram_id=args.telegram_id,
                question_id=args.question_id,
                front=front,
                back=back,
                anki_card_id=anki_card_id,
            )
            print(f"[OK] Flashcard salvo: {flashcard_id}")
        except Exception as exc:
            print(f"[WARN] Falha ao atualizar Supabase: {exc}")
            print(f"       .apkg ainda foi salvo em: {apkg_path}")
    elif args.review_card_json and not args.no_db_update:
        print("[WARN] review_card mode não atualiza a tabela flashcards automaticamente; use o metadata da sessão como fonte de rastreabilidade.")

    print(f"\n[DONE] {apkg_path.name} pronto para importar no Anki.")
    if args.json:
        print(json.dumps({
            "ok": True,
            "question_id": question_id,
            "review_card_id": review_card_id,
            "user_id": args.user_id,
            "telegram_id": args.telegram_id,
            "apkg_path": str(apkg_path),
            "anki_card_id": anki_card_id,
            "flashcard_id": flashcard_id,
        }, ensure_ascii=True))


if __name__ == "__main__":
    main()
