# Handoff 2026-04-03: Validacao dos fluxos da Tutora

## Objetivo
Registrar o estado real dos fluxos testados hoje no n8n e deixar claro o ponto exato de retomada para a proxima semana.

## Resultado do dia
Os dois caminhos principais do workflow `me-testa` foram testados manualmente e ficaram funcionais:

1. `bank_match`
2. `student_submitted`

Tambem foi validada a persistencia do pacote de revisao/Anki em `study_sessions.metadata` nos dois cenarios.

## O que ficou funcionando

### 1. Questao no banco (`bank_match`)
- Questao enviada em texto completo consegue bater no banco.
- O ajuste de curadoria deixou de bloquear a busca so porque a questao ja veio estruturada.
- Questoes em espanhol deixaram de ser descartadas por um gate de idioma excessivamente restritivo.
- O fluxo de acerto e erro voltou a funcionar com `question_id` valido.
- No erro, a sessao passa a persistir:
  - `metadata.state = DONE`
  - `metadata.source_mode = bank_match`
  - `metadata.question_id`
  - `metadata.question_snapshot`
  - `metadata.question_ref`
  - `metadata.review_card`
  - `metadata.anki`
  - `metadata.anki_status = queued_local_build`
- O `builder_mode` ficou correto como `question_id`.

### 2. Questao enviada pela aluna (`student_submitted`)
- O fallback multimodal conseguiu resolver questao fora do banco usando `question_snapshot`.
- O fluxo foi separado do caminho do banco para evitar cruzamento de ramos.
- Foi criado um IF exclusivo para esse caminho:
  - `Fallback Resolvido?`
  - `Resposta Correta Fallback?`
- No erro, a sessao passou a persistir:
  - `metadata.state = DONE`
  - `metadata.source_mode = student_submitted`
  - `metadata.question_id = null`
  - `metadata.question_snapshot`
  - `metadata.question_ref`
  - `metadata.review_card`
  - `metadata.anki`
  - `metadata.anki_status = queued_local_build`
- O `builder_mode` ficou correto como `review_card`.

## Evidencia validada em banco

### `bank_match`
Foi observado `study_sessions.metadata` com:
- `source_mode = bank_match`
- `question_id` preenchido
- `review_card` preenchido
- `anki.status = queued_local_build`
- `anki.builder_mode = question_id`

### `student_submitted`
Foi observado `study_sessions.metadata` com:
- `source_mode = student_submitted`
- `question_id = null`
- `question_snapshot` preenchido
- `review_card` preenchido
- `anki.status = queued_local_build`
- `anki.builder_mode = review_card`

## Problemas encontrados e tratados hoje

### 1. Curadoria inicial bloqueando busca no banco
O node `Curadoria Entrada` marcava `searchable = false` quando a questao vinha estruturada.

Efeito:
- a questao nao era realmente buscada no banco;
- o fluxo caia em fallback mesmo quando o item existia.

Direcao aplicada:
- separar enunciado das alternativas;
- manter a busca no banco mesmo para texto estruturado.

### 2. Gate de idioma descartando questoes validas
O node `Curadoria Match` descartava candidatos que nao parecessem portugues.

Efeito:
- questoes em espanhol eram rejeitadas mesmo existindo no banco.

Direcao aplicada:
- flexibilizacao do gate para aceitar conteudo PT/ES e rejeitar apenas sinais ruins.

### 3. Questoes com `correct_alternative = 'X'`
Foram encontrados registros de teste com placeholder `X`.

Efeito:
- qualquer resposta da aluna seria tratada como errada;
- o fluxo confundia problema de dado com problema de logica.

Acao:
- limpeza dos registros de teste no banco;
- confirmacao da causa raiz em `scripts/ingest_enem.py`.

### 4. Erro estrutural no fallback
O mesmo IF de `Resposta Correta?` estava sendo compartilhado entre banco e fallback.

Efeito:
- o ramo `false` disparava os dois tratamentos de erro.

Acao:
- separacao do fallback em um IF proprio: `Resposta Correta Fallback?`

## O que ainda nao foi fechado

### 1. Geracao real de Anki
Hoje o fluxo termina em:
- `metadata.anki.status = queued_local_build`

Mas ainda nao foi validado o caminho completo:
- rodar `scripts/build_pending_apkgs.py`
- gerar `.apkg`
- persistir `flashcards`

Consequencia:
- `flashcards` ainda pode aparecer vazio mesmo com `review_card` e `anki` corretos na sessao.

### 2. Sincronizacao repo -> n8n
Boa parte dos ajustes foi feita manualmente no n8n durante a sessao.

Risco:
- drift entre o workflow publicado e o builder local em `scripts/fix_tutora_workflows.py`

### 3. Rotacao da chave `service_role`
A chave do Supabase apareceu exposta durante os testes.

Acao obrigatoria:
- girar a `service_role` key antes de continuar trabalho real.

### 4. Pagamento via Telegram
Ficou combinado deixar isso para a proxima fase.

Direcao ja definida:
- pagamento sera direto no Telegram via `AccessManager`
- nao ha necessidade de grupo neste momento
- sera preciso desenhar o fluxo de acesso e assinatura depois

## Ponto exato de retomada
Na proxima semana, retomar por esta ordem:

1. Rotacionar a `service_role` key do Supabase.
2. Validar o builder de Anki ponta a ponta:
   - `scripts/build_pending_apkgs.py`
   - `scripts/apkg_builder.py`
   - persistencia em `flashcards`
3. Consolidar no codigo do repo os ajustes feitos manualmente no n8n.
4. Desenhar a proxima fase:
   - integracao de pagamento via `AccessManager`
   - estrategia de acesso apos pagamento
   - impacto em `bot_users` e possivel tabela de assinatura/acesso

## Regra pratica para a proxima sessao
- Nao reabrir o debug de roteamento dos fluxos principais.
- Os dois caminhos (`bank_match` e `student_submitted`) ja foram validados funcionalmente.
- O foco agora deve sair de roteamento e ir para:
  - persistencia final do Anki
  - consolidacao do codigo
  - desenho do pagamento
