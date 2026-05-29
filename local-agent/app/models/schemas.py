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


class ChatResponse(BaseModel):
    request_id: str
    model: str
    provider: str
    reply: str
