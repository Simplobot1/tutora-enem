#!/usr/bin/env python3
"""
ingest_enem.py — Ingere questões de provas ENEM (PDF) no Supabase.

Fluxo:
  PDF → pymupdf (extrai texto por página)
      → Claude Vision (descreve imagens em páginas com figuras/gráficos)
      → parse questão + alternativas (regex)
      → INSERT em materials + questions (Supabase via service_role)

Uso:
  python scripts/ingest_enem.py --file materiais/provas/enem2024.pdf
  python scripts/ingest_enem.py --file ... --year 2024 --gabarito materiais/gabaritos/2024.csv
  python scripts/ingest_enem.py --file ... --use-vision --dry-run

Gabarito CSV (sem cabeçalho):
  1,C
  2,A
  ...

Env vars necessárias (.env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  ANTHROPIC_API_KEY
"""

import argparse
import base64
import csv
import os
import re
import sys
from pathlib import Path
from typing import Optional

import fitz  # pymupdf
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers: env + clients
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
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pages(pdf_path: str) -> list[dict]:
    """
    Retorna lista de {page_num, text, has_images, _page_obj}.
    Não renderiza imagens aqui — só quando necessário.
    """
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        images = page.get_images(full=True)
        pages.append({
            "page_num": i + 1,
            "text": page.get_text("text"),
            "has_images": len(images) > 0,
            "_page_obj": page,
        })
    return pages


def render_page_png(page_obj) -> bytes:
    """Renderiza página como PNG em alta resolução (2×zoom)."""
    mat = fitz.Matrix(2.0, 2.0)
    pix = page_obj.get_pixmap(matrix=mat)
    return pix.tobytes("png")


# ---------------------------------------------------------------------------
# Claude Vision
# ---------------------------------------------------------------------------

def describe_with_vision(anthropic_client, png_bytes: bytes, page_num: int) -> str:
    """Envia página como imagem para Claude Vision e retorna descrição textual."""
    b64 = base64.standard_b64encode(png_bytes).decode()
    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        f"Esta é a página {page_num} de uma prova do ENEM. "
                        "Descreva com precisão todo conteúdo visual: gráficos, tabelas, "
                        "figuras, fórmulas e imagens. Transcreva texto visível não extraído "
                        "pelo parser. Seja detalhado para que um estudante entenda o contexto."
                    ),
                },
            ],
        }],
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Question parser
# ---------------------------------------------------------------------------

# Padrão de início de questão — suporta dois formatos:
#   "Questão 1" / "QUESTÃO 1"  (ENEM oficial)
#   "01."  (provas estaduais/vestibulares — número de 1 ou 2 dígitos seguido de ponto)
_Q_START = re.compile(
    r"(?:(?:Questão|QUESTÃO|Quest[ãa]o)\s+(\d+)|\n(\d{1,2})\.(?=\s+\S))",
    re.IGNORECASE,
)

# Alternativas: A) ... B) ... C) ... D) ... E) ...
_ALT = re.compile(
    r"\n([A-E])\)\s+(.+?)(?=\n[A-E]\)|\Z)",
    re.DOTALL,
)


def parse_questions_from_text(text: str) -> list[dict]:
    """
    Extrai lista de questões do texto completo do PDF.
    Cada item: {number, content, alternatives: [{label, text}]}

    Suporta dois formatos de marcador:
      - "Questão N" / "QUESTÃO N"  → 1 grupo de captura
      - "01."                      → 2 grupos de captura (g1=None, g2=número)
    O regex tem 2 grupos, então split() produz 3 tokens por match:
      [pre_text, g1_or_None, g2_or_None, body, ...]
    """
    text = re.sub(r"\r\n?", "\n", text)

    tokens = _Q_START.split(text)
    # stride = 3  (pré-texto + 2 grupos + corpo = 4 por ciclo, mas o pré-texto
    # fica no índice 0 e depois alterna: g1, g2, corpo)

    questions = []
    i = 1  # pula pré-texto inicial
    while i < len(tokens) - 2:
        g1 = tokens[i]      # grupo "Questão N"
        g2 = tokens[i + 1]  # grupo "01."
        body = tokens[i + 2]

        raw_num = g1 if g1 is not None else g2
        if raw_num is None:
            i += 3
            continue
        try:
            num = int(raw_num)
        except ValueError:
            i += 3
            continue

        q = _parse_body(num, body)
        if q:
            questions.append(q)
        i += 3

    return questions


