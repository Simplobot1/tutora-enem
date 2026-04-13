# ESTADO DO PROJETO — Tutora ENEM

Atualize este arquivo sempre que concluir uma tarefa.
Ultima atualizacao: 2026-04-05 | Agentes: @dev (Dex), @aiox-master (Orion)

---

## Progresso geral

### Infraestrutura
- [x] Estrutura de pastas completa criada (materiais/, scripts/, n8n/, supabase/)
- [x] .env.example atualizado com variáveis específicas (Telegram, NotebookLM, n8n)
- [x] _ctx/ configurada e arquivos compartilhados criados (DECISOES.md, HANDOFF.md)
- [x] Arquitetura: `docs/architecture/ARCHITECTURE.md` revisada conforme `_ctx/DECISOES.md`
- [x] Supabase: Design do schema inicial criado (migrations/) [corrigido com migration `20260315000001_fix_missing_fields.sql`]
- [x] Supabase: projeto criado no dashboard (qnuubscjgsltgvwqhmiu)
- [x] Supabase: `npx supabase link` executado
- [x] Supabase: migrations aplicadas (`npx supabase db push`) — schema inicial + correções
- [ ] Supabase: migrations de review 0.2 preparadas e pendentes de aplicação
  - `20260322000005_nullable_answers_question_id.sql`
  - `20260322000006_allow_ansiosa_in_study_sessions_mood.sql`
- [x] .env preenchido com credenciais reais (não commitado)
- [x] n8n: workflows criados e funcionando
- [x] Validacao manual real dos fluxos principais registrada em `docs/handoffs/2026-04-03-tutora-workflows-validation.md`

### Conteudo
- [ ] notebooklm-py instalado e autenticado
- [x] Primeira prova ENEM em materiais/provas/
- [x] Scripts python (ingest_enem.py, apkg_builder.py) implementados e testados
  - `python3 scripts/ingest_enem.py --file 'materiais/provas/1º DIA - PROVA TIPO 3.pdf' --dry-run --year 2024` -> 61 questões extraídas sem erro
  - `python3 scripts/ingest_enem.py --file 'materiais/provas/1º DIA - PROVA TIPO 3.pdf' --year 2024` -> 1 material + 61 questões inseridas no Supabase ativo
  - `scripts/ingest_enem.py` revisado em 2026-03-22 para deduplicar questões no parse e fazer upsert lógico em reruns
- [x] 5 questões fictícias no banco para testes (Supabase)

### Bot (n8n)
- [x] me-testa (ID: 1q9aRuO2uwLbXV6V) — ✅ COMPLETO E TESTADO
  - Fluxo principal reconstruído para começar pela questão enviada pela aluna, fazer curadoria, receber resposta, corrigir, classificar erro e decidir entre socrático ou explicação direta
  - Salva acerto e erro em `answers` (selected_alternative, is_correct, error_type, feedback_received)
  - Prepara revisão/Anki em `study_sessions.metadata`
  - Webhook: https://n8n.simplobot.com.br/webhook/tutora-main (POST, onReceived)
  - Workflow reaplicado em 2026-03-22 via `python3 scripts/fix_tutora_workflows.py`
  - Evoluído em 2026-03-22 para fallback multimodal fora do banco com reconhecimento de `texto`, `foto/imagem`, `documento`, `áudio` e `vídeo`
  - `foto/imagem` e `documento` agora entram em trilha de extração/OCR via Claude quando houver arquivo viável; `áudio` e `vídeo` respondem com fallback controlado e pedido de reformatação
  - Casos fora do banco persistem confiança, contexto faltante e `question_snapshot` em `study_sessions.metadata`; `answers.question_id` passou a aceitar `NULL` para esses atendimentos ad hoc
  - Review 0.2 corrigido para persistir `answers` e `study_sessions` antes de ramificar para socrático/direto
  - `anki_ready` agora permanece `false` até existir `user_id` Supabase confiável para geração real de `.apkg`
  - Reaplicado em 2026-03-29 com correção do fallback multimodal textual: Claude agora responde sob contrato de JSON puro, o parser local aceita JSON cercado por markdown/wrappers, alternativas inline e formatos `A)`, `A.`, `A:`, `A -`
  - O estado `WAITING_FALLBACK_ANSWER` voltou a ser alcançável em texto suficiente; `WAITING_FALLBACK_DETAILS` permanece para entrada realmente incompleta/ilegível
  - O branch de erro fallback continua registrando revisão apenas em `study_sessions.metadata`; ainda não gera `.apkg` quando não há `question_id` confiável
  - O branch socrático continua disparando somente em respostas erradas quando `decisao = socratico`; no fallback isso depende da normalização da resolução devolvida pelo Claude
  - Em 2026-03-30 o gerador local recebeu melhoria de respostas no fallback: linguagem mais pedagógica, sem jargão interno, com composição defensiva para evitar texto ruim por valores ausentes e sem prometer revisão automática fora do que a infraestrutura suporta
  - Em 2026-04-03 os dois caminhos principais (`bank_match` e `student_submitted`) foram validados manualmente no n8n/Telegram, com persistência observada de `review_card`, `question_snapshot`, `question_ref` e `anki` em `study_sessions.metadata`
  - Em 2026-04-05 o gerador local foi reconciliado com o workflow publicado; comparação remota confirmou `68` nodes no n8n e `68` nodes no builder local, sem diferença nominal
