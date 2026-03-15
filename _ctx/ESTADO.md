# ESTADO DO PROJETO — Tutora ENEM

Atualize este arquivo sempre que concluir uma tarefa.
Ultima atualizacao: 2026-03-15 | Agente: @architect (Aria)

---

## Progresso geral

### Infraestrutura
- [x] Estrutura de pastas completa criada (materiais/, scripts/, n8n/, supabase/)
- [x] .env.example atualizado com variáveis específicas (Telegram, NotebookLM, n8n)
- [x] _ctx/ configurada e arquivos compartilhados criados (DECISOES.md, HANDOFF.md)
- [x] Arquitetura: `docs/architecture/ARCHITECTURE.md` revisada conforme `_ctx/DECISOES.md`
- [x] Supabase: Design do schema inicial criado (migrations/) [corrigido com migration `20260315000001_fix_missing_fields.sql`]
- [ ] Supabase: projeto criado no dashboard
- [ ] Supabase: `npx supabase link` executado
- [ ] Supabase: migrations aplicadas (`npx supabase db push`)
- [ ] .env preenchido com credenciais reais
- [ ] n8n: workflows importados

### Conteudo
- [ ] notebooklm-py instalado e autenticado
- [ ] Primeira prova ENEM em materiais/provas/
- [ ] Scripts python (ingest_enem.py, etc.) implementados
- [ ] Primeiras questoes no banco Supabase (Pronto para ingestão via pgvector)

### Bot (n8n)
- [ ] Webhook Telegram configurado no n8n
- [ ] Workflow check-in emocional
- [ ] Workflow "me testa" (sessao basica)
- [ ] Workflow socratico + classificacao de erro
- [ ] Workflow relatorio semanal (cron)

### Anki
- [ ] apkg_builder.py funcionando
- [ ] Bot envia .apkg apos erro
