import json
from functools import lru_cache
from typing import AsyncIterator, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.computer_control import (
    ComputerControlPlan,
    build_computer_control_reply,
    execute_computer_control_plan,
    extract_search_query_for_tavily,
    plan_computer_control,
    should_control_computer,
    should_web_search,
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
from app.agent.tavily_search import (
    TavilySearchResponse,
    format_tavily_results,
    tavily_search,
)
from app.models.schemas import (
    AgentWorkflowEvent,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ComputerActionResult,
    FileActionResult,
    TaskItem,
    TaskPlan,
    WebSearchResult,
    WorkflowStatus,
)
from app.storage.tasks import create_tasks


AgentIntent = Literal["chat", "task_plan", "computer_control", "file_control", "web_search"]

POST_COMPUTER_ANSWER_SYSTEM_PROMPT = """
你是本地电脑控制后的结果说明助手。用户的请求包含两部分：先操作电脑，再回答问题。
请只基于 Windows-MCP 执行结果、网页/屏幕文本和用户原始请求回答。
如果 MCP 结果没有提供足够信息，明确说无法从当前页面确认，不要编造实时数据。
用中文简洁回答；可以简要说明已经完成的电脑动作。
""".strip()

WEB_SEARCH_ANSWER_SYSTEM_PROMPT = """
你是一个智能助手。用户请求了联网搜索，以下是搜索结果。
请根据搜索结果，用中文简洁准确地回答用户的问题。
注意：
1. 只基于提供的搜索结果回答，不要编造信息。
2. 如果搜索结果不足以回答问题，明确说明。
3. 适当引用来源。
4. 回答要自然流畅，像是在和用户对话。
""".strip()

ANSWER_AFTER_CONTROL_KEYWORDS = (
    "告诉我",
    "回答我",
    "跟我说",
    "给我说",
    "说一下",
    "汇报",
    "结果",
    "答案",
    "是什么",
    "是多少",
    "怎么样",
    "天气",
    "温度",
    "今天",
    "现在",
    "最新",
)

OBSERVATION_TOOLS = {"web_search", "open_url", "snapshot", "screenshot", "wait_for"}


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
    if should_web_search(request):
        return "web_search"
    if should_control_computer(request):
        return "computer_control"
    return "task_plan" if should_create_task_plan(request) else "chat"


def _intent_message(intent: AgentIntent) -> str:
    if intent == "file_control":
        return "已识别为工作空间文件操作请求。"
    if intent == "web_search":
        return "已识别为联网搜索请求，正在搜索。"
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


def _latest_user_text(request: ChatRequest) -> str:
    if request.prompt:
        return request.prompt.strip()

    for message in reversed(request.messages):
        if message.role == "user":
            return message.content.strip()

    return ""


def _should_answer_after_computer_control(
    request: ChatRequest,
    plan: ComputerControlPlan,
    results: list[ComputerActionResult],
) -> bool:
    if plan.requires_confirmation:
        return False
    text = _latest_user_text(request)
    if not text or not any(keyword in text for keyword in ANSWER_AFTER_CONTROL_KEYWORDS):
        return False
    if not any(result.status == "success" for result in results):
        return False
    return any(result.tool in OBSERVATION_TOOLS for result in results)


def _build_post_computer_answer_request(
    request: ChatRequest,
    plan: ComputerControlPlan,
    results: list[ComputerActionResult],
) -> ChatRequest:
    user_text = _latest_user_text(request)
    context = _computer_results_context(plan, results)
    return ChatRequest(
        messages=[
            ChatMessage(role="system", content=POST_COMPUTER_ANSWER_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"用户原始请求：{user_text}\n\n"
                    f"Windows-MCP 执行结果：\n{context}\n\n"
                    "请继续完成用户要求的回答部分。"
                ),
            ),
        ],
        model=request.model,
        temperature=min(request.temperature, 0.3),
        max_tokens=request.max_tokens or 1024,
        think=request.think,
        request_id=request.request_id,
    )


def _computer_results_context(
    plan: ComputerControlPlan,
    results: list[ComputerActionResult],
) -> str:
    lines = [f"计划摘要：{plan.summary}", "执行结果："]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"{index}. tool={result.tool}; status={result.status}; "
            f"message={_compact_text(result.message, max_length=1600)}"
        )
        detail_text = _interesting_result_details(result)
        if detail_text:
            lines.append(f"   details={detail_text}")
    return _compact_text("\n".join(lines), max_length=12000)


def _interesting_result_details(result: ComputerActionResult) -> str:
    keys = ("query", "url", "snapshot_text", "mcp_response", "condition")
    details = {key: result.details[key] for key in keys if key in result.details}
    if not details:
        return ""
    return _compact_text(
        json.dumps(details, ensure_ascii=False, default=str),
        max_length=6000,
    )


def _compact_text(text: str, *, max_length: int = 1200) -> str:
    value = text.strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _build_web_search_answer_request(
    request: ChatRequest,
    query: str,
    search_context: str,
) -> ChatRequest:
    """Build a ChatRequest that asks the LLM to answer based on Tavily search results."""
    user_text = _latest_user_text(request)
    return ChatRequest(
        messages=[
            ChatMessage(role="system", content=WEB_SEARCH_ANSWER_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"用户原始请求：{user_text}\n\n"
                    f"搜索查询：{query}\n\n"
                    f"{search_context}\n\n"
                    "请根据以上搜索结果回答用户的问题。"
                ),
            ),
        ],
        model=request.model,
        temperature=min(request.temperature, 0.3),
        max_tokens=request.max_tokens or 1024,
        think=request.think,
        request_id=request.request_id,
    )