def _parse_body(number: int, body: str) -> Optional[dict]:
    """Converte o corpo de uma questão em estrutura {number, content, alternatives}."""
    alts = _ALT.findall(body)
    if len(alts) < 4:
        # Questão incompleta / sem alternativas reconhecíveis — pula
        return None

    # Conteúdo = tudo antes da primeira alternativa
    first = _ALT.search(body)
    content = body[: first.start()].strip() if first else body.strip()
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if not content:
        return None

    alternatives = [
        {"label": lbl, "text": txt.strip()}
        for lbl, txt in alts[:5]
    ]

    return {"number": number, "content": content, "alternatives": alternatives}


# ---------------------------------------------------------------------------
# Subject inference (caderno padrão ENEM)
# ---------------------------------------------------------------------------

_SUBJECT_RANGES = [
    (1,   45,  "Linguagens e Códigos",    "Linguagens"),
    (46,  90,  "Ciências Humanas",        "Ciências Humanas"),
    (91,  135, "Ciências da Natureza",    "Ciências da Natureza"),
    (136, 180, "Matemática",             "Matemática"),
]


def infer_subject(number: int, override: Optional[str] = None) -> tuple[str, str]:
    if override:
        return override, override
    for start, end, subject, topic in _SUBJECT_RANGES:
        if start <= number <= end:
            return subject, topic
    return "Desconhecido", ""


# ---------------------------------------------------------------------------
# Gabarito (CSV)
# ---------------------------------------------------------------------------

