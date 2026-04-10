#!/usr/bin/env python3
"""
fix_table_names.py
Corrige os 4 workflows n8n: nomes de tabelas, colunas e troca para service_role_key.
"""

import json
import re
import copy
import sys
import os
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://n8n.simplobot.com.br/api/v1")
N8N_API_KEY = os.getenv("N8N_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qnuubscjgsltgvwqhmiu.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

WORKFLOWS = {
    "check-in-emocional": "ejIaFov6qFRNvpTI",
    "me-testa":           "1q9aRuO2uwLbXV6V",
    "socratico":          "1ftyRX3qd5bBmWLn",
    "relatorio-semanal":  "mSfE36bkqitAZYSQ",
}

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ---------------------------------------------------------------------------
# Mapeamento de correções de strings (aplicado a qualquer valor string no JSON)
# ---------------------------------------------------------------------------
TABLE_MAP = {
    "/rest/v1/sessions":   "/rest/v1/study_sessions",
    "/rest/v1/questoes":   "/rest/v1/questions",
    "/rest/v1/erros":      "/rest/v1/answers",
    "/rest/v1/mood_logs":  "/rest/v1/users",
}

COLUMN_MAP = [
    # (padrão regex, substituição)
    (r'\baluno_id\b',         "user_id"),
    (r'\bquestao_id\b',       "question_id"),
    (r'\btipo_erro\b',        "error_type"),
    (r'\bfeedback\b(?!\s*_received)',  "feedback_received"),
]

# Chaves Supabase que devem ser trocadas
ANON_KEY_PATTERN = re.compile(
    r'eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'
)

# ---------------------------------------------------------------------------
# Definição das correções específicas por workflow e nome do node
# ---------------------------------------------------------------------------

# Estrutura: { "workflow_name": { "node_name_substr": { "method": .., "url": .., "body": .., "headers": {..}, "qs": .. } } }
# Onde None = não alterar esse campo
SPECIFIC_FIXES = {
    "check-in-emocional": {
        "Salva Mood": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{{{{ $json.body.message.from.id }}}}",
            "body": json.dumps({"mood": "={{ $json.mood }}", "mood_updated_at": "={{ new Date().toISOString() }}"}),
            "extra_headers": {"Prefer": "return=minimal"},
        },
        "Garante Usuário": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/users",
            "body": json.dumps({
                "id": "={{ $json.body.message.from.id.toString() }}",
                "telegram_id": "={{ $json.body.message.from.id }}",
                "full_name": "={{ $json.body.message.from.first_name }}"
            }),
            "extra_headers": {"Prefer": "resolution=ignore-duplicates"},
        },
        # fallback: qualquer node que mencione mood_logs
        "mood_logs": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/users?telegram_id=eq.{{{{ $json.body.message.from.id }}}}",
            "body": json.dumps({"mood": "={{ $json.mood }}", "mood_updated_at": "={{ new Date().toISOString() }}"}),
            "extra_headers": {"Prefer": "return=minimal"},
        },
    },
    "me-testa": {
        "Busca Sessão": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?user_id=eq.{{{{ $json.body.message.from.id }}}}&status=eq.active&order=started_at.desc&limit=1",
            "body": None,
        },
        "Busca Questão": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/questions?select=*&limit=1",
            "body": None,
        },
        "Cria Sessão": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions",
            "body": json.dumps({
                "user_id": "={{ $json.body.message.from.id.toString() }}",
                "type": "quiz",
                "status": "active",
                "metadata": {
                    "state": "WAITING_ANSWER",
                    "question_id": "={{ $node['Busca Questão Aleatória'].json[0].id }}"
                }
            }),
            "extra_headers": {"Prefer": "return=representation"},
        },
        "Atualiza Acerto": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?id=eq.{{{{ $node['Busca Sessão'].json[0].id }}}}",
            "body": json.dumps({"status": "completed"}),
        },
        "Salva Erro": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/answers",
            "body": json.dumps({
                "user_id": "={{ $json.body.message.from.id.toString() }}",
                "question_id": "={{ $node['Busca Sessão'].json[0].metadata.question_id }}",
                "session_id": "={{ $node['Busca Sessão'].json[0].id }}",
                "is_correct": False,
                "error_type": "={{ $json.error_type }}",
                "feedback_received": "={{ $json.feedback }}"
            }),
        },
        "Atualiza Sessão Erro": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?id=eq.{{{{ $node['Busca Sessão'].json[0].id }}}}",
            "body": json.dumps({"status": "completed"}),
        },
    },
    "socratico": {
        "Busca Sessão": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?user_id=eq.{{{{ $json.body.message.from.id }}}}&status=eq.active&type=eq.socratic_drill&order=started_at.desc&limit=1",
            "body": None,
        },
        "Busca Questão": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/questions?select=*&limit=1",
            "body": None,
        },
        "Salva Sessão Q1_WAITING": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions",
            "body": json.dumps({
                "user_id": "={{ $json.body.message.from.id.toString() }}",
                "type": "socratic_drill",
                "status": "active",
                "metadata": {
                    "state": "Q1_WAITING",
                    "question_id": "={{ $node['Busca Questão'].json[0].id }}"
                }
            }),
            "extra_headers": {"Prefer": "return=representation"},
        },
        "Salva Sessão Q2_WAITING": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?id=eq.{{{{ $node['Salva Sessão Q1_WAITING'].json[0].id }}}}",
            "body": json.dumps({
                "metadata": {
                    "state": "Q2_WAITING",
                    "question_id": "={{ $node['Busca Questão'].json[0].id }}"
                }
            }),
        },
        "Reset Sessão IDLE": {
            "method": "PATCH",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?id=eq.{{{{ $node['Busca Sessão'].json[0].id }}}}",
            "body": json.dumps({"status": "completed"}),
        },
    },
    "relatorio-semanal": {
        "Busca Erros": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/answers?is_correct=eq.false&created_at=gte.{{{{ new Date(Date.now()-7*24*60*60*1000).toISOString() }}}}&select=error_type,question_id",
            "body": None,
        },
        "Busca Sessões": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/study_sessions?started_at=gte.{{{{ new Date(Date.now()-7*24*60*60*1000).toISOString() }}}}&select=id,status,type",
            "body": None,
        },
    },
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def n8n_request(method: str, path: str, body=None):
    url = N8N_BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        print(f"  [HTTP ERROR {e.code}] {method} {url}")
        print(f"  Response: {body_txt[:500]}")
        raise


