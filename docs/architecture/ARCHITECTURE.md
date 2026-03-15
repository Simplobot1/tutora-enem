# Arquitetura Técnica: Tutora ENEM

## 1. Stack Tecnológica (MVP)

A arquitetura foi simplificada para priorizar velocidade de entrega e baixo custo de manutenção, utilizando ferramentas low-code para orquestração e serviços gerenciados para backend.

| Componente | Tecnologia | Papel |
| :--- | :--- | :--- |
| **Orquestrador (Bot)** | **n8n** | Workflows visuais para lógica do Telegram, FSM e integração. |
| **Backend / DB** | **Supabase** | PostgreSQL gerenciado, Auth, Storage e API REST/Edge Functions. |
| **Inteligência Artificial** | **Claude 3.5 Sonnet** | Classificação de erros, dicas socráticas e explicações. |
| **Estado de Sessão** | **n8n Internal** | Gerenciado nativamente pelos workflows do n8n. |
| **Scripts de Apoio** | **Python 3.11+** | Ingestão de dados (NotebookLM), OCR e geração de `.apkg`. |
| **Banco de Questões** | **pgvector (Supabase)** | Busca semântica de questões e materiais de estudo. |

---

## 2. Fluxo de Integração (n8n ↔ Supabase ↔ Claude)

O **n8n** atua como o sistema nervoso central, conectando as pontas:

1.  **Entrada:** Webhook do Telegram recebe mensagem da aluna.
2.  **Contexto:** n8n consulta o perfil e estado emocional da aluna no **Supabase**.
3.  **Raciocínio (Claude API):**
    *   O n8n envia o prompt (Persona Tutora + Histórico + Questão) para o Claude.
    *   Claude retorna a classificação do erro (Conceitual, Interpretação, Atenção) ou a dica socrática.
4.  **Ação:**
    *   n8n salva a resposta/progresso no Supabase.
    *   Se houver erro, dispara script Python para gerar flashcard Anki.
    *   Envia resposta formatada para o Telegram.

---

## 3. Esquema do Banco de Dados (Supabase/PostgreSQL)

### 3.1 Tabela `profiles`
Extensão dos usuários do Supabase Auth.
*   `id`: uuid (PK, references auth.users)
*   `telegram_id`: bigint (unique)
*   `full_name`: text
*   `current_mood`: text (☕️ cansada, ⚡️ normal, 🔋 animada)
*   `preferences`: jsonb (objetivos, temas de interesse)

### 3.2 Tabela `questions`
Banco de questões com suporte a busca semântica.
*   `id`: uuid (PK)
*   `content`: text (enunciado)
*   `options`: jsonb (alternativas A-E)
*   `correct_option`: char(1)
*   `subject`: text (ex: Matemática)
*   `topic`: text (ex: Logaritmos)
*   `difficulty`: int (1-5)
*   `embedding`: vector(1536) (pgvector para busca semântica)
*   `explanation_base`: text (gabarito comentado base)

### 3.3 Tabela `student_responses`
Log de interações para análise pedagógica.
*   `id`: uuid (PK)
*   `profile_id`: uuid (FK)
*   `question_id`: uuid (FK)
*   `selected_option`: char(1)
*   `is_correct`: boolean
*   `error_type`: text (Conceitual, Interpretação, Atenção)
*   `socratic_steps`: int (passos no diálogo socrático)
*   `created_at`: timestamptz

### 3.4 Tabela `srs_queue` (Revisão Espaçada)
*   `id`: uuid (PK)
*   `profile_id`: uuid (FK)
*   `question_id`: uuid (FK)
*   `next_review_at`: timestamptz
*   `interval_days`: int
*   `ease_factor`: float

---

## 4. Estratégia Pedagógica e Tom de Voz

*   **Modo Socrático:** Limite de 2 perguntas guiadas antes de revelar a resposta.
*   **Adaptação por Mood:** Se `current_mood` == 'cansada', o diálogo socratico é ignorado em favor de uma explicação direta e encorajadora.
*   **Persona Aria:** Atua como uma "colega mais velha" — experiente, mas acessível e acolhedora. Evita termos puramente acadêmicos em favor de clareza e conexão.

---

## 5. Próximos Passos de Infraestrutura

1.  **Supabase Setup:** Criar projeto e aplicar migrations iniciais.
2.  **n8n Workflows:** Implementar o webhook básico de recebimento e roteamento.
3.  **Python Ingestion:** Finalizar `scripts/ingest_enem.py` para popular o banco inicial.
4.  **Claude Prompts:** Refinar os system prompts para classificação de erro e pedagogia socrática.
