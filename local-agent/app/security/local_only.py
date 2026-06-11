from urllib.parse import urlparse


LOCAL_MODEL_HOSTS = {"127.0.0.1", "localhost", "::1", "192.168.0.105"}

CLOUD_LLM_HOSTS = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "open.bigmodel.cn",
    "dashscope.aliyuncs.com",
}


def ensure_allowed_model_url(url: str, *, allow_remote_llm: bool) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("LLM_BASE_URL must use http or https.")

    if not host:
        raise ValueError("LLM_BASE_URL must include a hostname.")

    if host in CLOUD_LLM_HOSTS and not allow_remote_llm:
        raise ValueError(
            "Remote LLM endpoints are disabled. "
            f"Set allow_remote_llm=true before using cloud host: {host}"
        )

    if not allow_remote_llm and host not in LOCAL_MODEL_HOSTS:
        raise ValueError(
            "Remote LLM endpoints are disabled. Use 127.0.0.1 or localhost."
        )