def load_gabarito(path: str) -> dict[int, str]:
    """Lê CSV sem cabeçalho: número,resposta (ex: 1,C)."""
    gabarito: dict[int, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    gabarito[int(row[0].strip())] = row[1].strip().upper()
                except ValueError:
                    pass
    return gabarito


# ---------------------------------------------------------------------------
# Supabase inserts
# ---------------------------------------------------------------------------

def insert_material(sb, title: str, pdf_path: str, year: int) -> str:
    result = sb.table("materials").insert({
        "title": title,
        "type": "pdf",
        "metadata": {
            "year": year,
            "source": "ENEM",
            "filename": Path(pdf_path).name,
        },
    }).execute()
    return result.data[0]["id"]


def upsert_material(sb, title: str, pdf_path: str, year: int) -> tuple[str, bool]:
    payload = {
        "title": title,
        "type": "pdf",
        "metadata": {
            "year": year,
            "source": "ENEM",
            "filename": Path(pdf_path).name,
        },
    }
    existing = sb.table("materials").select("id").eq("title", title).limit(1).execute()
    if existing.data:
        material_id = existing.data[0]["id"]
        sb.table("materials").update(payload).eq("id", material_id).execute()
        return material_id, False
    return insert_material(sb, title, pdf_path, year), True


def insert_question(sb, record: dict) -> str:
    result = sb.table("questions").insert(record).execute()
    return result.data[0]["id"]


def upsert_question(sb, record: dict) -> tuple[str, bool]:
    query = sb.table("questions").select("id")
    material_id = record.get("material_id")
    if material_id:
        query = query.eq("material_id", material_id).eq("number", record["number"])
    else:
        query = query.eq("year", record["year"]).eq("number", record["number"]).eq("source", record["source"])
    existing = query.limit(1).execute()
    if existing.data:
        question_id = existing.data[0]["id"]
        sb.table("questions").update(record).eq("id", question_id).execute()
        return question_id, False
    return insert_question(sb, record), True


def deduplicate_questions(questions: list[dict]) -> list[dict]:
    """Mantém a melhor versão de cada número de questão dentro do parse atual."""
    best_by_number: dict[int, dict] = {}
    order: list[int] = []

    def score(question: dict) -> tuple[int, int]:
        return (
            len(question.get("alternatives", [])),
            len(question.get("content", "")),
        )

    for question in questions:
        number = question["number"]
        if number not in best_by_number:
            best_by_number[number] = question
            order.append(number)
            continue
        if score(question) > score(best_by_number[number]):
            best_by_number[number] = question

    return [best_by_number[number] for number in order]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingere questões de prova ENEM (PDF) no Supabase"
    )
    parser.add_argument("--file", required=True, help="Caminho para o PDF da prova")
    parser.add_argument("--year", type=int, default=2024, help="Ano do ENEM (padrão: 2024)")
    parser.add_argument("--subject", default=None, help="Forçar matéria (ex: 'Matemática')")
    parser.add_argument(
        "--gabarito", default=None,
        help="CSV com gabarito (formato: número,resposta). "
             "Sem gabarito = correct_alternative='X' (placeholder).",
    )
    parser.add_argument(
        "--use-vision", action="store_true",
        help="Envia páginas com imagens para Claude Vision (mais lento, mais preciso)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Não insere no banco; apenas imprime o que seria inserido",
    )
    args = parser.parse_args()

    pdf_path = args.file
    if not Path(pdf_path).exists():
        print(f"[ERROR] Arquivo não encontrado: {pdf_path}")
        sys.exit(1)

    # Clients
    sb = None if args.dry_run else _build_supabase()
    anthropic_client = _build_anthropic() if args.use_vision else None

    # Gabarito
    gabarito: dict[int, str] = {}
    if args.gabarito:
        gabarito = load_gabarito(args.gabarito)
        print(f"[INFO] Gabarito: {len(gabarito)} respostas carregadas")

    # Extração do PDF
    print(f"[INFO] Lendo PDF: {pdf_path}")
    pages = extract_pages(pdf_path)
    print(f"[INFO] Total de páginas: {len(pages)}")

    # Agrega texto (com Vision se solicitado)
    text_parts: list[str] = []
    for page in pages:
        page_text = page["text"]
        if args.use_vision and page["has_images"] and anthropic_client:
            print(f"  [Vision] Página {page['page_num']} tem imagens — consultando Claude...")
            png = render_page_png(page["_page_obj"])
            desc = describe_with_vision(anthropic_client, png, page["page_num"])
            page_text = f"{page_text}\n[DESCRIÇÃO VISUAL — página {page['page_num']}:\n{desc}\n]"
        text_parts.append(page_text)

    full_text = "\n".join(text_parts)

    # Parse das questões
    questions = parse_questions_from_text(full_text)
    print(f"[INFO] Questões identificadas: {len(questions)}")
    deduped_questions = deduplicate_questions(questions)
    if len(deduped_questions) != len(questions):
        print(f"[INFO] Questões deduplicadas no parse: {len(questions)} -> {len(deduped_questions)}")
    questions = deduped_questions

    if not questions:
        print(
            "[WARN] Nenhuma questão extraída. "
            "Verifique se o PDF usa o padrão 'Questão N'. "
            "Tente com --use-vision para PDFs baseados em imagem."
        )
        sys.exit(1)

    # Insere material no Supabase
    title = f"ENEM {args.year} — {Path(pdf_path).stem}"
    material_id: Optional[str] = None
    if not args.dry_run:
        material_id, created_material = upsert_material(sb, title, pdf_path, args.year)
        print(f"[INFO] Material {'criado' if created_material else 'reutilizado'}: {material_id}")

    # Processa e insere questões
    inserted = 0
    updated = 0
    skipped = 0

    for q in questions:
        num = q["number"]
        subject, topic = infer_subject(num, args.subject)
        correct = gabarito.get(num, "X")  # 'X' = placeholder sem gabarito

        # Embeddings removidos do MVP — manter NULL no banco

        record: dict = {
            "content": q["content"],
            "alternatives": q["alternatives"],
            "correct_alternative": correct,
            "subject": subject,
            "topic": topic,
            "difficulty": "medium",
            "year": args.year,
            "source": "ENEM",
            "material_id": material_id,
            "number": num,
            "enem_frequency_score": 0.5,
        }

        if args.dry_run:
            alts_preview = ", ".join(a["label"] for a in q["alternatives"])
            print(
                f"  [DRY] Q{num:3d} | {subject:28s} | gabarito={correct} "
                f"| alts=[{alts_preview}]"
            )
            inserted += 1
            continue

        try:
            qid, created_question = upsert_question(sb, record)
            status = "insert" if created_question else "update"
            print(f"  [OK] Q{num:3d} → {qid} ({status})")
            if created_question:
                inserted += 1
            else:
                updated += 1
        except Exception as exc:
            print(f"  [ERR] Q{num:3d}: {exc}")
            skipped += 1

    print(
        f"\n{'[DRY-RUN] ' if args.dry_run else ''}Concluído — "
        f"inseridas: {inserted} | atualizadas: {updated} | erros: {skipped}"
    )


if __name__ == "__main__":
    main()
