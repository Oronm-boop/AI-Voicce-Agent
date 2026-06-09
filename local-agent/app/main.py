from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.voice import router as voice_router
from app.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-only MVP backend for the desktop voice task agent.",
)

# The server only binds to 127.0.0.1, so network-level security is already
# enforced. Using allow_origins=["*"] avoids origin-mismatch issues between
# localhost and 127.0.0.1 (browsers treat them as different origins).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
app.include_router(tasks_router)
app.include_router(settings_router)
app.include_router(voice_router)
