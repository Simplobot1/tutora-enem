# Research Report — Tutora ENEM
## Comportamentos, Motivações e Dores do Estudante

**Data:** 2026-03-09
**Tipo:** User & Customer Research
**Status:** Concluído

---

## Executive Summary — 5 Insights Críticos

**✅ VALIDADO — Sessões curtas são o design certo, mas por motivo diferente do esperado**
O problema não é só fadiga cognitiva — é colapso de hábitos. 90,5% dos vestibulandos relatam que o vestibular destruiu sono, vida social e alimentação. Sessões longas amplificam esse colapso. O modelo de 10-15 min não é só pedagógico — é o único formato que sobrevive à vida real do estudante.

**⚠️ RISCO — Check-in emocional é válido, mas a consciência emocional é baixa**
23,5% dos estudantes apresentam ansiedade moderada/severa, e 70% relatam sintomas de depressão — mas a maioria não reconhece estar em estado crítico. O check-in precisa ser ultra-simples e não clínico. "Como você tá hoje?" com 3 emojis funciona melhor do que um formulário de estado emocional.

**✅ VALIDADO — Pressão parental é faca de dois gumes e o relatório semanal precisa ser posicionado com cuidado**
65% dos estudantes se sentem pressionados pelos pais (principalmente via comparação com irmãos). O relatório ao pai precisa ser fraseado como "conquistas da semana", não como "o que ela errou". A percepção de vigilância destrói motivação intrínseca.

**✅ VALIDADO — Telegram como canal tem alta aceitação para estudo**
A plataforma já é usada organicamente para grupos de estudo, canais ENEM e bots educacionais no Brasil. A fricção de adoção é baixa. A objeção principal não é o canal — é a percepção de que "mais uma ferramenta = mais complexidade".

**⚠️ TENSÃO — Diálogo socrático tem risco de frustração se não calibrado**
O método socrático é pedagogicamente sólido, mas estudantes em alta ansiedade têm baixa tolerância para atraso na resposta correta. A regra deve ser: no máximo 2 perguntas socráticas antes de oferecer a explicação. Com estado emocional "cansada", pular direto para explicação.

---

## Persona Refinada

| Campo | Detalhe |
|-------|---------|
| Nome fictício | Sofia, 17 anos |
| Escola | Pública ou particular de médio porte |
| Contexto | Terceirão ou cursinho — primeira ou segunda tentativa |
| Estado base | Ansiosa crônica, autocrítica, sente que "não dá conta de tudo" |
| Rotina real | Dorme mal (73%), come mal (47%), isolamento social (78%) |
| Dispositivo | Smartphone Android, usa Telegram ativamente |
| Plataformas | Conhece Stoodi/Descomplica mas abandona por sobrecarga |
| Relação c/ erro | Baixa consciência metacognitiva — sabe que erra, mas não sabe *por que* erra |
| Flashcards | Conhece Anki, mas adesão é baixa sem reforço externo |

---

## JTBD Map — Jobs-to-be-Done

| Dimensão | Job | Evidência |
|----------|-----|-----------|
| Funcional | "Quero saber exatamente o que cai no ENEM e focar só nisso" | Sobrecarga de conteúdo é gatilho #1 de abandono |
| Funcional | "Quero saber se estou evoluindo sem ter que calcular nada" | Estudantes abandonam plataformas sem feedback de progresso visível |
| Emocional | "Quero estudar sem sentir que estou desperdiçando tempo" | Sensação de ineficácia é maior desmotivador |
| Emocional | "Quero me sentir capaz, não burra" | Tom intimidador = evasão imediata |
| Social | "Quero que meus pais vejam que estou me esforçando" | 65% sentem pressão parental indireta |
| Social | "Quero entrar na faculdade que escolhi, não a que minha família escolheu" | Autonomia na escolha vocacional é fator motivacional crítico |

---

## Padrão Real de Sessões de Estudo

| Campo | Dado |
|-------|------|
| Duração ideal percebida | 25-50 min (Pomodoro é referência cultural) |
| Duração real suportada | 10-20 min sem perda de foco |
| Frequência | Irregular — picos antes de simulados, vácuos após decepções |
| Horários preferidos | Noite (problema: sono já comprometido) |
| Interrupções | Smartphone é causa #1 — paradoxo do canal Telegram |
| Principal gatilho de abandono | Sensação de que "não adiantou nada" |

> **Implicação direta:** o feedback de encerramento da sessão ("Você acertou 4 de 5 hoje — foco em Funções Matemáticas") é tão importante quanto a sessão em si.

---

## Parental Dynamics — Como posicionar o relatório semanal

