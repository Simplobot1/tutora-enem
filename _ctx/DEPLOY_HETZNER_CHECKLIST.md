# DEPLOY HETZNER — Checklist Amanhã

**Data:** 2026-04-10
**Próximo passo:** Deploy FastAPI em Hetzner com Docker

---

## 📋 CHECKLIST DEPLOYMENT (2026-04-11)

**Timeline Total: ~3.5 horas**

### Fase 0: Implementar Fotos/Multimodal (~2h) — ANTES DE DEPLOY
- [ ] **Claude Vision Integration** (20 min)
  - `app/services/photo_ocr_service.py`
  - Recebe `file_id` do Telegram
  - Chama Claude Vision API
  - Retorna texto da questão
  
- [ ] **Supabase Storage** (15 min)
  - Upload foto em `storage.from('questions')`
  - Guarda referência em metadata
  
- [ ] **Multimodal Intake** (25 min)
  - Estender `MeTestaEntryService` para foto
  - Chamar OCR → question_snapshot
  - Mesmo fluxo que texto
  
- [ ] **Tests Multimodal** (30 min)
  - 5-6 testes: foto → OCR → snapshot
  - Validar alternativas extraídas
  - Edge cases (foto ilegível, etc)

- [ ] **Build + Testes locais** (10 min)
  - `python3 -m pytest tests/ -v`
  - Deve ter ~95-100 testes passando

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

## 📝 Arquivos Novos (Multimodal)

### `app/services/photo_ocr_service.py`
```python
class PhotoOCRService:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def extract_question_from_photo(self, file_id: str, telegram_token: str) -> QuestionSnapshot:
        # 1. Download foto do Telegram via file_id
        # 2. Enviar para Claude Vision
        # 3. Retornar question_snapshot com alternativas
        pass
```

### `app/api/me_testa_photo.py` (Novo endpoint)
```python
@router.post("/api/me-testa/photo")
async def intake_photo(
    request: Request,
    file_id: str,  # do Telegram
) -> dict:
    # Recebe foto
    # Chama PhotoOCRService
    # Retorna question_snapshot
    # Processa como texto
    pass
```

### Tests
- `test_photo_ocr_service.py` (5-6 testes)
  - Photo → Claude Vision → snapshot
  - Valida alternativas extraídas
  - Edge cases (ilegível, etc)

---

## ✅ Resultado Final Esperado

```
✅ Código local: texto + FOTOS funcionando
✅ ~95-100 testes passando
✅ Docker rodando em Hetzner
✅ URL permanente (seu IP/domínio)
✅ Webhook Telegram ativo (texto + fotos)
✅ CI/CD automático (git push → deploy)
✅ SISTEMA COMPLETO em produção
```

---

## 🎯 Tempo Total: ~3.5 horas

**Breakdown:**
- Fase 0 (Multimodal): ~2h
- Fase 1-5 (Deploy): ~1.5h

**Ready para amanhã!** 🚀