def _tavily_to_schema_results(
    search_response: TavilySearchResponse,
) -> list[WebSearchResult]:
    """Convert Tavily search results to API-facing WebSearchResult models."""
    return [
        WebSearchResult(
            title=r.title,
            url=r.url,
            content=r.content,
            score=r.score,
        )
        for r in search_response.results
    ]


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
    intent = _detect_intent(request)

    if intent == "file_control":
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

    if intent == "web_search":
        workflow_events = [
            _event("understand_request", "completed", _intent_message("web_search")),
            _event("web_search", "running", "正在通过 Tavily 联网搜索。"),
        ]
        query = extract_search_query_for_tavily(request)
        search_response = await tavily_search(
            query,
            api_key=settings.tavily_api_key,
            search_depth=settings.tavily_search_depth,
            max_results=settings.tavily_max_results,
            timeout_seconds=settings.tavily_timeout_seconds,
        )
        web_results = _tavily_to_schema_results(search_response)
        if search_response.ok:
            workflow_events.append(
                _event("web_search", "completed", f"搜索到 {len(search_response.results)} 条结果。")
            )
            context = format_tavily_results(search_response)
            answer_request = _build_web_search_answer_request(request, query, context)
            workflow_events.append(
                _event("assistant_reply", "running", "正在根据搜索结果生成回复。")
            )
            answer_response = await client.chat(answer_request)
            reply = answer_response.reply
            workflow_events.append(
                _event("assistant_reply", "completed", "已根据搜索结果生成回复。")
            )
        else:
            workflow_events.append(
                _event("web_search", "error", f"搜索失败：{search_response.error}")
            )
            reply = f"联网搜索失败：{search_response.error}"
        return ChatResponse(
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            reply=reply,
            web_search_results=web_results,
            workflow_events=workflow_events,
        )

    if intent == "computer_control":
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
        results = execute_computer_control_plan(plan, settings)
        reply = build_computer_control_reply(plan, results)
        workflow_events.append(
            _event(
                "computer_control",
                _computer_control_status(results),
                "本地电脑动作处理完成。",
            )
        )
        if _should_answer_after_computer_control(request, plan, results):
            workflow_events.append(
                _event(
                    "assistant_reply",
                    "running",
                    "正在根据 Windows-MCP 结果生成回复。",
                )
            )
            answer_request = _build_post_computer_answer_request(request, plan, results)
            answer_response = await client.chat(answer_request)
            reply = answer_response.reply
            workflow_events.append(
                _event(
                    "assistant_reply",
                    "completed",
                    "已根据 Windows-MCP 结果生成回复。",
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

    if intent == "web_search":
        yield _stream_event(request, settings, "web_search", "running", "正在通过 Tavily 联网搜索。")
        query = extract_search_query_for_tavily(request)
        search_response = await tavily_search(
            query,
            api_key=settings.tavily_api_key,
            search_depth=settings.tavily_search_depth,
            max_results=settings.tavily_max_results,
            timeout_seconds=settings.tavily_timeout_seconds,
        )
        web_results = _tavily_to_schema_results(search_response)
        yield ChatStreamEvent(
            type="web_search",
            request_id=request.request_id,
            model=request.model or settings.llm_model,
            provider=settings.llm_provider,
            web_search_results=web_results,
            message=f"搜索 \"{query}\" 完成，找到 {len(web_results)} 条结果。" if search_response.ok else f"搜索失败：{search_response.error}",
        )
        if search_response.ok:
            yield _stream_event(request, settings, "web_search", "completed", f"搜索到 {len(search_response.results)} 条结果。")
            context = format_tavily_results(search_response)
            answer_request = _build_web_search_answer_request(request, query, context)
            yield _stream_event(request, settings, "assistant_reply", "running", "正在根据搜索结果生成回复。")
            saw_done = False
            async for event in client.chat_stream(answer_request):
                yield event
                if event.type == "done":
                    saw_done = True
                if event.type == "error":
                    return
            if saw_done:
                yield _stream_event(request, settings, "assistant_reply", "completed", "已根据搜索结果生成回复。")
        else:
            yield _stream_event(request, settings, "web_search", "error", f"搜索失败：{search_response.error}")
            yield ChatStreamEvent(
                type="done",
                request_id=request.request_id,
                model=request.model or settings.llm_model,
                provider=settings.llm_provider,
                reply=f"联网搜索失败：{search_response.error}",
            )
        return

    if intent == "computer_control":
        yield _stream_event(
            request,
            settings,
            "computer_control",
            "running",
            "正在规划并执行本地电脑动作。",
        )
        plan = await plan_computer_control(client, request)
        results = execute_computer_control_plan(plan, settings)
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
        if _should_answer_after_computer_control(request, plan, results):
            yield _stream_event(
                request,
                settings,
                "assistant_reply",
                "running",
                "正在根据 Windows-MCP 结果生成回复。",
            )
            answer_request = _build_post_computer_answer_request(request, plan, results)
            saw_done = False
            async for event in client.chat_stream(answer_request):
                yield event
                if event.type == "done":
                    saw_done = True
                if event.type == "error":
                    return

            if saw_done:
                yield _stream_event(
                    request,
                    settings,
                    "assistant_reply",
                    "completed",
                    "已根据 Windows-MCP 结果生成回复。",
                )
            return

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
