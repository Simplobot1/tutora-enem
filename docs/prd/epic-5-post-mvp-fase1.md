# Epic 5: Post-MVP Fase 1 — Anki Inline, Perfil de Erros, OCR

## Status
Planning

## Objetivo
Fechar os loops de valor do MVP que ficaram pendentes e adicionar os primeiros diferenciais da Post-MVP Vision.

## Contexto
Com M4 concluído (FastAPI em produção, Docker Swarm no Hetzner, n8n removido do caminho crítico), o próximo passo natural é:
1. Completar o loop do Anki — o deck é preparado mas nunca entregue automaticamente.
2. Expor o perfil de erros acumulado — dado já existe no banco, falta superfície de consulta.
3. Habilitar OCR — permite que a aluna fotografe a questão em vez de digitar.

## Stories

| ID | Título | Prioridade |
|----|--------|------------|
| 5.1 | `.apkg` inline delivery após erro | P0 |
| 5.2 | Perfil de erros acumulado (`/perfil`) | P1 |
| 5.3 | OCR via Claude Vision | P2 |

## Dependências
- M4-S1: ApkgBuilderService ✅
- M4-S3: FastAPI cutover ✅
- M4-S4: Deploy Hetzner ✅

## Acceptance Criteria do Epic
- [ ] Aluna recebe `.apkg` automaticamente no Telegram após cada erro
- [ ] Aluna consegue consultar seus top-3 pontos fracos por tópico
- [ ] Aluna pode fotografar questão e receber correção (OCR)
