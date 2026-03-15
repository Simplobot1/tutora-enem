# PRD - Tutora ENEM v1.0

## 1. Visão Geral
A **Tutora ENEM** é uma assistente pessoal via Telegram focada em micro-estudos (10-15 min) e suporte emocional para vestibulandos. O diferencial é a **hiper-personalização** baseada em:
1. Estado emocional do dia.
2. Análise pedagógica de tipos de erro (conceitual vs. interpretação).
3. Priorização estatística (o que mais cai no ENEM).

---

## 2. Personas e Público-Alvo
### 2.1 Primário: Sofia (16-19 anos)
*   **Perfil:** Estudante de 3º ano ou cursinho.
*   **Dores:** Ansiedade, sensação de "atrasada", dificuldade em manter rotina.
*   **Objetivo:** Consistência e clareza sobre o que priorizar.

### 2.2 Secundário: Pais (Decisores Financeiros)
*   **Perfil:** Preocupados com o futuro, mas querem evitar conflito direto sobre estudos.
*   **Objetivo:** Saber que o investimento está gerando engajamento e progresso, sem monitoramento invasivo.

---

## 3. User Journey (Jornada do Usuário)

### Fase 1: Onboarding "Zero Fricção"
1.  Usuário clica no link do bot.
2.  Bot: "Oi! Sou a Tutora. Vamos ver como você está hoje? ☕️/⚡️/🔋 (Check-in rápido)".
3.  Primeira questão do ENEM enviada imediatamente (sem formulários longos).

### Fase 2: Sessão Diária (Loop de Retenção)
1.  **Check-in Emocional:** 3 emojis para definir o "mood" (Ansiosa, Cansada, Pronta).
2.  **Ajuste de Carga:** Se "Cansada", o bot reduz a dificuldade ou foca em revisão leve.
3.  **Diálogo Socrático:** O bot não dá a resposta. Se errar, ele pergunta: "O que você acha que aconteceu aqui? Faltou saber o conceito ou foi a leitura?".
4.  **Fechamento:** Resumo da conquista do dia e convite para a próxima sessão.

### Fase 3: Relatório Parental (Confiança)
1.  Relatório semanal enviado aos pais/responsáveis.
2.  **Foco em Esforço e Progresso:** "Sofia completou 5 sessões de Matemática e superou 12 desafios esta semana!".
3.  **Privacidade:** Notas específicas e erros não são detalhados para os pais, preservando o espaço seguro do estudante.

---

## 4. Requisitos Funcionais

### RF01: Mecanismo de Check-in Emocional
*   O sistema deve solicitar o estado emocional antes de cada sessão.
*   A IA deve adaptar o tom de voz e a seleção de questões com base nesse estado.

### RF02: Classificador de Tipo de Erro
*   Ao errar, o bot deve interagir para classificar o erro em: **Conceitual**, **Interpretação** ou **Atenção**.
*   O sistema deve gerar estatísticas sobre qual tipo de erro é predominante para cada tópico.

### RF03: Motor de Diálogo Socrático
*   O bot deve ser instruído a dar dicas (máximo 2) antes de revelar o gabarito comentado.
*   O objetivo é levar o aluno a perceber o erro sozinho.

### RF04: Revisão Espaçada (SRS)
*   Questões erradas devem ser agendadas para revisão automática seguindo a lógica de repetição espaçada.

### RF05: Relatório de Conquistas (Pais)
*   Dashboard ou mensagem formatada para pais com métricas de engajamento (horas, sessões, tópicos concluídos).

---

## 5. Requisitos Não-Funcionais

### RNF01: Latência
*   Respostas da IA no Telegram não devem demorar mais de 3 segundos para começar a ser digitadas.

### RNF02: Privacidade (LGPD)
*   Dados sensíveis do estudante (emoções, notas exatas) devem ter um *toggle* de privacidade antes de serem compartilhados com terceiros.

### RNF03: Disponibilidade
*   O bot deve operar 24/7, com tempo de resposta consistente.

---

## 6. Métricas de Sucesso (KPIs)
1.  **Retenção D7:** % de alunos que voltam ao bot após 7 dias do onboarding.
2.  **Precisão da Classificação:** % de erros classificados corretamente pela IA (validado por amostragem).
3.  **Engajamento Diário:** Média de sessões completadas por usuário ativo por semana.

---

## 7. MVP Scope (O que faremos agora)
1.  Integração básica Telegram + LLM (OpenAI/Gemini).
2.  Banco de dados com as 200 questões mais frequentes do ENEM.
3.  Fluxo de check-in emocional -> 1 questão -> classificação de erro.
4.  Relatório semanal simples em formato de texto.
