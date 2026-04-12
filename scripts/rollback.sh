#!/usr/bin/env bash
# rollback.sh — Retorna ao último commit estável taggeado ou commit específico
# Uso: ./scripts/rollback.sh [commit-sha-ou-tag]
set -e

DEPLOY_PATH="${DEPLOY_PATH:-.}"
TARGET="${1:-}"

cd "$DEPLOY_PATH"

if [ -z "$TARGET" ]; then
    # Usa o último commit antes do atual (git log)
    TARGET=$(git log --oneline -2 | tail -1 | awk '{print $1}')
    echo "Nenhum target especificado. Usando: $TARGET"
fi

echo "Iniciando rollback para: $TARGET"
git checkout "$TARGET"
docker build -t tutora-api:latest .
if [ -f docker-stack.traefik.yml ]; then
    docker stack deploy -c docker-stack.traefik.yml tutora
else
    docker compose up -d --build --remove-orphans
fi

echo "Aguardando API..."
for i in $(seq 1 10); do
    HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "Rollback concluído com sucesso. HEAD: $(git rev-parse HEAD)"
        exit 0
    fi
    sleep 3
done

echo "ERRO: API não respondeu após rollback para $TARGET"
exit 1
