# HANDOFF — Tutora ENEM
**Data:** 2026-03-15
**De:** @data-engineer (Dara)
**Para:** @devops (Gage) ou @dev (Dex)

### O que foi feito:
1.  **Schema do Banco de Dados:** Criada a primeira migration em `supabase/migrations/20260315000000_initial_schema.sql`.
2.  **Tecnologias Habilitadas:** PostgreSQL com extensões `pgvector` (para RAG) e `uuid-ossp`.
3.  **Estrutura de Tabelas:** `users`, `materials`, `questions`, `study_sessions`, `answers`, `flashcards`.
4.  **Analytics:** Criada a view `performance_by_topic` para monitorar o progresso do aluno por tópico e tipo de erro.
5.  **Segurança:** RLS (Row Level Security) configurado em todas as tabelas.
6.  **Migration de Correção:** Criada `supabase/migrations/20260315000001_fix_missing_fields.sql` para adicionar `study_sessions.mood`, `questions.material_id`, `questions.number`, `questions.enem_frequency_score`, `answers.time_spent_seconds` e `flashcards.anki_card_id`.
7.  **Índices para o Selector:** Adicionados índices em `questions(material_id)` e `questions(enem_frequency_score DESC NULLS LAST)`.
8.  **Analytics Atualizado:** A view `performance_by_topic` agora expõe `last_studied_at` e `trend`, mantendo aliases compatíveis com a versão anterior.

### Próximos Passos Sugeridos:
- **@devops (Gage):** Executar `npx supabase link` e `npx supabase db push` assim que o projeto no dashboard estiver criado, aplicando também a migration corretiva `20260315000001_fix_missing_fields.sql`.
- **@dev (Dex):** Ajustar ingestão e selector para preencher/consumir `questions.material_id`, `questions.number`, `questions.enem_frequency_score` e `answers.time_spent_seconds`.
- **@dev (Dex):** Ajustar integração Anki para persistir `flashcards.anki_card_id`.

### Bloqueios:
- Aguardando credenciais do Supabase para realizar o link e push das migrations.
