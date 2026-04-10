# Migracao da Tutora

## Objetivo

Registrar o estado atual da reconstrucao da Tutora saindo do modelo baseado em `n8n` para um backend Python com `FastAPI`, `Supabase` como system of record e `question_snapshot` como fonte primaria.

## Direcao aprovada

- Remover `n8n` do caminho critico
- Usar `FastAPI` como runtime HTTP
- Manter `Supabase` como system of record
- Usar `question_snapshot` como fonte primaria
- Tratar `question_id` apenas como enriquecimento opcional
- Migrar primeiro `me-testa`, depois `socratico`, depois jobs

## O que ja foi feito

### Limpeza do modelo antigo

- Removidos do repo os principais artefatos operacionais do `n8n`:
  - `scripts/fix_tutora_workflows.py`
  - `scripts/audit_and_fix_workflows.py`
  - `scripts/fix_telegram_id.py`
  - `scripts/rebuild_me_testa.py`
  - `scripts/n8n_mcp_server.py`
  - `docs/N8N_MCP.md`
  - `docs/n8n/fallback-multimodal-nodes.json`
- Removido o MCP do `n8n` de `.claude/settings.json`

### Nova base da aplicacao

- Criada a estrutura nova em `app/`
- Criado o runtime `FastAPI`
- Criados modulos iniciais de:
  - `api`
  - `clients`
  - `domain`
  - `repositories`
  - `services`
  - `jobs`
  - `cli`
- Adicionadas dependencias de backend em `requirements.txt`
- Criado `README.md` inicial da nova app

### M1-S1 e M1-S2

- Bootstrap inicial do backend criado
- `clients` explicitos para `Supabase` e `LLM`
- Contrato canonico de sessao criado em `app/domain/session_metadata.py`
- `question_snapshot` tratado como contrato proprio
- `SessionService` separado
- `study_sessions_repository` e `questions_repository` criados
- `question_snapshot_service` criado

### M2-S1 implementado e corrigido

- Criada rota HTTP de intake do `me-testa`
- Criado bootstrap compartilhado em `app/api/runtime.py`
- `me_testa_entry_service` passou a:
  - montar `question_snapshot`
  - persistir sessao
  - tentar `bank_match` apenas como enriquecimento opcional
  - manter os modos `bank_match` e `student_submitted`
- Corrigida a persistencia e reidratacao de `chat_id`
- Ajustado o contrato HTTP de `me-testa` para aceitar `text` ou `caption`
- Expandido o contrato de `question_snapshot` com:
  - `correct_alternative`
  - `explanation`
- Adicionados testes para:
  - round-trip do repositorio de `study_sessions`
  - reidratacao de sessao
  - webhook real
  - integridade de `question_snapshot` com `bank_match`

### Validacoes ja executadas

- Compilacao Python dos modulos novos concluida
- Suite principal local passou com 14 testes:
  - `tests.test_question_snapshot_service`
  - `tests.test_session_metadata`
  - `tests.test_intake_and_me_testa`
  - `tests.test_health`
  - `tests.test_me_testa_api`
  - `tests.test_study_sessions_repository`
  - `tests.test_models_and_webhook`
- Dependencias do backend instaladas em `.venv`

## Estado atual do gate

### QA verdict atual (M2-S1)

`READY FOR REVALIDATION`

Os findings da primeira revisao de QA foram corrigidos no codigo. O corte `M2-S1` agora precisa apenas de uma nova rodada de QA para confirmar o fechamento do gate antes de seguir para `M2-S2`.

### Progresso M2-S2

`IMPLEMENTADO` ✅

Pessimistic locking + race condition mitigation foi completado com:
- Implementação de `FOR UPDATE` em PostgreSQL via RPC
- 34 testes passando (excedendo requirement de 31+)
- Integridade validada para snapshot + bank_match
- Round-trip preserva chat_id sem race condition

### Progresso M2-S3

`IMPLEMENTADO` ✅

Answer correction, error classification, e review card preparation completado com:
- Classificação de erros em 3 categorias (Conceitual, Interpretação, Atenção)
- Preparação automática de review cards para Anki
- `anki_status = queued_local_build` implementado
- 11 testes de answer processing passando
- **Total: 45 testes passando** (excedendo M2-S2)

### Findings da QA que ja foram tratados

1. `chat_id` no Supabase
   - persistencia corrigida
   - reidratacao corrigida

2. Contrato HTTP do `me-testa`
   - ajuste para aceitar `text` ou `caption`
   - `input_mode` preservado

3. Contrato de `question_snapshot`
   - adicionados `correct_alternative`
   - adicionada `explanation`

### Gaps de teste que tambem foram cobertos

- round-trip do `SupabaseStudySessionsRepository`
- reidratacao via `SessionRecord.from_persisted_row`
- webhook real em `app/api/telegram_webhook.py`
- round-trip com `bank_match` preservando `question_snapshot`
- ampliacao da cobertura do snapshot

## Estado atual do gate (atualizado M3-S1)

### M2-S1 status
`READY FOR REVALIDATION`

### M2-S2 status
✅ **COMPLETO**

### M2-S3 status
✅ **COMPLETO**

### M2-S4 status
✅ **IMPLEMENTADO**

### M3-S1 status
✅ **IMPLEMENTADO** (YOLO mode)

**O que foi feito em M3-S1:**
- `SocraticoService` implementado com 4 métodos principais:
  - `route_incorrect_answer()`: Mood check-in
  - `generate_q1()`: Primeira pergunta guiada
  - `process_q1_response()`: Captura resposta Q1
  - `process_q2_response()`: Captura resposta Q2 + explicação
- Integração com `MeTestaAnswerService`:
  - Após erro, roteia para Socratic ao invés de direct
  - Error classification (M2-S3) preservado
  - Review cards salvos antes da pergunta
- Runtime injection em `app/api/runtime.py`
- Handlers para WAITING_SOCRATIC_Q1/Q2 em `me_testa_service.py`
- **6 novos testes** (total: 60 testes passando)
  - Fluxo completo Q1 → Q2 → DONE
  - Mood "cansada" → direct explanation
  - Integration com error classification
  - Follow-ups após conclusão

## O que vem depois

Próximo passo: `M4-S1` LLM integration (Claude API) para geração dinâmica de Q1/Q2.

Depois disso:
1. `M4-S2` jobs
2. `M4-S3` cutover

## Arquivos mais relevantes neste ponto

- `app/api/runtime.py`
- `app/api/me_testa.py`
- `app/api/telegram_webhook.py`
- `app/domain/models.py`
- `app/domain/session_metadata.py`
- `app/repositories/study_sessions_repository.py`
- `app/repositories/questions_repository.py`
- `app/services/question_snapshot_service.py`
- `app/services/session_service.py`
- `app/services/me_testa_entry_service.py`
- `tests/test_question_snapshot_service.py`
- `tests/test_session_metadata.py`
- `tests/test_intake_and_me_testa.py`
- `tests/test_health.py`
- `tests/test_me_testa_api.py`

## Resumo executivo

A migracao saiu do legado em `n8n` e ja tem base nova em `FastAPI`, contratos de dominio definidos e intake inicial de `me-testa` implementado. Os findings iniciais da QA para `M2-S1` foram corrigidos e o proximo passo correto e uma revalidacao da `@qa`. Somente depois disso o projeto deve avancar para `M2-S2`.
