from functools import lru_cache
from typing import AsyncIterator, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.task_planner import (
    TaskPlanError,
    build_task_plan_request,
    parse_task_plan,
    should_create_task_plan,
)
from app.config import Settings
from app.models.ollama_client import OllamaClient
from app.models.schemas import (
    AgentWorkflowEvent,
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    TaskItem,
    TaskPlan,
    WorkflowStatus,
)
from app.storage.tasks import create_tasks


AgentIntent = Literal["chat", "task_plan"]


class AgentWorkflowState(TypedDict, total=False):
    request: ChatRequest
    settings: Settings
    client: OllamaClient
    intent: AgentIntent
    reply: str
    model: str
    provider: str
    task_plan: TaskPlan
    tasks_created: list[TaskItem]
    workflow_events: list[AgentWorkflowEvent]


def _event(step: str, status: WorkflowStatus, message: str) -> AgentWorkflowEvent:
    return AgentWorkflowEvent(step=step, status=status, message=message)


def _append_event(
    state: AgentWorkflowState,
    step: str,
    status: WorkflowStatus,
    message: str,
) -> list[AgentWorkflowEvent]:
    return [*state.get("workflow_events", []), _event(step, status, message)]


def _stream_event(
    request: ChatRequest,
    settings: Settings,
    step: str,
    status: WorkflowStatus,
    message: str,
) -> ChatStreamEvent:
    return ChatStreamEvent(
        type="workflow",
        request_id=request.request_id,
        model=request.model or settings.llm_model,
        provider=settings.llm_provider,
        workflow_step=step,
        workflow_status=status,
        message=message,
    )


async def _understand_request(state: AgentWorkflowState) -> AgentWorkflowState:
    request = state["request"]
    intent: AgentIntent = "task_plan" if should_create_task_plan(request) else "chat"
    message = (
        "已识别为任务规划请求，准备拆解步骤。"
        if intent == "task_plan"
        else "已识别为普通对话请求。"
    )
    return {
        "intent": intent,
        "workflow_events": _append_event(
            state,
            "understand_request",
            "completed",
            message,
        ),
    }


async def _assistant_reply(state: AgentWorkflowState) -> AgentWorkflowState:
    request = state["request"]
    client = state["client"]
    response = await client.chat(request)
    return {
        "reply": response.reply,
        "model": response.model,
        "provider": response.provider,
        "workflow_events": _append_event(
            state,
            "assistant_reply",
            "completed",
            "已生成面向用户的回复。",
        ),
    }


async def _generate_task_plan(state: AgentWorkflowState) -> AgentWorkflowState:
    request = state["request"]
    client = state["client"]
    plan_request = build_task_plan_request(request)
    response = await client.chat(plan_request)
    plan = parse_task_plan(response.reply)
    return {
        "task_plan": plan,
        "workflow_events": _append_event(
            state,
            "generate_task_plan",
            "completed",
            f"已生成 {len(plan.tasks)} 个候选任务。",
        ),
    }


async def _write_tasks(state: AgentWorkflowState) -> AgentWorkflowState:
    settings = state["settings"]
    plan = state.get("task_plan")
    if not plan:
        raise TaskPlanError("Task plan is missing before write_tasks.")

    tasks_created = create_tasks(settings, plan.tasks)
    return {
        "tasks_created": tasks_created,
        "workflow_events": _append_event(
            state,
            "write_tasks",
            "completed",
            f"已写入 {len(tasks_created)} 个任务到本地任务表。",
        ),
    }


def _route_after_reply(state: AgentWorkflowState) -> str:
    return "generate_task_plan" if state.get("intent") == "task_plan" else "end"


@lru_cache(maxsize=1)
def get_agent_graph():
    graph = StateGraph(AgentWorkflowState)
    graph.add_node("understand_request", _understand_request)
    graph.add_node("assistant_reply", _assistant_reply)
    graph.add_node("generate_task_plan", _generate_task_plan)
    graph.add_node("write_tasks", _write_tasks)

    graph.set_entry_point("understand_request")
    graph.add_edge("understand_request", "assistant_reply")
    graph.add_conditional_edges(
        "assistant_reply",
        _route_after_reply,
        {
            "generate_task_plan": "generate_task_plan",
            "end": END,
        },
    )
    graph.add_edge("generate_task_plan", "write_tasks")
    graph.add_edge("write_tasks", END)
    return graph.compile()


async def run_agent_workflow(
    settings: Settings,
    client: OllamaClient,
    request: ChatRequest,
) -> ChatResponse:
    state = await get_agent_graph().ainvoke(
        {
            "request": request,
            "settings": settings,
            "client": client,
            "workflow_events": [],
            "tasks_created": [],
        }
    )

    return ChatResponse(
        request_id=request.request_id,
        model=state.get("model") or request.model or settings.llm_model,
        provider=state.get("provider") or settings.llm_provider,
        reply=state.get("reply", ""),
        tasks_created=state.get("tasks_created", []),
        workflow_events=state.get("workflow_events", []),
    )


async def stream_agent_workflow(
    settings: Settings,
    client: OllamaClient,
    request: ChatRequest,
) -> AsyncIterator[ChatStreamEvent]:
    intent: AgentIntent = "task_plan" if should_create_task_plan(request) else "chat"
    yield _stream_event(
        request,
        settings,
        "understand_request",
        "completed",
        (
            "已识别为任务规划请求，准备拆解步骤。"
            if intent == "task_plan"
            else "已识别为普通对话请求。"
        ),
    )

    yield _stream_event(
        request,
        settings,
        "assistant_reply",
        "running",
        "正在生成回复。",
    )

    saw_done = False
    async for event in client.chat_stream(request):
        yield event
        if event.type == "done":
            saw_done = True
        if event.type == "error":
            return

    if not saw_done:
        return

    yield _stream_event(
        request,
        settings,
        "assistant_reply",
        "completed",
        "已生成面向用户的回复。",
    )

    if intent != "task_plan":
        return

    yield _stream_event(
        request,
        settings,
        "generate_task_plan",
        "running",
        "正在拆解任务。",
    )
    plan_request = build_task_plan_request(request)
    plan_response = await client.chat(plan_request)
    plan = parse_task_plan(plan_response.reply)
    yield _stream_event(
        request,
        settings,
        "generate_task_plan",
        "completed",
        f"已生成 {len(plan.tasks)} 个候选任务。",
    )

    yield _stream_event(
        request,
        settings,
        "write_tasks",
        "running",
        "正在写入本地任务表。",
    )
    tasks_created = create_tasks(settings, plan.tasks)
    yield _stream_event(
        request,
        settings,
        "write_tasks",
        "completed",
        f"已写入 {len(tasks_created)} 个任务到本地任务表。",
    )

    if tasks_created:
        yield ChatStreamEvent(
            type="tasks",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            tasks_created=tasks_created,
        )
