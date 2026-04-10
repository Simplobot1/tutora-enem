# 🚀 AIOX Quick Start — Tutora ENEM

## Como Chamar os Agentes

### ✅ Forma 1: Com Barra (RECOMENDADO)

```
/dev

/qa

/architect

/pm

/po

/sm

/devops

/analyst

/data-engineer
```

**Exemplo:**
```
/dev
Implementar a feature de login
```

### ✅ Forma 2: Com @mention (também funciona)

```
@dev

@qa

@architect

@pm

@po

@sm

@devops

@analyst

@data-engineer
```

**Exemplo:**
```
@dev
Implementar a feature de login
```

## Comandos Disponíveis

### Por Agente

#### @dev (Dex) — Implementação
```
*help                    # Ver comandos
*develop                 # Iniciar desenvolvimento
*code-review             # Revisar código
*fix-tests              # Corrigir testes
```

#### @qa (Quinn) — Testes e QA
```
*qa-gate                # Gate de qualidade
*qa-loop                # Loop iterativo de QA
*qa-loop-review         # Revisar QA
*qa-loop-fix            # Corrigir issues de QA
```

#### @architect (Aria) — Arquitetura
```
*design                 # Propor design
*architecture-review    # Revisar arquitetura
*tech-decision          # Decisão técnica
```

#### @sm (River) — Scrum Master / Story Creation
```
*draft                  # Criar story draft
*create-story           # Criar nova story
*estimate               # Estimar story
```

#### @po (Pax) — Product Owner
```
*validate-story-draft   # Validar story
*prioritize             # Priorizar backlog
*requirements           # Escrever requisitos
```

#### @pm (Morgan) — Product Manager
```
*create-epic            # Criar epic
*execute-epic           # Executar epic
*spec                   # Escrever spec
```

#### @devops (Gage) — CI/CD e Git (EXCLUSIVO)
```
*push                   # Git push (APENAS @devops)
*pr-create              # Criar PR (APENAS @devops)
*ci-status              # Ver status CI
*deploy                 # Deploy (se configurado)
```

---

## 📋 Workflow Típico

### 1️⃣ Criar Story (Story Development Cycle)

```
@sm
*create-story

(responda as perguntas sobre:
 - Que epic pertence?
 - Qual é a descrição?
 - Critérios de aceitação?)
```

### 2️⃣ Validar Story

```
@po
*validate-story-draft

(checklist 10-pontos é executado automaticamente)
```

### 3️⃣ Implementar

```
@dev
*develop

(escolha modo: interactive/yolo/pre-flight)
```

### 4️⃣ QA Gate

```
@qa
*qa-gate

(verifica 7 critérios de qualidade)
```

### 5️⃣ Push (se PASSOU)

```
@devops
*push

(git add + commit + git push)
```

---

## 🔗 MCP Customizado: n8n

Você tem um MCP **n8n** configurado:

```
# Criar/atualizar workflow n8n
/create-workflow

# Exemplos:
/create-workflow meu-workflow-inicial
/create-workflow {"name": "tutora-socrático", "nodes": [...]}
```

---

## 🎯 Próximos Passos

1. **Teste um agente simples:**
   ```
   @architect
   Que tecnologias vocês recomendam para o bot Telegram da Tutora?
   ```

2. **Crie uma story:**
   ```
   @sm
   *create-story
   ```

3. **Veja o status do projeto:**
   ```
   Qual é o status do projeto agora?
   (AIOX carrega automaticamente a visão do projeto)
   ```

---

## 📚 Documentação Completa

- **Constitution (Inegociável):** `.aiox-core/constitution.md`
- **Agent Authority:** `.claude/rules/agent-authority.md`
- **Workflow Execution:** `.claude/rules/workflow-execution.md`
- **Stories:** `docs/stories/`

---

## ⚠️ Regras Críticas

| Regra | Quem | Comando |
|-------|------|---------|
| Git Push | APENAS @devops | `@devops *push` |
| Criar Epic | APENAS @pm | `@pm *create-epic` |
| Validar Story | APENAS @po | `@po *validate-story-draft` |
| Criar Story | APENAS @sm | `@sm *create-story` |

---

**Tudo pronto! Comece a usar os agentes agora! 🎉**