# ---------------------------------------------------------------------------
# Core fix logic
# ---------------------------------------------------------------------------

def fix_string_value(s: str) -> str:
    """Apply generic table/column/key replacements to a plain string."""
    # Replace tables in URL paths
    for old, new in TABLE_MAP.items():
        s = s.replace(old, new)
    # Replace column names
    for pattern, replacement in COLUMN_MAP:
        s = re.sub(pattern, replacement, s)
    # Replace any Supabase JWT (anon or old service role) with service_role_key
    # but only if it's NOT already our service_role_key
    def replace_key(m):
        found = m.group(0)
        if found == SUPABASE_SERVICE_ROLE_KEY:
            return found
        # Only replace if it looks like a Supabase JWT (contains supabase in payload)
        try:
            import base64
            payload = found.split('.')[1]
            # add padding
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload).decode()
            if 'supabase' in decoded or 'role' in decoded:
                return SUPABASE_SERVICE_ROLE_KEY
        except Exception:
            pass
        return found
    s = ANON_KEY_PATTERN.sub(replace_key, s)
    return s


def fix_value_recursive(obj):
    """Walk the entire JSON object tree and fix string values."""
    if isinstance(obj, str):
        return fix_string_value(obj)
    elif isinstance(obj, dict):
        return {k: fix_value_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_value_recursive(item) for item in obj]
    return obj


