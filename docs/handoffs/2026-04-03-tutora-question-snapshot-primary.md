# Handoff 2026-04-03: Tutora `question_snapshot` como fonte primária

## Objetivo
Deixar documentado o problema de modelagem identificado no fluxo da Tutora e o ajuste mínimo recomendado para a próxima sessão.

## Contexto
Durante a revisão do fluxo `me-testa`, ficou claro que a lógica atual ainda trata `questions` no Supabase como caminho principal quando a aluna envia uma questão.

Isso conflita com a direção funcional discutida hoje:
- a aluna manda a própria questão;
- essa questão pode não existir no banco;
- em muitos casos ela nunca vai existir no banco;
- o banco deve ser enriquecimento opcional, não pré-condição do fluxo.

## Problema central
Hoje o fluxo está modelado como:
1. tentar casar a questão enviada com `questions`;
2. se houver match, seguir com `question_id` como fonte de verdade;
3. se não houver match, cair para fallback.

A direção correta para o produto é:
1. tratar o conteúdo enviado pela aluna como fonte primária;
2. montar e persistir um `question_snapshot` canônico;
3. usar `question_id` apenas quando houver match confiável e isso realmente ajudar;
4. nunca depender do banco para o fluxo continuar.

## Evidência da confusão atual no código

### 1. Busca no banco continua sendo a primeira aposta
Em [`scripts/fix_tutora_workflows.py:881`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:881), o node `Busca Questao Curada` sempre tenta consultar `questions`.

### 2. O UUID zero é um sentinela para "não encontrado"
Em [`scripts/fix_tutora_workflows.py:887`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:887), quando `searchable` é falso, o fluxo monta:

```text
id=eq.00000000-0000-0000-0000-000000000000
```

Isso não é a causa do problema; é só um placeholder para forçar resultado vazio.

### 3. A resposta da aluna ainda bifurca por `question_id`
Em [`scripts/fix_tutora_workflows.py:1486`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:1486), o fluxo usa `Tem Question ID Resposta?`.

Se houver `question_id`, ele faz nova busca no banco em [`scripts/fix_tutora_workflows.py:1490`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:1490).

### 4. Feedback e correção ainda dependem da questão buscada no banco
Os ramos de acerto e erro usam dados de `Busca Questao da Sessao`:
- [`scripts/fix_tutora_workflows.py:1534`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:1534)
- [`scripts/fix_tutora_workflows.py:1548`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:1548)
- [`scripts/fix_tutora_workflows.py:1639`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:1639)

Isso mantém a questão do banco como referência principal para:
- explicação;
- gabarito;
- alternativas;
- classificação do erro.

### 5. O socrático já aponta a direção certa
O subfluxo socrático já aceita `question_snapshot` e usa o banco só como apoio:
- [`scripts/fix_tutora_workflows.py:2160`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:2160)
- [`scripts/fix_tutora_workflows.py:2204`](/root/projetos/tutora/scripts/fix_tutora_workflows.py:2204)

Essa parte do desenho está mais próxima do modelo correto.

## Diagnóstico
O sistema hoje mistura dois modelos:

### Modelo A
Questão enviada pela aluna, mas com expectativa de match no banco.

### Modelo B
Questão enviada pela aluna como fonte primária, com banco apenas como reforço opcional.

O produto precisa operar principalmente no Modelo B.

## Consequência prática
Enquanto o fluxo continuar centrado em `question_id`, estes sintomas vão aparecer:
- consultas vazias com UUID placeholder;
- ramos errados quando a questão não existir no banco;
- dificuldade para suportar casos ad hoc;
- revisão/Anki presa a um modelo baseado em `question_id`;
- conflito com a intenção da story `0.4`, que já pressupõe contexto sem `question_id` obrigatório.

## Fix recomendado para a próxima sessão

### Objetivo do refactor
Fazer `question_snapshot` virar a fonte primária do `me-testa`.

### Regra desejada
- sempre que a aluna mandar uma questão, montar um `question_snapshot` canônico;
- persistir esse snapshot na sessão;
- usar `question_id` apenas se houver match confiável;
- não travar o fluxo quando `question_id` for `null`.

### Refactor mínimo sugerido
1. Ajustar a criação/curadoria da sessão para sempre persistir `question_snapshot`, mesmo quando houver `bank_match`.
2. Mudar a normalização da resposta para depender primeiro de `question_snapshot` e só secundariamente de `question_id`.
3. Remover a dependência obrigatória do node `Busca Questao da Sessao` para corrigir e explicar.
4. Fazer os ramos de acerto/erro lerem:
   - `question_snapshot.correct_alternative`
   - `question_snapshot.alternatives`
   - `question_snapshot.content`
   - `question_snapshot.explanation`
5. Deixar `Busca Questao da Sessao` apenas como enriquecimento opcional quando existir `question_id`.
6. Alinhar o pós-erro e a revisão futura para trabalhar com snapshot/contexto, não só com `question_id`.

## Ordem prática de implementação amanhã
1. Revisar os nodes da curadoria inicial e garantir persistência de `question_snapshot` em todos os casos.
2. Refatorar o bloco da resposta da aluna:
   - `Normaliza Resposta`
   - `Tem Question ID Resposta?`
   - `Busca Questao da Sessao`
   - `Resposta Correta?`
   - `Classifica Erro`
   - `Explicacao Direta`
3. Reaproveitar o padrão já usado no socrático para normalizar contexto híbrido (`question_id` + `question_snapshot`).
4. Atualizar testes para validar que o fluxo continua funcionando com `question_id = null`.

## Critério de aceite técnico para esse ajuste
- o fluxo consegue corrigir uma resposta usando apenas o conteúdo enviado pela aluna e o snapshot persistido;
- `question_id` deixa de ser requisito para feedback, classificação e explicação;
- o banco continua opcional e útil, mas não bloqueia a jornada;
- a base fica pronta para a story `0.4` trabalhar `concept_card` sobre contexto real de erro.

## Observação importante
O UUID `00000000-0000-0000-0000-000000000000` não é o problema principal. Ele é só um sintoma da modelagem atual, que ainda assume o banco como centro do fluxo. Corrigir apenas esse placeholder sem inverter a prioridade da fonte de verdade não resolve a raiz.

