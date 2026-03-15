# DECISOES TECNICAS — Tutora ENEM

Decisoes ja tomadas. Nao reabrir sem motivo forte.
Ao tomar uma nova decisao importante, registre aqui.

---

## Arquitetura

| Decisao              | Escolha                  | Motivo                                              |
|----------------------|--------------------------|-----------------------------------------------------|
| Bot runtime          | n8n (workflows visuais)  | Ja instalado, sem servidor Python 24/7              |
| Banco                | Supabase                 | Managed Postgres + pgvector nativo, free tier ok    |
| IA runtime           | Claude Sonnet 4.6        | Melhor classificacao de erro pedagogico             |
| Pipeline de conteudo | Python scripts locais    | NotebookLM sem API oficial — uso local apenas       |
| Anki                 | .apkg gerado             | Nao depende do Anki estar aberto                    |
| Redis                | Removido do MVP          | n8n gerencia estado de sessao internamente          |
| Railway              | Removido do MVP          | Supabase cloud + n8n local suficientes para MVP     |
| Embeddings           | vector(1536)             | Compatibilidade com Claude/OpenAI                   |

---

## Pedagogia (regras de negocio — nao alterar)

| Regra                        | Valor                                              |
|------------------------------|----------------------------------------------------|
| Socratico maximo             | 2 perguntas antes de entregar gabarito             |
| Pular socratico se           | mood = cansada                                     |
| Sessao ideal                 | 10-15 minutos                                      |
| Algoritmo de selecao         | 60% fraquezas / 20% manutencao / 10% novos / 10% revisao |
| Corte de prioridade maxima   | < 65% de acerto no topico                          |
| Tom da tutora                | colega mais velha, nunca professora autoritaria    |
| Feedback de encerramento     | obrigatorio — tempo + acertos + ponto mais fraco   |
| Relatorio ao pai             | so progresso relativo, nunca score absoluto        |

---

## NotebookLM

| Uso                          | Como                                               |
|------------------------------|----------------------------------------------------|
| Ingestao de PDFs ENEM        | notebooklm-py local, offline, na sua maquina       |
| Geracao de flashcards base   | .generate_quiz() → JSON → converte para .apkg      |
| Geracao de audio por topico  | .generate_audio() → MP3 → envia no Telegram        |
| Runtime do bot               | NAO usa NotebookLM (autenticacao incompativel)     |