| | Exemplo |
|-|---------|
| ❌ Framing errado | "Sofia errou 60% das questões de História esta semana" |
| ✅ Framing certo | "Sofia estudou 4 dias esta semana e melhorou 12% em Biologia" |

**Risco principal:** Pai usa dados para cobrar → Sofia percebe bot como ferramenta de vigilância → abandono

**Oportunidade:** Pai usa dados para encorajar → Sofia sente apoio → retenção

**Recomendação MVP:** Relatório só mostra progresso relativo (vs. semana anterior), nunca score absoluto na primeira versão.

---

## Bot Acceptance — Barreiras de Adoção

| Barreira | Intensidade | Resposta do Produto |
|----------|-------------|---------------------|
| "Telegram é pra grupo de amigos, não pra estudo" | Baixa — já existe uso educacional orgânico | Onboarding que normaliza o canal |
| "Vai ser igual ao Stoodi que eu abandonei" | Alta | Primeira sessão entrega valor imediato e é < 5 min |
| "Não quero meu pai vendo tudo que erro" | Alta | Controle explícito: aluna escolhe o que compartilhar |
| "IA não entende minha dúvida de verdade" | Média | Tom acolhedor + "não entendi, pode reformular?" como válvula |
| Custo cognitivo de começar nova ferramenta | Alta | Nenhum cadastro, nenhum formulário — só mandar "oi" |

---

## Estado Emocional × Comportamento Esperado

| Estado | Tolerância à Frustração | Comportamento Típico | Adaptação do Tutora |
|--------|------------------------|---------------------|---------------------|
| Cansada | Muito baixa | Abandona na 1ª dificuldade | Sessão curta, conteúdo fácil, só revisão — pular socrático |
| Normal | Média | Engaja se vê progresso | Rotina padrão, 2 perguntas socráticas |
| Animada | Alta | Quer desafio, fica frustrada com conteúdo fácil | Modo desafio, questões mais difíceis |

---

## Consciência do Tipo de Erro

| Tipo de Erro | Consciência da Aluna | Comportamento | Remediação |
|--------------|---------------------|---------------|------------|
| Conceitual | Quase nunca | "Nunca aprendi isso direito" — erra mesmo sabendo que errou | Explicação em camadas + flashcard + revisão espaçada |
| Interpretação ENEM | Quase nunca | "Eu sabia a matéria mas errei a questão" — confunde com erro conceitual | Treino de leitura de enunciado, não mais conteúdo |
| Atenção | Às vezes | "Fui impulsivo, vi a resposta errada" — auto-percepção de descuido | Feedback imediato + técnica de releitura antes de confirmar |

> **Insight crítico:** a maioria dos estudantes não distingue erro de interpretação de erro de conteúdo. O classificador automático do Tutora entrega algo que nem cursinhos tradicionais entregam — esse é o diferencial de produto mais defensável.

---

## Recomendações Acionáveis para o MVP

1. **Check-in emocional deve ser 1 toque** — 3 emojis, sem texto. A fricção de digitar "estou cansada" é suficiente para pular o check-in.
2. **Primeira mensagem do onboarding deve ser uma questão, não um formulário** — mostrar valor antes de pedir qualquer dado.
3. **Relatório parental precisa de toggle de privacidade** — Sofia precisa confiar que controla o que o pai vê, senão o produto vira ferramenta de controle parental.
4. **Máximo 2 perguntas socráticas por questão** — após 2 tentativas sem acerto, entregar a explicação completa. Tolerância à frustração é baixa em contexto de alta ansiedade.
5. **Feedback de encerramento de sessão é obrigatório no MVP** — "Você estudou X min e acertou Y questões. Seu ponto mais fraco hoje: [tópico]." Sem isso, a sensação de "não adiantou nada" prevalece.
6. **Tom da tutora deve ser de colega mais velha, não de professora** — estudantes em colapso emocional respondem melhor a acolhimento informal do que a autoridade pedagógica.

---

## Resposta à Pergunta de Sucesso

> "O modelo de sessões curtas + check-in emocional + diálogo socrático é o que essa estudante realmente precisa?"

**Sim — com uma ressalva crítica:** o diálogo socrático precisa ser condicionado ao estado emocional. Estudante cansada + socrático longo = abandono. O check-in não é um feature nice-to-have — é o mecanismo que torna todo o resto funcionar.

---

## Sources

- Ansiedade em vestibulandos — SciELO
- Intervenção para stress e ansiedade em pré-vestibulandos — BVSalud
- Pressão familiar às vésperas do ENEM — Lupa
- 70% dos estudantes relatam depressão e ansiedade — Secretaria SP
- SCHOT — Telegram Bot pedagógico — Ceará Científico
- VestCards — Flashcards ENEM
- Como o método socrático engaja os alunos — Editora do Brasil