def is_supabase_http_node(node: dict) -> bool:
    """Return True if node is an httpRequest node that calls Supabase."""
    if node.get("type") not in ("n8n-nodes-base.httpRequest", "@n8n/n8n-nodes-langchain.httpRequest"):
        return False
    params = node.get("parameters", {})
    url = params.get("url", "")
    if "supabase" in url.lower() or "qnuubscjgsltgvwqhmiu" in url:
        return True
    # Check options/headers
    raw = json.dumps(params)
    return "supabase" in raw.lower() or "qnuubscjgsltgvwqhmiu" in raw


def apply_supabase_headers(params: dict) -> dict:
    """Ensure the node uses service_role_key for apikey and Authorization."""
    # n8n stores headers in different places depending on version
    # Try headerParameters (older) and headers (newer)
    changed = False

    # ---- headerParameters style ----
    header_params = params.get("headerParameters", {})
    if isinstance(header_params, dict):
        params_list = header_params.get("parameters", [])
        if isinstance(params_list, list):
            new_list = []
            replaced_apikey = False
            replaced_auth = False
            for h in params_list:
                name = h.get("name", "").lower()
                if name == "apikey":
                    new_list.append({"name": "apikey", "value": SUPABASE_SERVICE_ROLE_KEY})
                    replaced_apikey = True
                    changed = True
                elif name == "authorization":
                    new_list.append({"name": "Authorization", "value": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"})
                    replaced_auth = True
                    changed = True
                else:
                    new_list.append(h)
            if not replaced_apikey:
                new_list.append({"name": "apikey", "value": SUPABASE_SERVICE_ROLE_KEY})
                changed = True
            if not replaced_auth:
                new_list.append({"name": "Authorization", "value": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"})
                changed = True
            params["headerParameters"] = {"parameters": new_list}

    # ---- headers style (newer n8n) ----
    headers_obj = params.get("headers", {})
    if isinstance(headers_obj, dict) and "values" in headers_obj:
        values = headers_obj["values"]
        if isinstance(values, dict):
            values["apikey"] = SUPABASE_SERVICE_ROLE_KEY
            values["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
            changed = True

    # If neither structure exists, create headerParameters
    if not params.get("headerParameters") and not params.get("headers"):
        params["headerParameters"] = {
            "parameters": [
                {"name": "apikey", "value": SUPABASE_SERVICE_ROLE_KEY},
                {"name": "Authorization", "value": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        }
        changed = True

    return params, changed


def apply_specific_fix(params: dict, fix: dict) -> (dict, list):
    """Apply a specific fix dict to node parameters. Returns (params, changes_list)."""
    changes = []

    if fix.get("method") and params.get("method", "").upper() != fix["method"].upper():
        old = params.get("method", "")
        params["method"] = fix["method"]
        changes.append(f"method: {old!r} → {fix['method']!r}")

    if "url" in fix and fix["url"] is not None:
        old = params.get("url", "")
        if old != fix["url"]:
            params["url"] = fix["url"]
            changes.append(f"url: {old!r} → {fix['url']!r}")

    if "body" in fix and fix["body"] is not None:
        # body might be in parameters.body or parameters.bodyParameters
        old_body = params.get("body", params.get("bodyParametersJson", ""))
        new_body = fix["body"]
        if old_body != new_body:
            params["body"] = new_body
            # also set bodyParametersJson if it exists
            if "bodyParametersJson" in params:
                params["bodyParametersJson"] = new_body
            # set sendBody = true
            params["sendBody"] = True
            params["specifyBody"] = "json"
            changes.append(f"body updated")

    elif fix.get("body") is None and fix.get("method") == "GET":
        # GET requests shouldn't have body
        if "body" in params:
            del params["body"]
            changes.append("body removed (GET)")

    if fix.get("extra_headers"):
        hp = params.get("headerParameters", {})
        params_list = hp.get("parameters", []) if isinstance(hp, dict) else []
        for hname, hval in fix["extra_headers"].items():
            found = False
            for h in params_list:
                if h.get("name", "").lower() == hname.lower():
                    h["value"] = hval
                    found = True
                    break
            if not found:
                params_list.append({"name": hname, "value": hval})
        params["headerParameters"] = {"parameters": params_list}
        changes.append(f"extra_headers: {list(fix['extra_headers'].keys())}")

    return params, changes


def find_specific_fix(workflow_name: str, node_name: str):
    """Find the best matching specific fix for a node."""
    wf_fixes = SPECIFIC_FIXES.get(workflow_name, {})
    # Exact match first
    if node_name in wf_fixes:
        return wf_fixes[node_name]
    # Substring match
    for key, fix in wf_fixes.items():
        if key.lower() in node_name.lower() or node_name.lower() in key.lower():
            return fix
    return None


def process_workflow(wf_name: str, wf_id: str):
    print(f"\n{'='*60}")
    print(f"Workflow: {wf_name} ({wf_id})")
    print(f"{'='*60}")

    # GET workflow
    wf = n8n_request("GET", f"/workflows/{wf_id}")
    nodes = wf.get("nodes", [])
    print(f"  Nodes encontrados: {len(nodes)}")

    changes_report = []
    total_changed = 0

    for i, node in enumerate(nodes):
        node_name = node.get("name", f"node_{i}")
        node_type = node.get("type", "")

        # 1. Apply generic fixes recursively to all string values
        node_fixed = fix_value_recursive(node)

        # 2. For Supabase HTTP nodes, do specific fixes
        if is_supabase_http_node(node_fixed):
            params = node_fixed.get("parameters", {})

            # Apply service_role_key to headers
            params, header_changed = apply_supabase_headers(params)

            specific_changes = []
            fix = find_specific_fix(wf_name, node_name)
            if fix:
                params, specific_changes = apply_specific_fix(params, fix)
                print(f"  [SPECIFIC FIX] Node '{node_name}'")
            else:
                print(f"  [GENERIC FIX]  Node '{node_name}' (supabase http node, no specific fix)")

            node_fixed["parameters"] = params
            all_changes = (["service_role_key applied"] if header_changed else []) + specific_changes

            if all_changes or node != node_fixed:
                changes_report.append({
                    "node": node_name,
                    "changes": all_changes
                })
                total_changed += 1

        nodes[i] = node_fixed

    wf["nodes"] = nodes

    # PUT workflow back — n8n only accepts these 4 fields
    PUT_ALLOWED = {"name", "nodes", "connections", "settings"}
    payload = {k: wf[k] for k in PUT_ALLOWED if k in wf}

    print(f"\n  Enviando workflow atualizado...")
    try:
        result = n8n_request("PUT", f"/workflows/{wf_id}", body=payload)
        print(f"  PUT OK — id={result.get('id')}, updatedAt={result.get('updatedAt')}")
    except Exception as e:
        print(f"  PUT FALHOU: {e}")
        return changes_report

    # Report
    print(f"\n  Nodes alterados: {total_changed}")
    for cr in changes_report:
        print(f"    * {cr['node']}: {', '.join(cr['changes']) if cr['changes'] else 'generic string replacements'}")

    return changes_report


def main():
    print("=== fix_table_names.py ===")
    print(f"Base URL: {N8N_BASE_URL}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print()

    all_reports = {}
    for wf_name, wf_id in WORKFLOWS.items():
        try:
            report = process_workflow(wf_name, wf_id)
            all_reports[wf_name] = report
        except Exception as e:
            print(f"  ERRO ao processar {wf_name}: {e}")
            all_reports[wf_name] = [{"error": str(e)}]

    print("\n\n" + "="*60)
    print("RESUMO FINAL")
    print("="*60)
    for wf_name, report in all_reports.items():
        print(f"\n{wf_name}:")
        if not report:
            print("  (nenhuma alteração)")
        for cr in report:
            if "error" in cr:
                print(f"  ERRO: {cr['error']}")
            else:
                print(f"  [{cr['node']}] {', '.join(cr['changes']) if cr['changes'] else 'string replacements only'}")

    print("\nConcluído.")


if __name__ == "__main__":
    main()
