# Skills da Tutora ENEM (Toolbox)

Estas são as funções (tools) que a IA pode "chamar" para realizar ações no mundo real e acessar dados dinâmicos.

---

## 1. Skill: `get_next_question`
Permite à IA buscar a questão mais relevante para o momento atual da Sofia.
*   **Parâmetros:**
    *   `subject` (opcional): Filtro por matéria (ex: Matemática).
    *   `difficulty_target` (opcional): Nível de 1 a 5.
    *   `is_revision` (booleano): Se deve buscar algo do banco de SRS.
*   **Uso:** A IA chama isso após o check-in emocional para iniciar a sessão.

---

## 2. Skill: `log_user_answer`
Registra a resposta e a análise da IA no banco de dados.
*   **Parâmetros:**
    *   `question_id`: ID da questão respondida.
    *   `selected_option`: A letra escolhida pela Sofia.
    *   `is_correct`: Se ela acertou.
    *   `error_type`: (Conceitual, Interpretação, Atenção).
    *   `socratic_steps`: Quantas interações foram necessárias.
*   **Uso:** Essencial para alimentar o motor de progresso e o relatório parental.

---

## 3. Skill: `schedule_srs_review`
Agenda quando a Sofia deve ver essa questão novamente.
*   **Parâmetros:**
    *   `question_id`: ID da questão.
    *   `performance_score`: 1 (errou feio) a 5 (acertou de primeira rápido).
*   **Uso:** Chamada automaticamente após a conclusão de uma interação de questão.

---

## 4. Skill: `get_student_stats`
Permite que a IA responda perguntas do tipo "Como eu estou indo em Biologia?".
*   **Parâmetros:**
    *   `time_range`: (semana, mes, total).
*   **Retorno:** JSON com % de acerto por matéria e pontos fracos.
*   **Uso:** Para a IA dar feedbacks motivacionais baseados em fatos.

---

## 5. Skill: `search_theory_snippet`
Se a Sofia estiver muito travada, a IA pode buscar uma explicação teórica curta (pílula de conhecimento) no banco de dados.
*   **Parâmetros:**
    *   `topic`: O assunto específico (ex: "Leis de Newton").
*   **Uso:** Parte do diálogo socrático quando a dica socrática não for suficiente.

---

## 6. Skill: `update_mood_log`
Registra o estado emocional diário.
*   **Parâmetros:**
    *   `mood_emoji`: ☕️, ⚡️ ou 🔋.
    *   `user_comment` (opcional): O que a Sofia escreveu além do emoji.
*   **Uso:** Para gerar o gráfico de "Estado Emocional vs. Performance" no futuro.

---

## Como isso funciona tecnicamente?

1.  A Sofia manda uma mensagem.
2.  A IA (Gemini/Claude) analisa e decide: *"Para responder a isso, eu preciso da Skill `get_student_stats`"*.
3.  O nosso backend (FastAPI) executa a query no PostgreSQL.
4.  O backend devolve o resultado para a IA.
5.  A IA formula a resposta final: *"Sofia, você está arrasando em Natureza (80% de acerto), mas vamos focar um pouco mais em Física amanhã?"*.
