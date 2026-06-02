import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.ollama_client import OllamaClient, OllamaClientError
from app.models.schemas import ChatRequest, ChatResponse


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    settings = get_settings()
    client = OllamaClient(settings)

    if request.stream:

        async def event_generator() -> AsyncIterator[str]:
            try:
                async for event in client.chat_stream(request):
                    payload = json.dumps(event.model_dump(), ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            except (OllamaClientError, ValueError) as exc:
                payload = json.dumps(
                    {
                        "type": "error",
                        "request_id": request.request_id,
                        "model": request.model or settings.llm_model,
                        "provider": settings.llm_provider,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        return await client.chat(request)
    except OllamaClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
