from fastapi import APIRouter

from app.config import get_settings
from app.models.ollama_client import OllamaClient


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
async def model_status() -> dict:
    settings = get_settings()
    client = OllamaClient(settings)
    return await client.status()
