from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Local Agent Runtime"
    agent_host: str = "127.0.0.1"
    agent_port: int = 8765
    allow_remote_llm: bool = False
    llm_provider: str = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:0.5b"
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    default_max_tokens: int = Field(default=256, gt=0)
    enable_thinking: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
