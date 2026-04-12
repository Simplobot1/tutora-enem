#!/usr/bin/env bash
# register_webhook.sh — Registra o webhook do Telegram para a URL pública
# Pré-requisitos: TELEGRAM_BOT_TOKEN e FQDN configurados
#
# Uso:
#   export TELEGRAM_BOT_TOKEN="<token>"
#   export FQDN="tutora.example.com"
#   export TELEGRAM_WEBHOOK_SECRET="<secret-opcional>"
#   ./scripts/register_webhook.sh
#
# Verificação posterior:
#   curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo
set -e

: "${TELEGRAM_BOT_TOKEN:?Variável TELEGRAM_BOT_TOKEN não definida}"
: "${FQDN:?Variável FQDN não definida}"

WEBHOOK_URL="https://${FQDN}/webhooks/telegram"

PAYLOAD=$(python3 -c "
import json, os
d = {'url': '${WEBHOOK_URL}', 'allowed_updates': ['message', 'callback_query']}
secret = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
if secret:
    d['secret_token'] = secret
print(json.dumps(d))
")

echo "Registrando webhook em: $WEBHOOK_URL"
RESPONSE=$(curl -s -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

echo "Resposta: $RESPONSE"
echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); exit(0 if d.get('ok') else 1)" \
    && echo "Webhook registrado com sucesso." \
    || (echo "ERRO ao registrar webhook."; exit 1)

echo ""
echo "Verificando registro:"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
