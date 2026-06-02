from fastapi import APIRouter, HTTPException

from app.models.schemas import AppSettingsResponse, AppSettingsUpdate
from app.runtime_settings import get_app_settings_response, update_app_settings


router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=AppSettingsResponse)
def get_settings_api():
    return get_app_settings_response()


@router.put("/settings", response_model=AppSettingsResponse)
def put_settings_api(payload: AppSettingsUpdate):
    try:
        return update_app_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
