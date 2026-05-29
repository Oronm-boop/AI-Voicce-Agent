from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.models.schemas import ChatRequest, ChatResponse
from app.security.local_only import ensure_allowed_model_url


class OllamaClientError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.llm_base_url.rstrip("/")

    @property
    def is_openai_compatible(self) -> bool:
        path = urlparse(self.base_url).path.rstrip("/")
        return path.endswith("/v1")

    async def status(self) -> dict:
        try:
            ensure_allowed_model_url(
                self.base_url,
                allow_remote_llm=self.settings.allow_remote_llm,
            )
        except ValueError as exc:
            return self._status_payload(available=False, error=str(exc))

        try:
            if self.is_openai_compatible:
                models = await self._list_models_openai_compatible()
            else:
                models = await self._list_models_native()
        except (httpx.HTTPError, OllamaClientError, ValueError) as exc:
            return self._status_payload(available=False, error=str(exc))

        return self._status_payload(available=True, models=models)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        ensure_allowed_model_url(
            self.base_url,
            allow_remote_llm=self.settings.allow_remote_llm,
        )

        if self.settings.llm_provider != "ollama":
            raise OllamaClientError(
                f"Unsupported LLM provider for MVP: {self.settings.llm_provider}"
            )

        try:
            if self.is_openai_compatible:
                reply = await self._chat_openai_compatible(request)
            else:
                reply = await self._chat_native(request)
        except httpx.TimeoutException as exc:
            raise OllamaClientError(
                "Ollama request timed out. The model may still be generating; "
                "try a shorter prompt, lower max_tokens, or restart Ollama."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise OllamaClientError(
                f"Ollama returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            detail = str(exc) or exc.__class__.__name__
            raise OllamaClientError(f"Ollama request failed: {detail}") from exc

        return ChatResponse(
            request_id=request.request_id,
            model=request.model or self.settings.llm_model,
            provider=self.settings.llm_provider,
            reply=reply,
        )

    async def _list_models_native(self) -> list[str]:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()

        return [
            item.get("name", "")
            for item in payload.get("models", [])
            if item.get("name")
        ]

    async def _list_models_openai_compatible(self) -> list[str]:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            payload = response.json()

        return [
            item.get("id", "")
            for item in payload.get("data", [])
            if item.get("id")
        ]

    async def _chat_native(self, request: ChatRequest) -> str:
        max_tokens = request.max_tokens or self.settings.default_max_tokens
        think = self.settings.enable_thinking if request.think is None else request.think

        payload: dict[str, Any] = {
            "model": request.model or self.settings.llm_model,
            "messages": [message.model_dump() for message in request.to_messages()],
            "stream": False,
            "think": think,
            "options": {
                "temperature": request.temperature,
                "num_predict": max_tokens,
            },
        }

        async with self._client() as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            result = response.json()

        message = result.get("message", {})
        content = message.get("content")
        thinking = message.get("thinking")
        if not content:
            if thinking:
                raise OllamaClientError(
                    "Ollama returned thinking output but no final answer. "
                    "Keep think=false, increase max_tokens, or use a non-thinking model."
                )
            raise OllamaClientError("Ollama returned an empty chat response.")

        return content

    async def _chat_openai_compatible(self, request: ChatRequest) -> str:
        max_tokens = request.max_tokens or self.settings.default_max_tokens

        payload: dict[str, Any] = {
            "model": request.model or self.settings.llm_model,
            "messages": [message.model_dump() for message in request.to_messages()],
            "stream": False,
            "temperature": request.temperature,
            "max_tokens": max_tokens,
        }

        async with self._client() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        choices = result.get("choices", [])
        content = choices[0].get("message", {}).get("content") if choices else None
        if not content:
            raise OllamaClientError("Ollama returned an empty chat response.")

        return content

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)

    def _status_payload(
        self,
        *,
        available: bool,
        models: list[str] | None = None,
        error: str | None = None,
    ) -> dict:
        model_names = models or []
        configured_model = self.settings.llm_model

        return {
            "provider": self.settings.llm_provider,
            "base_url": self.base_url,
            "available": available,
            "configured_model": configured_model,
            "configured_model_present": configured_model in model_names,
            "models": model_names,
            "error": error,
            "local_only": not self.settings.allow_remote_llm,
        }
