from functools import lru_cache
from typing import AsyncIterator, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.computer_control import (
    build_computer_control_reply,
    execute_computer_control_plan,
    plan_computer_control,
    should_control_computer,
)
from app.agent.file_control import (
    build_file_operation_reply,
    execute_file_operation_plan,
    plan_file_operations,
    should_control_files,
)
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
    ComputerActionResult,
    FileActionResult,
    TaskItem,
    TaskPlan,
    WorkflowStatus,
)
from app.storage.tasks import create_tasks


AgentIntent = Literal["chat", "task_plan", "computer_control", "file_control"]


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


def _detect_intent(request: ChatRequest) -> AgentIntent:
    if should_control_files(request):
        return "file_control"
    if should_control_computer(request):
        return "computer_control"
    return "task_plan" if should_create_task_plan(request) else "chat"


def _intent_message(intent: AgentIntent) -> str:
    if intent == "file_control":
        return "已识别为工作空间文件操作请求。"
    if intent == "computer_control":
        return "已识别为本地电脑控制请求。"
    if intent == "task_plan":
        return "已识别为任务规划请求，准备拆解步骤。"
    return "已识别为普通对话请求。"


def _computer_control_status(
    results: list[ComputerActionResult],
) -> WorkflowStatus:
    if any(result.status == "error" for result in results):
        return "error"
    if any(result.status == "confirm_required" for result in results):
        return "skipped"
    return "completed"


def _file_operation_status(
    results: list[FileActionResult],
) -> WorkflowStatus:
    if any(result.status == "error" for result in results):
        return "error"
    if any(result.status == "skipped" for result in results):
        return "skipped"
    return "completed"


async def _understand_request(state: AgentWorkflowState) -> AgentWorkflowState:
    request = state["request"]
    intent = _detect_intent(request)
    return {
        "intent": intent,
        "workflow_events": _append_event(
            state,
            "understand_request",
            "completed",
            _intent_message(intent),
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
    if _detect_intent(request) == "file_control":
        workflow_events = [
            _event(
                "understand_request",
                "completed",
                _intent_message("file_control"),
            ),
            _event(
                "file_control",
                "running",
                "正在规划并执行工作空间文件操作。",
            ),
        ]
        plan = await plan_file_operations(settings, client, request)
        results = execute_file_operation_plan(settings, plan)
        reply = build_file_operation_reply(plan, results)
        workflow_events.append(
            _event(
                "file_control",
                _file_operation_status(results),
                "工作空间文件操作处理完成。",
            )
        )
        return ChatResponse(
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            reply=reply,
            file_actions=results,
            workflow_events=workflow_events,
        )

    if _detect_intent(request) == "computer_control":
        workflow_events = [
            _event(
                "understand_request",
                "completed",
                _intent_message("computer_control"),
            ),
            _event(
                "computer_control",
                "running",
                "正在规划并执行本地电脑动作。",
            ),
        ]
        plan = await plan_computer_control(client, request)
        results = execute_computer_control_plan(plan)
        reply = build_computer_control_reply(plan, results)
        workflow_events.append(
            _event(
                "computer_control",
                _computer_control_status(results),
                "本地电脑动作处理完成。",
            )
        )
        return ChatResponse(
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            reply=reply,
            computer_actions=results,
            workflow_events=workflow_events,
        )

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
    intent = _detect_intent(request)
    yield _stream_event(
        request,
        settings,
        "understand_request",
        "completed",
        _intent_message(intent),
    )

    if intent == "computer_control":
        yield _stream_event(
            request,
            settings,
            "computer_control",
            "running",
            "正在规划并执行本地电脑动作。",
        )
        plan = await plan_computer_control(client, request)
        results = execute_computer_control_plan(plan)
        reply = build_computer_control_reply(plan, results)
        yield ChatStreamEvent(
            type="computer_actions",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            computer_actions=results,
            message=reply,
        )
        yield _stream_event(
            request,
            settings,
            "computer_control",
            _computer_control_status(results),
            "本地电脑动作处理完成。",
        )
        yield ChatStreamEvent(
            type="done",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            reply=reply,
        )
        return

    if intent == "file_control":
        yield _stream_event(
            request,
            settings,
            "file_control",
            "running",
            "正在规划并执行工作空间文件操作。",
        )
        plan = await plan_file_operations(settings, client, request)
        results = execute_file_operation_plan(settings, plan)
        reply = build_file_operation_reply(plan, results)
        yield ChatStreamEvent(
            type="file_actions",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            file_actions=results,
            message=reply,
        )
        yield _stream_event(
            request,
            settings,
            "file_control",
            _file_operation_status(results),
            "工作空间文件操作处理完成。",
        )
        yield ChatStreamEvent(
            type="done",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            reply=reply,
        )
        return

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
