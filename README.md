# Tutora ENEM

Reconstrução da Tutora como backend Python orientado a webhook, sem `n8n` no caminho crítico.

## Estrutura inicial

- `app/main.py`: FastAPI app
- `app/api/`: endpoints HTTP
- `app/domain/`: estados e modelos
- `app/services/`: regra de aplicação
- `app/adapters/`: integrações externas
- `app/jobs/`: jobs operacionais
- `app/cli/`: comandos operacionais

## Execução

Instale dependências e rode a API:

```bash
uvicorn app.main:app --reload
```

## Estado atual

Este é o primeiro corte da reconstrução:

- webhook do Telegram criado
- intake normalizado
- sessão em memória para bootstrap
- fluxo inicial do `me-testa` em código
- integração real com Supabase/Claude ainda será ligada nos próximos cortes
