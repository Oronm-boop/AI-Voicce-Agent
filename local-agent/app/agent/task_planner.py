import json
import re

from pydantic import ValidationError

from app.config import Settings
from app.models.ollama_client import OllamaClient
from app.models.schemas import ChatMessage, ChatRequest, TaskItem, TaskPlan
from app.storage.tasks import create_tasks


TASK_INTENT_KEYWORDS = (
    "拆任务",
    "任务拆解",
    "拆解",
    "开发计划",
    "计划",
    "待办",
    "todo",
    "todolist",
    "todo list",
    "步骤",
    "里程碑",
    "排期",
)


TASK_PLAN_SYSTEM_PROMPT = """
你是一个任务规划器。请把用户目标拆成可以执行的任务，并且只输出 JSON。

输出必须符合这个结构：
{
  "type": "task_plan",
  "summary": "一句话总结",
  "tasks": [
    {
      "title": "任务标题",
      "description": "任务说明",
      "priority": "high|medium|low",
      "status": "todo",
      "progress": 0
    }
  ]
}

要求：
- 只输出 JSON，不要输出 Markdown，不要解释。
- tasks 数量控制在 3 到 8 个。
- status 只能是 todo。
- priority 只能是 high、medium、low。
- progress 必须是 0。
""".strip()


class TaskPlanError(RuntimeError):
    """Raised when the model cannot produce a valid task plan."""


def should_create_task_plan(request: ChatRequest) -> bool:
    latest_user_message = next(
        (
            message.content
            for message in reversed(request.to_messages())
            if message.role == "user"
        ),
        "",
    )
    content = latest_user_message.lower()
    return any(keyword.lower() in content for keyword in TASK_INTENT_KEYWORDS)


def build_task_plan_request(source_request: ChatRequest) -> ChatRequest:
    user_content = "\n".join(
        message.content for message in source_request.to_messages() if message.role == "user"
    )
    return ChatRequest(
        messages=[
            ChatMessage(role="system", content=TASK_PLAN_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ],
        model=source_request.model,
        temperature=0.2,
        max_tokens=max(source_request.max_tokens or 512, 512),
        think=False,
        stream=False,
    )


async def create_task_plan_from_chat(
    settings: Settings,
    client: OllamaClient,
    source_request: ChatRequest,
) -> list[TaskItem]:
    if not should_create_task_plan(source_request):
        return []

    plan_request = build_task_plan_request(source_request)
    response = await client.chat(plan_request)
    plan = parse_task_plan(response.reply)
    return create_tasks(settings, plan.tasks)


def parse_task_plan(text: str) -> TaskPlan:
    payload = _extract_json_object(text)
    try:
        return TaskPlan.model_validate(payload)
    except ValidationError as exc:
        raise TaskPlanError(f"Invalid task plan JSON: {exc}") from exc


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()

    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        try:
            payload = json.loads(fenced.group(1))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(stripped[start : end + 1])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:
            raise TaskPlanError(f"Model returned malformed JSON: {exc}") from exc

    raise TaskPlanError("Model did not return a JSON object.")
