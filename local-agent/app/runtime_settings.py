from app.config import Settings, get_settings
from app.model_config import (
    MODEL_CONFIG_KEYS,
    load_model_config_overrides,
    save_model_config_updates,
)
from app.models.schemas import AppSettingsResponse, AppSettingsUpdate
from app.security.local_only import ensure_allowed_model_url
from app.security.workspace import normalize_workspace_path
from app.storage.settings import load_setting_overrides, save_setting_overrides


def get_runtime_settings() -> Settings:
    base_settings = get_settings()
    setting_overrides = load_setting_overrides(base_settings)
    model_overrides = load_model_config_overrides(base_settings)
    return base_settings.model_copy(update={**setting_overrides, **model_overrides})


def get_app_settings_response() -> AppSettingsResponse:
    settings = get_runtime_settings()
    return AppSettingsResponse(
        llm_provider=settings.llm_provider,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        allow_remote_llm=settings.allow_remote_llm,
        enable_thinking=settings.enable_thinking,
        default_max_tokens=settings.default_max_tokens,
        workspace_path=settings.workspace_path,
        data_dir=settings.data_dir,
    )


def update_app_settings(payload: AppSettingsUpdate) -> AppSettingsResponse:
    current_settings = get_runtime_settings()
    updates = payload.model_dump(exclude_none=True)

    if "workspace_path" in updates:
        updates["workspace_path"] = normalize_workspace_path(updates["workspace_path"])

    model_updates = {
        key: value for key, value in updates.items() if key in MODEL_CONFIG_KEYS
    }
    setting_updates = {
        key: value for key, value in updates.items() if key not in MODEL_CONFIG_KEYS
    }

    if model_updates:
        next_llm_base_url = model_updates.get(
            "llm_base_url",
            current_settings.llm_base_url,
        )
        next_allow_remote_llm = model_updates.get(
            "allow_remote_llm",
            current_settings.allow_remote_llm,
        )
        ensure_allowed_model_url(
            next_llm_base_url,
            allow_remote_llm=next_allow_remote_llm,
        )
        save_model_config_updates(current_settings, model_updates)

    save_setting_overrides(current_settings, setting_updates)
    return get_app_settings_response()
