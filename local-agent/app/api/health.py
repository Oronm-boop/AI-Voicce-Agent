from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "0.1.0",
        "time": datetime.now(timezone.utc).isoformat(),
        "llm_provider": settings.llm_provider,
        "allow_remote_llm": settings.allow_remote_llm,
    }
