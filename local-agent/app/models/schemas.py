from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    prompt: str | None = Field(default=None, description="Shortcut user prompt.")
    messages: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    think: bool | None = Field(
        default=None,
        description="Enable or disable Ollama thinking output for thinking models.",
    )
    stream: bool = Field(
        default=False,
        description="Return server-sent events for incremental generation output.",
    )
    request_id: str = Field(default_factory=lambda: str(uuid4()))

    @model_validator(mode="after")
    def require_prompt_or_messages(self) -> "ChatRequest":
        if not self.prompt and not self.messages:
            raise ValueError("Either prompt or messages is required.")
        return self

    def to_messages(self) -> list[ChatMessage]:
        messages = list(self.messages)
        if self.prompt:
            messages.append(ChatMessage(role="user", content=self.prompt))
        return messages


TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]
WorkflowStatus = Literal["running", "completed", "skipped", "error"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    progress: int = Field(default=0, ge=0, le=100)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    progress: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "TaskUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one task field is required.")
        return self


class TaskItem(BaseModel):
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    progress: int
    created_at: datetime
    updated_at: datetime


class AgentWorkflowEvent(BaseModel):
    step: str
    status: WorkflowStatus
    message: str


class ChatResponse(BaseModel):
    request_id: str
    model: str
    provider: str
    reply: str
    tasks_created: list[TaskItem] = Field(default_factory=list)
    workflow_events: list[AgentWorkflowEvent] = Field(default_factory=list)


ChatStreamEventType = Literal["start", "delta", "done", "error", "tasks", "workflow"]


class ChatStreamEvent(BaseModel):
    type: ChatStreamEventType
    request_id: str
    model: str | None = None
    provider: str | None = None
    delta: str | None = None
    reply: str | None = None
    error: str | None = None
    tasks_created: list[TaskItem] = Field(default_factory=list)
    workflow_step: str | None = None
    workflow_status: WorkflowStatus | None = None
    message: str | None = None


class TaskPlan(BaseModel):
    type: Literal["task_plan"] = "task_plan"
    summary: str = Field(min_length=1, max_length=1000)
    tasks: list[TaskCreate] = Field(min_length=1, max_length=20)


class AppSettingsResponse(BaseModel):
    llm_provider: str
    llm_base_url: str
    llm_model: str
    allow_remote_llm: bool
    enable_thinking: bool
    default_max_tokens: int
    data_dir: str


class AppSettingsUpdate(BaseModel):
    llm_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    enable_thinking: bool | None = None
    default_max_tokens: int | None = Field(default=None, gt=0, le=8192)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AppSettingsUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one setting field is required.")
        return self


VoiceTranscriptionStatus = Literal["ok", "not_configured", "error"]


class VoiceTranscriptionResponse(BaseModel):
    status: VoiceTranscriptionStatus
    transcript: str = ""
    message: str
    audio_bytes: int = Field(default=0, ge=0)
