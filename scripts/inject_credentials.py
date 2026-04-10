#!/usr/bin/env python3
"""Injeta credenciais via ambiente nos workflows do n8n via API REST."""

import json
import os
import requests
import sys
from copy import deepcopy
from pathlib import Path

def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        env[key.strip()] = value.strip()
    return env


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
ENV = load_env(ENV_PATH)
SUPABASE_URL = ENV.get("SUPABASE_URL", "https://qnuubscjgsltgvwqhmiu.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = ENV.get("SUPABASE_ANON_KEY", ENV.get("SUPABASE_SERVICE_ROLE_KEY", ""))
TELEGRAM_BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
N8N_API_KEY = ENV.get("N8N_API_KEY", "")

if not N8N_API_KEY:
    sys.exit("ERRO: N8N_API_KEY não encontrada no .env")
if not SUPABASE_ANON_KEY:
    sys.exit("ERRO: SUPABASE_ANON_KEY ou SUPABASE_SERVICE_ROLE_KEY não encontrada no .env")

N8N_BASE_URL = "https://n8n.simplobot.com.br/api/v1"
HEADERS_N8N = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json",
}

WORKFLOWS = {
    "check-in-emocional": "ejIaFov6qFRNvpTI",
    "me-testa": "1q9aRuO2uwLbXV6V",
    "socratico": "1ftyRX3qd5bBmWLn",
    "relatorio-semanal": "mSfE36bkqitAZYSQ",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def supabase_headers():
    return [
        {"name": "apikey", "value": SUPABASE_ANON_KEY},
        {"name": "Authorization", "value": f"Bearer {SUPABASE_ANON_KEY}"},
        {"name": "Content-Type", "value": "application/json"},
    ]

def anthropic_headers():
    return [
        {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
        {"name": "anthropic-version", "value": "2023-06-01"},
        {"name": "Content-Type", "value": "application/json"},
    ]

def anthropic_body():
    return """={{ {
        model: "claude-haiku-4-5-20251001",
        max_tokens: 1024,
        messages: [{ role: "user", content: $json.prompt || "Olá" }]
    } }}"""

def is_supabase_node(node: dict) -> bool:
    """Detecta se o httpRequest node chama o Supabase."""
    params = node.get("parameters", {})
    url = str(params.get("url", "")).lower()
    name = node.get("name", "").lower()
    return (
        "supabase" in url
        or "qnuubscjgsltgvwqhmiu" in url
        or "supabase" in name
        or "perfil" in name
        or "mood" in name
        or "progresso" in name
        or "flashcard" in name
        or "questao" in name
        or "sessao" in name
        or "historico" in name
        or "usuario" in name
    )

def is_anthropic_node(node: dict) -> bool:
    """Detecta se o httpRequest node chama a Anthropic."""
    params = node.get("parameters", {})
    url = str(params.get("url", "")).lower()
    name = node.get("name", "").lower()
    return (
        "anthropic" in url
        or "claude" in url
        or "api.anthropic" in url
        or "claude" in name
        or "classifica" in name
        or "gera" in name
        or "socrát" in name
        or "socratic" in name
        or "feedback" in name
        or "explica" in name
        or "ia" in name
        or "llm" in name
        or "ai" in name
    )

def inject_http_node(node: dict) -> tuple[dict, str | None]:
    """
    Injeta credenciais num httpRequest node.
    Retorna (node_modificado, tipo_injecao | None).
    """
    node = deepcopy(node)
    params = node.setdefault("parameters", {})

    if is_anthropic_node(node):
        params["headerParameters"] = {"parameters": anthropic_headers()}
        # Garante sendBody + body correto se ainda não tiver body configurado
        if not params.get("sendBody"):
            params["sendBody"] = True
        if not params.get("body"):
            params["body"] = anthropic_body()
        # URL padrão da Anthropic se não definida
        if not params.get("url") or params["url"] in ("", "={{ $json.url }}"):
            params["url"] = "https://api.anthropic.com/v1/messages"
        return node, "anthropic"

    if is_supabase_node(node):
        params["headerParameters"] = {"parameters": supabase_headers()}
        # Corrige base URL se estiver incompleta
        url = params.get("url", "")
        if url and not url.startswith("http") and not url.startswith("{{"):
            params["url"] = SUPABASE_URL + "/rest/v1" + url
        elif not url:
            params["url"] = SUPABASE_URL + "/rest/v1/questoes"
        return node, "supabase"

    return node, None

def inject_telegram_node(node: dict) -> tuple[dict, bool]:
    """
    Marca nodes Telegram com nota e adiciona chatId placeholder.
    """
    node = deepcopy(node)
    params = node.setdefault("parameters", {})
    # Adiciona chatId placeholder se ausente
    if not params.get("chatId"):
        params["chatId"] = "={{ $json.chat_id }}"
    # Nota para configurar no UI
    node["notes"] = "Configurar credencial Telegram no n8n UI"
    node["notesInFlow"] = True
    return node, True

# ── Core ───────────────────────────────────────────────────────────────────────

def get_workflow(workflow_id: str) -> dict:
    url = f"{N8N_BASE_URL}/workflows/{workflow_id}"
    resp = requests.get(url, headers=HEADERS_N8N, timeout=30)
    resp.raise_for_status()
    return resp.json()

def put_workflow(workflow_id: str, payload: dict) -> dict:
    url = f"{N8N_BASE_URL}/workflows/{workflow_id}"
    resp = requests.put(url, headers=HEADERS_N8N, json=payload, timeout=30)
    if not resp.ok:
        print(f"  [ERRO] PUT {workflow_id}: {resp.status_code} — {resp.text[:300]}")
        resp.raise_for_status()
    return resp.json()

def process_workflow(name: str, wf_id: str):
    print(f"\n{'='*60}")
    print(f"Workflow: {name}  ({wf_id})")
    print("="*60)

    wf = get_workflow(wf_id)

    nodes = wf.get("nodes", [])
    updated_nodes = []
    report = []

    for node in nodes:
        node_type = node.get("type", "")
        node_name = node.get("name", "<sem nome>")

        if node_type == "n8n-nodes-base.httpRequest":
            if is_anthropic_node(node):
                new_node, kind = inject_http_node(node)
                updated_nodes.append(new_node)
                report.append(f"  [ANTHROPIC] {node_name}")
            elif is_supabase_node(node):
                new_node, kind = inject_http_node(node)
                updated_nodes.append(new_node)
                report.append(f"  [SUPABASE]  {node_name}")
            else:
                updated_nodes.append(node)
                report.append(f"  [SKIP-HTTP] {node_name}  (sem padrão reconhecido)")
        elif node_type == "n8n-nodes-base.telegram":
            new_node, _ = inject_telegram_node(node)
            updated_nodes.append(new_node)
            report.append(f"  [TELEGRAM]  {node_name}  → nota + chatId placeholder")
        else:
            updated_nodes.append(node)

    # Monta payload preservando todos os campos
    payload = {
        "name": wf.get("name"),
        "nodes": updated_nodes,
        "connections": wf.get("connections", {}),
        "settings": wf.get("settings", {}),
        "staticData": wf.get("staticData"),
    }
    # Remove campos None para não sujar o payload
    payload = {k: v for k, v in payload.items() if v is not None}

    put_workflow(wf_id, payload)

    for line in report:
        print(line)
    print(f"  → {len([r for r in report if 'SKIP' not in r])} nodes atualizados")
    return report

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Iniciando injeção de credenciais nos workflows n8n...")
    print(f"Base URL: {N8N_BASE_URL}")
    print(f"N8N_API_KEY: {N8N_API_KEY[:20]}...")

    summary = {}
    for name, wf_id in WORKFLOWS.items():
        try:
            report = process_workflow(name, wf_id)
            summary[name] = {"status": "OK", "nodes": report}
        except Exception as e:
            print(f"  [FALHA] {name}: {e}")
            summary[name] = {"status": "ERRO", "error": str(e)}

    print("\n" + "="*60)
    print("RESUMO FINAL")
    print("="*60)
    for wf_name, result in summary.items():
        status = result["status"]
        if status == "OK":
            updates = [n for n in result["nodes"] if "SKIP" not in n]
            print(f"  {wf_name}: {status} ({len(updates)} nodes atualizados)")
        else:
            print(f"  {wf_name}: {status} — {result.get('error')}")

if __name__ == "__main__":
    main()
