# Project Brief: Tutora ENEM

**Data:** 2026-03-09
**Status:** Rascunho
**Versão:** 1.0

---

## Executive Summary

A **Tutora ENEM** é um bot no Telegram que atua como tutora pessoal para estudantes se preparando para o ENEM, oferecendo sessões de estudo de 10-15 minutos, várias vezes ao dia, com foco cirúrgico nos pontos fracos da aluna e no conteúdo com maior probabilidade de cair na prova.

**Problema central:** Estudantes do ENEM sabem que precisam estudar mais, mas colapso emocional, falta de método e sensação de ineficácia destroem a consistência. Plataformas existentes (Stoodi, Descomplica) são abandonadas por sobrecarga de conteúdo e ausência de personalização real.

**Mercado:** Estudantes brasileiros do ensino médio e cursinho preparatório para o ENEM — estimativa de 3-4 milhões de candidatos ativos por ciclo.

**Proposta de valor:** A única tutora que adapta o conteúdo ao seu estado emocional do dia, sabe exatamente onde você erra (e por quê), e mantém o pai informado sem virar ferramenta de vigilância.

---

## Problem Statement

### Estado atual e dores

90,5% dos vestibulandos relatam que a preparação para o ENEM destruiu sono, vida social e alimentação. 23,5% apresentam ansiedade moderada/severa, e 70% relatam sintomas de depressão — mas a maioria não reconhece estar em estado crítico.

O estudante enfrenta três problemas simultâneos:

1. **Sobrecarga de conteúdo** — não sabe o que priorizar; tudo parece urgente
2. **Baixa metacognição** — sabe que erra, mas não sabe *por que* erra; não distingue erro conceitual de erro de interpretação
3. **Colapso de hábitos** — sessões longas não sobrevivem à rotina real; abandona plataformas após a primeira decepção

### Por que soluções existentes falham

- **Plataformas (Stoodi, Descomplica):** Conteúdo abundante mas não personalizado; sem adaptação ao estado emocional; feedback de progresso fraco; sensação de "estou atrasada" constante
- **Cursinhos:** Caros, rígidos, não adaptam ao ritmo individual; não classificam o tipo de erro
- **Grupos de Telegram/WhatsApp:** Sem estrutura pedagógica; ruído alto; não priorizam o que cai no ENEM

### Urgência

O ENEM é anual e a janela de preparação é finita. Cada semana de estudo ineficaz é irreversível para o candidato daquele ciclo.

---

## Proposed Solution

### Conceito central

Um bot no Telegram que funciona como tutora pessoal — disponível a qualquer hora, sem fricção de onboarding, que começa com uma questão (não um formulário) e entrega valor na primeira interação.

### Diferenciadores

| Diferencial | Tutora ENEM | Concorrentes |
|-------------|-------------|--------------|
| Adapta sessão ao estado emocional | ✅ Check-in com 3 emojis | ❌ Sessão sempre igual |
| Classifica tipo de erro automaticamente | ✅ Conceitual / Interpretação / Atenção | ❌ Só certo ou errado |
| Prioriza o que mais cai no ENEM | ✅ Frequência das últimas 10 edições | ⚠️ Parcial |
| Diálogo socrático (não entrega gabarito direto) | ✅ Máx. 2 perguntas | ❌ Gabarito imediato |
| Relatório parental focado em conquistas | ✅ Só progresso relativo, toggle de privacidade | ❌ N/A |
| Revisão espaçada integrada (Anki) | ✅ Automático | ❌ Manual |
| Canal já usado pelo estudante | ✅ Telegram | ❌ App novo a instalar |

### Por que vai funcionar

Sessões de 10-15 min são o único formato que sobrevive à vida real do estudante em colapso de hábitos. O Telegram elimina fricção de adoção. A classificação automática de tipo de erro entrega algo que nem cursinhos tradicionais entregam — esse é o diferencial de produto mais defensável.

---

## Target Users

### Usuário Primário: Sofia (estudante ENEM)

| Campo | Detalhe |
|-------|---------|
| Idade | 16-19 anos |
| Contexto | Terceirão ou cursinho — 1ª ou 2ª tentativa |
| Estado emocional base | Ansiosa crônica, autocrítica |
| Rotina | Dorme mal (73%), come mal (47%), isolamento social (78%) |
| Dispositivo | Smartphone Android, Telegram ativo |
| Relação com erro | Baixa metacognição — sabe que erra, não sabe por quê |
| Histórico de plataformas | Conhece Stoodi/Descomplica, abandonou por sobrecarga |

**Jobs-to-be-done:**
- "Quero saber exatamente o que cai no ENEM e focar só nisso"
- "Quero saber se estou evoluindo sem ter que calcular nada"
- "Quero estudar sem sentir que estou desperdiçando tempo"
- "Quero me sentir capaz, não burra"
- "Quero que meus pais vejam que estou me esforçando"

