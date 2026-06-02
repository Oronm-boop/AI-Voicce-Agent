import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.task_planner import TaskPlanError
from app.agent.workflow import run_agent_workflow, stream_agent_workflow
from app.models.ollama_client import OllamaClient, OllamaClientError
from app.models.schemas import ChatRequest, ChatResponse
from app.runtime_settings import get_runtime_settings


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    settings = get_runtime_settings()
    client = OllamaClient(settings)

    if request.stream:

        async def event_generator() -> AsyncIterator[str]:
            try:
                async for event in stream_agent_workflow(settings, client, request):
                    payload = json.dumps(
                        event.model_dump(),
                        ensure_ascii=False,
                        default=str,
                    )
                    yield f"data: {payload}\n\n"
            except (OllamaClientError, TaskPlanError, ValueError) as exc:
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
        return await run_agent_workflow(settings, client, request)
    except OllamaClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TaskPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
