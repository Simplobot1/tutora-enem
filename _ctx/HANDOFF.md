# HANDOFF — Tutora ENEM
**Data:** 2026-04-05
**De:** @aiox-master (Orion)
**Para:** próxima sessão

### Estado consolidado
1. Os dois caminhos principais do `me-testa` já foram validados manualmente no n8n/Telegram:
   - `bank_match`
   - `student_submitted`
2. O gerador local foi reconciliado com o workflow publicado no n8n.
   - comparação remota confirmada: `68` nodes no remoto e `68` nodes no builder local
   - sem diferença nominal entre os conjuntos de nodes
3. A `SUPABASE_SERVICE_ROLE_KEY` já foi rotacionada pelo usuário.
4. O foco não é mais debug de fluxo. O próximo trabalho real é validar o builder local do Anki.

### O que ficou pronto
1. [`scripts/fix_tutora_workflows.py`](/root/projetos/tutora/scripts/fix_tutora_workflows.py) espelha o `me-testa` publicado hoje.
2. [`tests/test_fix_tutora_workflows.py`](/root/projetos/tutora/tests/test_fix_tutora_workflows.py) foi alinhado ao fluxo atual.
3. `python3 -m py_compile scripts/fix_tutora_workflows.py tests/test_fix_tutora_workflows.py` ✅
4. `python3 -m unittest tests.test_fix_tutora_workflows` ✅ (`16` testes)
5. Stories e estado foram atualizados para refletir:
   - validação manual real já executada
   - paridade repo ↔ n8n já reconciliada
   - pendência remanescente concentrada no builder local de `.apkg` e nos gates `npm`

### Próximo passo exato quando voltar
Validar ponta a ponta a fila local de Anki.

#### Como testar
1. Criar um caso real de erro pelo bot.
   - Caso A: `bank_match`
     - enviar uma questão que exista no banco
     - responder errado
   - Caso B: `student_submitted`
     - enviar uma questão fora do banco
     - responder errado
2. Confirmar no Supabase que a `study_session` ficou com:
   - `metadata.anki_status = queued_local_build`
   - `telegram_id` preenchido
   - e um destes:
     - `question_id` preenchido
     - ou `review_card.front` + `review_card.back`
3. Rodar:
```bash
python3 scripts/build_pending_apkgs.py
```
4. Verificar o resultado:
   - `.apkg` gerado em `materiais/flashcards/telegram_<id>/`
   - `study_sessions.metadata.anki_status = prepared`
   - `study_sessions.metadata.anki.ready = true`
   - `study_sessions.metadata.apkg_path` preenchido
5. Validar o comportamento por modo:
   - `question_id`:
     - deve gerar `.apkg`
     - deve persistir em `flashcards`
   - `review_card`:
     - deve gerar `.apkg`
     - hoje pode não persistir automaticamente em `flashcards`; confirmar se isso continua aceitável ou se vira próximo ajuste

### Depois disso
1. Resolver formalmente os gates do repo:
   - `npm run lint`
   - `npm run typecheck`
   - `npm test`
2. Só então fechar documentalmente as stories sem ressalva estrutural.

### Regra prática para a retomada
- Não reabrir roteamento do `me-testa`.
- Não mexer no workflow publicado sem necessidade.
- O próximo teste é operacional, não de arquitetura:
  - criar sessão com erro
  - rodar `build_pending_apkgs.py`
  - verificar `study_sessions` / `flashcards` / arquivo `.apkg`
