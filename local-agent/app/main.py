import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.voice import get_asr_engine, router as voice_router
from app.config import get_settings


def _setup_file_logging() -> None:
    """配置日志同时输出到控制台和文件，便于调试排查错误。"""
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    if not data_dir.is_absolute():
        data_dir = Path.cwd() / data_dir
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "local-agent.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 避免重复添加 handler
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        root_logger.addHandler(console_handler)


_setup_file_logging()

logger = logging.getLogger(__name__)

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


@app.on_event("startup")
async def _warm_up_asr() -> None:
    """Preload ASR engine at startup so the first voice request avoids cold-start latency."""
    try:
        get_asr_engine()
        logger.info("ASR engine warmed up successfully.")
    except Exception:
        logger.warning("ASR engine warm-up skipped (model not configured or missing).")
