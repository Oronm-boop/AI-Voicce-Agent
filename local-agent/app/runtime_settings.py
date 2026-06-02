from app.config import Settings, get_settings
from app.models.schemas import AppSettingsResponse, AppSettingsUpdate
from app.security.local_only import ensure_allowed_model_url
from app.storage.settings import load_setting_overrides, save_setting_overrides


def get_runtime_settings() -> Settings:
    base_settings = get_settings()
    overrides = load_setting_overrides(base_settings)
    return base_settings.model_copy(update=overrides)


def get_app_settings_response() -> AppSettingsResponse:
    settings = get_runtime_settings()
    return AppSettingsResponse(
        llm_provider=settings.llm_provider,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        allow_remote_llm=settings.allow_remote_llm,
        enable_thinking=settings.enable_thinking,
        default_max_tokens=settings.default_max_tokens,
        data_dir=settings.data_dir,
    )


def update_app_settings(payload: AppSettingsUpdate) -> AppSettingsResponse:
    base_settings = get_settings()
    updates = payload.model_dump(exclude_none=True)

    if "llm_base_url" in updates:
        ensure_allowed_model_url(
            updates["llm_base_url"],
            allow_remote_llm=base_settings.allow_remote_llm,
        )

    save_setting_overrides(base_settings, updates)
    return get_app_settings_response()