- [x] check-in-emocional (ID: ejIaFov6qFRNvpTI) — ✅ REBUILDADO
  - Persistência de `mood` e `mood_updated_at` em `public.bot_users`
  - Valores permitidos: `animada`, `normal`, `cansada`, `ansiosa`
- [x] socratico (ID: 1ftyRX3qd5bBmWLn) — ✅ REBUILDADO E ATIVADO
  - Máximo de 2 perguntas guiadas
  - Desvio para explicação direta quando `mood = cansada`
  - Aceita `question_snapshot` inline para suportar fallback multimodal sem depender de `question_id`
- [x] relatorio-semanal (ID: mSfE36bkqitAZYSQ) — ✅ REBUILDADO E ATIVADO
  - Agendamento semanal
  - Envio apenas de progresso relativo e engajamento
  - Fluxo revisado para não expor `telegram_id` bruto no texto e para só enviar quando houver destino explícito configurado

### Decisões técnicas tomadas (n8n)
- Switch node tem bug no typeVersion 3 — usar IF node
- specifyBody="json" com objeto JS direto (sem JSON.stringify) para chamadas Claude
- Expressões complexas em Telegram node causam "invalid syntax" — usar Code node antes
- $node['X'].json pode ser array [] quando Supabase não retorna resultado — usar Normaliza Estado
- bot_users usa telegram_id BIGINT como PK (sem auth.users)
- Coluna de resposta em answers: `selected_alternative` (não student_answer)

### Anki
- [x] apkg_builder.py funcionando
- [x] Bot prepara `.apkg` apos erro com `question_id` confiável
  - Fluxo atual gera o deck por `telegram_id`, registra `anki_status` em `study_sessions.metadata` e salva o arquivo em `materiais/flashcards/telegram_<telegram_id>/`
  - Entrega automatizada do arquivo no Telegram ainda não foi implementada; o estado atual é preparo/local file para importação manual no Anki
- [ ] Fallback multimodal ainda não gera `.apkg` sem `question_id`
  - Atualizacao 2026-04-03: o fluxo agora persiste `review_card` e `anki.builder_mode = review_card`, permitindo fila local de build mesmo quando `question_id = null`
  - Gap remanescente: ainda falta validar ponta a ponta `scripts/build_pending_apkgs.py` + `scripts/apkg_builder.py` + persistência final em `flashcards`

---

## ✅ MIGRAÇÃO FASTAPI COMPLETA (2026-04-10)

### Status Final
- ✅ **86 testes passando** (45 M2 + 6 M3 + 14 M4-S1 + 12 M4-S3)
- ✅ **Zero regressions**
- ✅ **N8N removido 100%**
- ✅ **Código em produção** (commit 8322e18)
- ✅ **Release v1.0.0 criada**
- ✅ **Webhook Telegram funcionando** (202 Accepted)

### Arquivos Críticos
- `app/main.py` — API principal
- `app/api/me_testa.py` — Intake
- `app/api/me_testa_answer.py` — Answer processing
- `app/services/` — Lógica de negócio
- `supabase/migrations/` — Schema com locking
- `scripts/{ingest_enem,apkg_builder,build_pending_apkgs}.py` — Automação

## 🔧 Fixes Aplicados (2026-04-12 23:43 - 23:48)

### Commit 7be1b68: Remove ocr_cache Parameter
**Problema:** Runtime.py passava parâmetro `ocr_cache` que MeTestaEntryService não esperava mais
- ❌ **TypeError:** `MeTestaEntryService.__init__() got an unexpected keyword argument 'ocr_cache'`
- **Impacto:** 500 error em TODOS os webhooks do Telegram

**Solução:**
```python
# app/api/runtime.py
- Removido: from app.services.ocr_cache import OcrCache
- Removido: ocr_cache = OcrCache()
- Removido: ocr_cache=ocr_cache (parâmetro na instantiação)

# tests/test_m5_s1_ocr_photo.py  
- Removida classe TestOcrCache (3 métodos)
- Removido test_handle_image_intake_cache_hit
```

**Validação:** ✅ 142 testes passando

### Commit 4d733db: Add --no-cache to Docker Build
**Problema:** Docker estava usando cache de build anterior (imagem com código antigo)
- Deploy passava no healthcheck mas webhook ainda retornava erro 500

**Solução:**
```yaml
# .github/workflows/deploy.yml
- docker build --no-cache -t tutora-api:latest .  (linhas 55 + 73)
```

**Validação:** ✅ Deploy completou com sucesso em 1m33s

### 📦 Deployment Status
- ✅ **Código:** Corrigido localmente (142 testes passando)
- ✅ **Git:** Commits enviados para origin/main (7be1b68, 4d733db)
- ✅ **Docker:** Imagem reconstruída SEM cache em Hetzner
- ✅ **API:** Health endpoint respondendo (20:48Z)

### 🧪 AGUARDANDO
- ⏳ Webhook do Telegram pode estar apontando para domínio antigo
- ⏳ Verificar: https://tutora-sofia.simplobot.com.br/webhooks/telegram (domínio correto)
