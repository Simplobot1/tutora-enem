# GUIA DE AGENTES — Tutora ENEM

Pasta compartilhada entre todos os agentes e modelos.
Antes de comecar qualquer tarefa: leia ESTADO.md e HANDOFF.md.
Ao terminar: atualize ESTADO.md e escreva em HANDOFF.md.

---

## Mapa de Agentes x LLMs

| Agente   | Persona  | LLM              | Ferramenta      | Responsabilidade principal         |
|----------|----------|------------------|-----------------|------------------------------------|
| @dev     | Dex      | Claude Sonnet 4.6| Claude Code WSL | Escrever e revisar codigo          |
| @architect | Aria   | Gemini Pro       | Gemini CLI      | Decisoes de arquitetura            |
| @data-engineer | Dara | Gemini Pro   | Gemini CLI      | Schema SQL, queries, migrations    |
| @pm      | Morgan   | Gemini Flash     | Gemini CLI      | Epicos, PRD, requisitos            |
| @po      | Pax      | Gemini Flash     | Gemini CLI      | Validacao de stories               |
| @sm      | River    | Gemini Flash     | Gemini CLI      | Criacao de stories                 |
| @qa      | Quinn    | Gemini Flash     | Gemini CLI      | Revisao de qualidade e testes      |
| @analyst | Alex     | Gemini Pro       | Gemini CLI      | Pesquisa, analise de dados         |
| @devops  | Gage     | Gemini Flash     | Gemini CLI      | Git, deploy, infraestrutura        |

---

## Como ativar cada agente

### @dev — Claude Code (WSL) — UNICO que usa Claude
```bash
# Terminal WSL no projeto:
cd /root/projetos/tutora
claude
# Dentro do Claude Code digite:
/AIOX:agents:dev
```

### Todos os outros — Gemini CLI (ja instalado)
```bash
# Terminal WSL no projeto:
cd /root/projetos/tutora
gemini
# Dentro do Gemini CLI digite:
/AIOX:agents:architect      # para @architect
/AIOX:agents:data-engineer  # para @data-engineer
/AIOX:agents:pm             # para @pm
/AIOX:agents:po             # para @po
/AIOX:agents:sm             # para @sm
/AIOX:agents:qa             # para @qa
/AIOX:agents:analyst        # para @analyst
/AIOX:agents:devops         # para @devops
```

---

## Protocolo de comunicacao entre agentes

```
1. ANTES de comecar  → leia: _ctx/ESTADO.md + _ctx/HANDOFF.md
2. DURANTE           → escreva decisoes em: _ctx/DECISOES.md
3. AO TERMINAR       → atualize: _ctx/ESTADO.md
4. PARA O PROXIMO    → escreva em: _ctx/HANDOFF.md
```

---

## Fluxo padrao de desenvolvimento (Story Development Cycle)

```
@sm  (Gemini Flash) → cria story         → docs/stories/
@po  (Gemini Flash) → valida story       → aprova ou rejeita
@dev (Claude)       → implementa         → codigo + testes
@qa  (Gemini Flash) → revisa qualidade   → aprovado ou correcoes
@devops (Gemini)    → git commit + push  → branch pronta
```

---

## Supabase CLI

```bash
# Inicializar projeto (uma vez):
npx supabase init

# Login:
npx supabase login

# Linkar ao projeto remoto (apos criar no dashboard):
npx supabase link --project-ref SEU_PROJECT_REF

# Rodar migrations:
npx supabase db push

# Ver status das migrations:
npx supabase migration list

# Abrir studio local:
npx supabase start
```

---

## Materiais de estudo (onde colocar os PDFs)

```
materiais/
  provas/     → PDFs das provas ENEM (baixe em: inep.gov.br)
  gabaritos/  → PDFs dos gabaritos oficiais
  livros/     → Livros didaticos (opcional)
  audio/      → MP3s gerados pelo NotebookLM (por topico)
```

---

## NotebookLM — uso offline

```bash
# Instalar (uma vez):
pip install "notebooklm-py[browser]"
playwright install chromium

# Autenticar (uma vez, abre o browser):
notebooklm login

# Gerar flashcards de um PDF:
python scripts/generate_flashcards.py --pdf materiais/provas/enem_2023.pdf

# Gerar audio de um topico:
python scripts/generate_audio.py --topic "Genetica"
```
