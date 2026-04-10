# DEPLOY HETZNER — Checklist Amanhã

**Data:** 2026-04-10
**Próximo passo:** Deploy FastAPI em Hetzner com Docker

---

## 📋 CHECKLIST DEPLOYMENT

### Fase 1: SSH + Servidor Hetzner (5 min)
- [ ] Conectar SSH ao VPS Hetzner
- [ ] Confirmar que tem root/sudo access
- [ ] `apt-get update && apt-get upgrade -y`

### Fase 2: Docker Install (10 min)
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar
docker --version
docker-compose --version
```

### Fase 3: Clone Repo + Build Docker (15 min)
```bash
cd /root
git clone https://github.com/Simplobot1/tutora-enem.git
cd tutora-enem

# Criar Dockerfile
# Criar docker-compose.yml
# Criar .env.production

# Build
docker-compose up -d
```

### Fase 4: CI/CD com GitHub Actions (10 min)
- [ ] Criar `.github/workflows/deploy.yml`
- [ ] Setup: SSH key, Hetzner IP em secrets
- [ ] Test: `git push` → auto deploy

### Fase 5: Registrar Webhook (2 min)
```bash
curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -d "url=https://seu-ip-hetzner/webhooks/telegram"
```

---

## 📦 Arquivos Necessários

### Dockerfile
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ app/
COPY scripts/ scripts/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    restart: always
```

### .github/workflows/deploy.yml
```yaml
name: Deploy to Hetzner
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.HETZNER_SSH_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh -o StrictHostKeyChecking=no root@${{ secrets.HETZNER_IP }} 'cd /root/tutora-enem && git pull && docker-compose up -d'
```

---

## 🔐 Secrets GitHub (Setup)

Adicionar em GitHub → Settings → Secrets:
- `HETZNER_SSH_KEY`: Sua chave SSH privada
- `HETZNER_IP`: IP do VPS Hetzner

---

## ✅ Resultado Final Esperado

```
✅ Docker rodando em Hetzner
✅ URL permanente (seu IP/domínio)
✅ Webhook Telegram ativo
✅ CI/CD automático (git push → deploy)
✅ Testes rodando antes de deploy
```

---

## 🎯 Tempo Total: ~45 min

**Ready para amanhã!** 🚀