### Usuário Secundário: Pai/Responsável

Quer acompanhar o progresso da filha sem microgerenciar. Recebe relatório semanal via Telegram. Risco: usar dados para cobrar ao invés de encorajar — o que destrói motivação intrínseca da aluna.

---

## Goals & Success Metrics

### Objetivos de Negócio

- Atingir retenção de 7 dias > 40% (benchmark: apps educacionais ~20%)
- Usuário completa ao menos 3 sessões por semana após onboarding
- NPS > 50 com usuários ativos após 30 dias

### Métricas de Sucesso do Usuário

- Aluna consegue identificar seus 3 maiores pontos fracos na primeira semana
- Taxa de acerto por tópico aumenta ≥ 10% após 30 dias de uso
- Aluna retorna ao bot sem precisar ser lembrada (hábito orgânico)

### KPIs

- **Sessões por semana:** ≥ 3 por usuário ativo
- **Taxa de conclusão de sessão:** ≥ 70% (sessões iniciadas → concluídas)
- **Retenção D7:** > 40%
- **Retenção D30:** > 25%
- **Tempo médio de sessão:** 10-15 min (fora disso = problema de UX)
- **Taxa de erro classificado:** 100% dos erros devem ter tipo atribuído

---

## MVP Scope

### Core Features (Must Have)

- **Onboarding zero-fricção:** primeira mensagem é uma questão, não um formulário; só mandar "oi"
- **Check-in emocional:** 3 botões de emoji (😴 / 😐 / ⚡️); sem texto; obrigatório no início de cada sessão
- **Sessão "me testa":** selector escolhe questões pelo algoritmo de priorização (60% fraquezas / 20% manutenção / 10% novos / 10% revisão); duração 10-15 min
- **Diálogo socrático:** máximo 2 perguntas antes de entregar explicação; pular socrático se estado = cansada
- **Classificação de erro:** conceitual / interpretação ENEM / atenção — em 100% das respostas erradas
- **Explicação em camadas:** o que a questão pede → por que cada alternativa → conceito → conexão interdisciplinar
- **Feedback de encerramento:** "Você estudou X min e acertou Y questões. Ponto mais fraco hoje: [tópico]." — obrigatório
- **Ingestão de PDFs:** extração de questões, alternativas e gabarito
- **Banco de questões:** busca semântica via pgvector quando aluna não sabe o número
- **Flashcard Anki automático:** criado para todo erro, com revisão espaçada (1d → 3d → 7d → 14d)
- **Relatório semanal ao pai:** só progresso relativo (vs. semana anterior), nunca score absoluto; toggle de privacidade controlado pela aluna

### Out of Scope para MVP

- Simulado ENEM cronometrado
- Geração de questões com IA
- Correção de redação
- Modo Feynman
- Dashboard visual / web app
- Plano adaptativo automático
- Onboarding multi-usuário / turmas

### MVP Success Criteria

O MVP é bem-sucedido se uma aluna real consegue: (1) iniciar sem cadastro, (2) completar uma sessão de "me testa" em 10-15 min, (3) receber classificação de erro e explicação em camadas, e (4) o pai recebe relatório semanal com framing positivo. Tudo isso sem nenhuma instrução prévia.

---

## Post-MVP Vision

### Phase 2

- Mapa de frequência ENEM (tópicos com maior histórico nas últimas 10 edições integrado ao selector)
- OCR de foto de questão via Claude Vision
- Áudio: aluna manda áudio com dúvida, tutora responde
- Perfil completo com histórico de erros por tipo e tópico
- Modo Feynman: aluna explica o conceito, tutora avalia

### Long-term Vision (1-2 anos)

Uma plataforma de preparação personalizada para exames brasileiros (ENEM, FUVEST, ENADE) que combina IA pedagógica com dados de desempenho longitudinal — potencialmente licenciável para cursinhos e escolas como backend de personalização.

### Expansion Opportunities

- Outros vestibulares (FUVEST, UNICAMP, concursos públicos)
- Versão para professores (painel de desempenho da turma)
- Marketplace de materiais ingeridos (banco de questões compartilhado)

---

## Technical Considerations

### Platform Requirements

- **Canal:** Telegram (Android e iOS via app nativo)
- **Performance:** Resposta do bot < 3s para mensagens de texto; < 10s para processamento de PDF
- **Disponibilidade:** 99% uptime (o estudo acontece a qualquer hora)

### Technology Stack

