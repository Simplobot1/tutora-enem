from __future__ import annotations

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.me_testa import router as me_testa_router
from app.api.telegram_webhook import router as telegram_router


app = FastAPI(title="Tutora API", version="0.1.0")
app.include_router(health_router)
app.include_router(me_testa_router)
app.include_router(telegram_router)
