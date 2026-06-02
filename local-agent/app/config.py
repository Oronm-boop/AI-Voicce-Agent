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
    default_max_tokens: int = Field(default=2048, gt=0)
    enable_thinking: bool = False
    data_dir: str = "data"
    asr_provider: str = "sherpa-onnx"
    asr_model_type: str = "sense_voice"
    asr_model: str = (
        "models/asr/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/"
        "model.int8.onnx"
    )
    asr_tokens: str = (
        "models/asr/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/"
        "tokens.txt"
    )
    asr_num_threads: int = Field(default=2, gt=0)
    asr_compute_provider: str = "cpu"
    asr_sample_rate: int = Field(default=16000, gt=0)
    asr_feature_dim: int = Field(default=80, gt=0)
    asr_decoding_method: str = "greedy_search"
    asr_use_itn: bool = True
    asr_debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
