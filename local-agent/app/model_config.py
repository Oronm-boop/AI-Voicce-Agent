import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings


MODEL_CONFIG_FILENAME = "model_config.json"
MODEL_CONFIG_KEYS = {
    "llm_provider",
    "llm_base_url",
    "llm_model",
    "allow_remote_llm",
    "llm_api_key",
    "llm_api_key_env",
    "enable_thinking",
    "default_max_tokens",
    "request_timeout_seconds",
}


class ModelConfigFile(BaseModel):
    llm_provider: str | None = Field(default=None, min_length=1, max_length=100)
    llm_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    allow_remote_llm: bool | None = None
    llm_api_key: str | None = Field(default=None, max_length=2000)
    llm_api_key_env: str | None = Field(default=None, max_length=200)
    enable_thinking: bool | None = None
    default_max_tokens: int | None = Field(default=None, gt=0, le=8192)
    request_timeout_seconds: float | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="ignore")


def model_config_path() -> Path:
    env_path = os.getenv("MODEL_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd = Path.cwd().resolve()
    source_root = Path(__file__).resolve().parents[2]
    candidates = [cwd, *cwd.parents, source_root]

    for base in candidates:
        path = base / MODEL_CONFIG_FILENAME
        if path.is_file():
            return path

    return source_root / MODEL_CONFIG_FILENAME


def default_model_config(settings: Settings) -> dict[str, Any]:
    return {
        "llm_provider": settings.llm_provider,
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "allow_remote_llm": settings.allow_remote_llm,
        "llm_api_key": settings.llm_api_key,
        "llm_api_key_env": settings.llm_api_key_env,
        "enable_thinking": settings.enable_thinking,
        "default_max_tokens": settings.default_max_tokens,
        "request_timeout_seconds": settings.request_timeout_seconds,
    }


def load_model_config_overrides(settings: Settings) -> dict[str, Any]:
    path = model_config_path()
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    config = ModelConfigFile.model_validate(payload)
    overrides = config.model_dump(exclude_none=True)

    api_key_env = overrides.get("llm_api_key_env")
    if api_key_env and not overrides.get("llm_api_key"):
        env_api_key = os.getenv(str(api_key_env), "")
        if env_api_key:
            overrides["llm_api_key"] = env_api_key

    return overrides


def save_model_config_updates(settings: Settings, updates: dict[str, Any]) -> None:
    model_updates = {key: value for key, value in updates.items() if key in MODEL_CONFIG_KEYS}
    if not model_updates:
        return

    path = model_config_path()
    payload = default_model_config(settings)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            payload.update(existing)

    payload.update(model_updates)
    config = ModelConfigFile.model_validate(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(exclude_none=True), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
