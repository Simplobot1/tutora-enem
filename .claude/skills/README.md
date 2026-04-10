# 🚀 AIOX Agents Skills

Shortcuts rápidos para ativar os agentes do AIOX com **barra** (`/`).

## Agentes Disponíveis

### 💻 `/dev` — Desenvolvimento
Ativa **@dev** (Dex) para implementação, bugs, refatoração, testes.

**Exemplo:**
```
/dev
Implementar login com Telegram
```

### ✅ `/qa` — Testes e Qualidade
Ativa **@qa** (Quinn) para testes, QA gate, code review.

**Exemplo:**
```
/qa
Rodar QA Gate nessa story
```

### 🏗️ `/architect` — Arquitetura
Ativa **@architect** (Aria) para decisões arquiteturais, tech decisions, design.

**Exemplo:**
```
/architect
Como devemos estruturar o RLS do Supabase?
```

### 📊 `/pm` — Product Manager
Ativa **@pm** (Morgan) para épics, specs, requisitos, roadmap.

**Exemplo:**
```
/pm
*create-epic
```

### ✋ `/po` — Product Owner
Ativa **@po** (Pax) para validação de stories, backlog, priorização.

**Exemplo:**
```
/po
*validate-story-draft
```

### 📖 `/sm` — Scrum Master
Ativa **@sm** (River) para criação de stories, estimativas, planejamento.

**Exemplo:**
```
/sm
*create-story
```

### 🚀 `/devops` — DevOps (EXCLUSIVO)
Ativa **@devops** (Gage) para git push, PRs, CI/CD, deploys.

⚠️ **APENAS @devops pode fazer:**
- `git push`
- Criar/merge de PRs
- Gerenciar MCPs
- Deploy

**Exemplo:**
```
/devops
*push
```

### 🔍 `/analyst` — Análise e Pesquisa
Ativa **@analyst** (Alex) para pesquisa, análise, comparação de soluções.

**Exemplo:**
```
/analyst
Pesquise alternativas de autenticação para Telegram
```

### 🗄️ `/data-engineer` — Banco de Dados
Ativa **@data-engineer** (Dara) para schema, RLS, queries, migrações.

**Exemplo:**
```
/data-engineer
Desenhe a tabela de sessões de estudo
```

---

## Workflow Rápido

### 1. Criar Story
```
/sm
*create-story
```

### 2. Validar
```
/po
*validate-story-draft
```

### 3. Desenvolver
```
/dev
*develop
```

### 4. Testar
```
/qa
*qa-gate
```

### 5. Deploy
```
/devops
*push
```

---

## ⚙️ Como Funciona

Cada skill (`/dev`, `/qa`, etc.) é um atalho que:
1. Ativa o agente correspondente
2. Mostra os comandos disponíveis
3. Aguarda sua pergunta/comando

Depois que o agente está ativo, use `*comando` para executar ações específicas.

---

**Comece agora:** `/dev` para perguntar algo ao Dex!
