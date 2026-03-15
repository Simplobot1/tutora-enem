# CLAUDE.md

This file provides guidance to agents when working with code in this repository.

---

## Projeto

**Tutora ENEM** — Bot no Telegram que atua como tutora pessoal para uma estudante se preparando para o ENEM. Utiliza n8n para orquestração de diálogos, Supabase como backend e Claude 3.5 Sonnet para inteligência pedagógica.

> Princípio central: sessões de 10-15 minutos, várias vezes ao dia — cirúrgico e eficaz, não exaustivo.

---

## Stack Real (MVP)

| Componente | Tecnologia |
| :--- | :--- |
| **Orquestrador** | **n8n** (workflows visuais) |
| **IA** | **Claude 3.5 Sonnet** (via n8n nodes) |
| **Banco / Auth** | **Supabase** (PostgreSQL + pgvector) |
| **Scripts Locais** | Python 3.11+ (Ingestão e Geração de `.apkg`) |
| **Integração** | Telegram Bot API (Webhooks via n8n) |
| **Sessão** | n8n Internal State (n8n gerencia o estado) |

---

## Estrutura de Pastas

```
n8n/workflows/               -- arquivos JSON dos workflows do n8n
supabase/migrations/         -- migrations SQL para o Supabase
scripts/                     -- ferramentas em Python para automação local
  ingest_enem.py             -- ingere questões no Supabase via API
  apkg_builder.py            -- gera flashcards Anki
materiais/                   -- arquivos fonte (PDFs de provas, livros)
_ctx/                        -- arquivos de contexto do projeto (DECISOES, ESTADO)
docs/architecture/           -- documentação técnica detalhada
```

---

## Comandos Úteis

```bash
# Iniciar Supabase localmente (se necessário)
npx supabase start

# Aplicar novas migrations
npx supabase db push

# Gerar tipos do Supabase (se usando scripts TS/JS)
npx supabase gen types typescript --local > supabase/types.ts

# Executar script de ingestão
python scripts/ingest_enem.py --file materiais/provas/enem2024.pdf
```

---

## Regras de Negócio Críticas

- **Persona Aria:** Colega mais velha, acolhedora, informal. Nunca autoritária.
- **Modo Socrático:** Máximo 2 perguntas guiadas antes da resposta.
- **Mood Check-in:** Se a aluna estiver "cansada", pular socrático e ir direto para a explicação.
- **Classificação de Erros:** Todo erro deve ser classificado em: **Conceitual**, **Interpretação** ou **Atenção**.
- **Anki:** Após cada erro, um flashcard `.apkg` deve ser gerado ou o registro para revisão espaçada atualizado.

---

## Arquitetura de Integração

```
Telegram -> n8n (Webhook)
  -> n8n (Consulta Supabase para perfil/mood)
  -> n8n (Chama Claude para gerar resposta socrática/feedback)
  -> n8n (Salva progresso no Supabase)
  -> n8n (Envia resposta para o Telegram)
```
