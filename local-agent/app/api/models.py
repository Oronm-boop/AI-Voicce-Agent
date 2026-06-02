from fastapi import APIRouter

from app.models.ollama_client import OllamaClient
from app.runtime_settings import get_runtime_settings


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
async def model_status() -> dict:
    settings = get_runtime_settings()
    client = OllamaClient(settings)
    return await client.status()
