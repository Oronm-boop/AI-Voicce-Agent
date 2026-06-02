import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import VoiceTranscriptionResponse
from app.runtime_settings import get_runtime_settings
from app.speech.asr import (
    AsrNotConfiguredError,
    AsrProcessingError,
    SherpaOnnxAsr,
)


router = APIRouter(prefix="/voice", tags=["voice"])

_asr_engine: SherpaOnnxAsr | None = None


def get_asr_engine() -> SherpaOnnxAsr:
    global _asr_engine

    if _asr_engine is None:
        _asr_engine = SherpaOnnxAsr(get_runtime_settings())

    return _asr_engine


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(request: Request):
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="Audio payload is required.")

    content_type = request.headers.get("content-type", "")
    try:
        result = await asyncio.to_thread(
            get_asr_engine().transcribe,
            audio,
            content_type,
        )
    except AsrNotConfiguredError as error:
        return VoiceTranscriptionResponse(
            status="not_configured",
            transcript="",
            message=str(error),
            audio_bytes=len(audio),
        )
    except AsrProcessingError as error:
        return VoiceTranscriptionResponse(
            status="error",
            transcript="",
            message=str(error),
            audio_bytes=len(audio),
        )

    if not result.text:
        return VoiceTranscriptionResponse(
            status="error",
            transcript="",
            message="未识别到有效文字，请靠近麦克风后重试。",
            audio_bytes=len(audio),
        )

    return VoiceTranscriptionResponse(
        status="ok",
        transcript=result.text,
        message=f"识别成功，音频时长约 {result.duration_seconds:.1f} 秒。",
        audio_bytes=len(audio),
    )
