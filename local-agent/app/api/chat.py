from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.ollama_client import OllamaClient, OllamaClientError
from app.models.schemas import ChatRequest, ChatResponse


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    client = OllamaClient(settings)

    try:
        return await client.chat(request)
    except OllamaClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