| Componente | Tecnologia |
|------------|------------|
| Bot | Python + `python-telegram-bot` |
| IA | Claude API (`claude-sonnet-4-6`) |
| Banco | PostgreSQL + `pgvector` |
| Cache / sessão | Redis |
| Ingestão PDF | `pymupdf` ou `pdfplumber` |
| OCR | Claude Vision (nativo na API) |
| Anki | AnkiConnect (local) ou `.apkg` gerado |
| Infra | Docker Compose (local) / Railway (prod) |

### Architecture Considerations

- Stateless handlers + estado de sessão no Redis (TTL 24h)
- Embeddings de questões no pgvector para busca semântica
- Máquinas de estado para diálogos (socrático, check-in, revisão)
- Relatório semanal via job agendado (cron)

### Security / Compliance

- Toggle de privacidade: aluna controla o que o pai vê
- Dados de desempenho são da aluna, não do pai
- LGPD: dados de menores requerem consentimento do responsável

---

## Constraints & Assumptions

### Constraints

- **Budget:** Projeto pessoal / bootstrapped — custos de API devem ser mínimos por sessão
- **Timeline:** MVP funcional em 8-12 semanas de desenvolvimento solo
- **Resources:** Desenvolvedor solo (full-stack) + Claude API
- **Technical:** Uma aluna específica como usuária inicial — não precisa escalar para milhares no MVP

### Key Assumptions

- A aluna tem acesso ao Telegram e o usa ativamente
- O pai tem Telegram e aceita receber relatórios por lá
- Questões do ENEM em PDF estão disponíveis para ingestão (INEP disponibiliza publicamente)
- Claude API consegue classificar tipo de erro com precisão aceitável (> 80%) sem fine-tuning
- Sessões de 10-15 min são suficientes para aprendizado significativo se frequentes (3-5x/dia)

---

## Risks & Open Questions

### Key Risks

- **Abandono no onboarding:** Se a primeira sessão não entregar valor imediato, a aluna não volta — mitigação: primeira mensagem já é uma questão
- **Classificação de erro incorreta:** Classificar como "conceitual" um erro de "interpretação" leva à remediação errada — mitigação: validar classificador com amostra manual
- **Relatório parental mal usado:** Pai usa dados para pressionar ao invés de encorajar — mitigação: toggle de privacidade + framing positivo obrigatório
- **Custo de API por sessão:** Claude API pode ficar caro com muitas sessões/dia — mitigação: medir custo médio por sessão no MVP e otimizar prompts
- **Qualidade da ingestão de PDF:** PDFs do ENEM têm layouts variados, OCR pode falhar — mitigação: validação manual das primeiras ingestões

### Open Questions

- Qual o custo médio de API por sessão de 10-15 min com Claude Sonnet?
- O AnkiConnect é viável para a aluna ou é mais simples gerar `.apkg`?
- Como lidar com questões de anos diferentes do ENEM com enunciados idênticos ou similares?
- O toggle de privacidade deve ser configurado uma vez ou por relatório?

### Areas Needing Further Research

- Custo de operação (Claude API + Railway + PostgreSQL) por usuário/mês
- Melhores práticas de prompt engineering para classificação de tipo de erro
- Formato ideal do relatório semanal para maximizar engajamento paternal positivo

---

## Appendices

### A. Research Summary

Pesquisa completa disponível em `docs/research/user-research.md`.

**5 insights críticos:**
1. ✅ Sessões curtas são o design certo — é o único formato que sobrevive ao colapso de hábitos
2. ⚠️ Check-in emocional válido, mas consciência emocional é baixa — deve ser 1 toque, 3 emojis
3. ✅ Pressão parental é faca de dois gumes — relatório deve ser fraseado como conquistas
4. ✅ Telegram tem alta aceitação — objeção é "mais uma ferramenta", não o canal
5. ⚠️ Socrático tem risco de frustração — máximo 2 perguntas, pular se estado = cansada

### B. References

- `docs/research/user-research.md` — User & Customer Research completo
- `CLAUDE.md` — Arquitetura, stack, regras de negócio e ordem de desenvolvimento
- INEP — Provas e gabaritos ENEM (públicos)
- SciELO, BVSalud, Secretaria SP — Dados sobre saúde mental de vestibulandos

---

## Next Steps

1. Ativar `@architect` para validar e detalhar decisões de arquitetura técnica
2. Ativar `@data-engineer` para projetar schema definitivo do banco com DDL
3. Ativar `@pm` para transformar este brief em PRD com épicos e histórias
4. Ativar `@sm` para criar as primeiras stories de desenvolvimento (início pelo banco + ingestão)
5. Inicializar repositório git e estrutura de pastas do projeto

---

*Este Project Brief fornece o contexto completo para o Tutora ENEM. Para PRD, acionar @pm com referência a este documento e ao user research em `docs/research/user-research.md`.*
