Crie ou atualize um workflow no n8n usando o MCP `n8n`.

Entrada do usuário: `$ARGUMENTS`

Procedimento:

1. Use `healthCheck` para validar conectividade do n8n.
2. Se o usuário pediu apenas criação por nome, use `createWorkflow` com um payload mínimo contendo:
   - `name`
   - `nodes: []`
   - `connections: {}`
   - `settings: {}`
3. Se o usuário forneceu JSON de workflow, envie o objeto completo em `workflow`.
4. Resuma o `id`, `name` e o status final criado/atualizado.
5. Se faltar `N8N_BASE_URL` ou `N8N_API_KEY`, explique exatamente qual variável está ausente.
