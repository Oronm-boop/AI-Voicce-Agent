from __future__ import annotations

import io
import json
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings


class AsrNotConfiguredError(RuntimeError):
    pass


class AsrProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class AsrTranscript:
    text: str
    sample_rate: int
    duration_seconds: float


class SherpaOnnxAsr:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._recognizer: Any | None = None
        self._lock = threading.Lock()

    def transcribe(self, audio: bytes, content_type: str = "") -> AsrTranscript:
        self._ensure_configured()

        if content_type and not self._is_wav_content_type(content_type):
            raise AsrProcessingError(
                "当前 ASR 接口需要 16-bit mono WAV 音频。请检查前端录音编码。"
            )

        samples, sample_rate = self._read_wav(audio)
        if len(samples) == 0:
            raise AsrProcessingError("音频为空，未采集到可识别的语音。")

        recognizer = self._get_recognizer()
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        recognizer.decode_stream(stream)

        text = self._extract_text(stream.result)
        duration_seconds = len(samples) / sample_rate if sample_rate > 0 else 0.0
        return AsrTranscript(
            text=text.strip(),
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
        )

    def _ensure_configured(self) -> None:
        model_type = self.settings.asr_model_type.strip()
        model = self._resolve_path(self.settings.asr_model)
        tokens = self._resolve_path(self.settings.asr_tokens)

        if self.settings.asr_provider != "sherpa-onnx":
            raise AsrNotConfiguredError(
                f"当前 ASR_PROVIDER={self.settings.asr_provider}，尚未启用 sherpa-onnx。"
            )

        if not model_type:
            raise AsrNotConfiguredError("ASR_MODEL_TYPE 未配置。")

        if not model or not model.is_file():
            raise AsrNotConfiguredError(
                "ASR 模型文件未配置或不存在。请在 .env 中设置 ASR_MODEL。"
            )

        if not tokens or not tokens.is_file():
            raise AsrNotConfiguredError(
                "ASR tokens 文件未配置或不存在。请在 .env 中设置 ASR_TOKENS。"
            )

    def _get_recognizer(self) -> Any:
        if self._recognizer is not None:
            return self._recognizer

        with self._lock:
            if self._recognizer is not None:
                return self._recognizer

            try:
                import sherpa_onnx
            except ImportError as exc:
                raise AsrNotConfiguredError(
                    "Python 依赖 sherpa-onnx 尚未安装，请先运行 pip install -r requirements.txt。"
                ) from exc

            model_type = self.settings.asr_model_type.strip().lower()
            model = self._path_arg(self.settings.asr_model)
            tokens = self._path_arg(self.settings.asr_tokens)

            if model_type == "sense_voice":
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=model,
                    tokens=tokens,
                    num_threads=self.settings.asr_num_threads,
                    sample_rate=self.settings.asr_sample_rate,
                    feature_dim=self.settings.asr_feature_dim,
                    decoding_method=self.settings.asr_decoding_method,
                    use_itn=self.settings.asr_use_itn,
                    debug=self.settings.asr_debug,
                    provider=self.settings.asr_compute_provider,
                )
            elif model_type == "paraformer":
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                    paraformer=model,
                    tokens=tokens,
                    num_threads=self.settings.asr_num_threads,
                    sample_rate=self.settings.asr_sample_rate,
                    feature_dim=self.settings.asr_feature_dim,
                    decoding_method=self.settings.asr_decoding_method,
                    debug=self.settings.asr_debug,
                    provider=self.settings.asr_compute_provider,
                )
            else:
                raise AsrNotConfiguredError(
                    "暂仅支持 ASR_MODEL_TYPE=sense_voice 或 paraformer。"
                )

            return self._recognizer

    def _resolve_path(self, value: str) -> Path | None:
        if not value.strip():
            return None

        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return Path.cwd() / path

    def _path_arg(self, value: str) -> str:
        path = Path(value).expanduser()
        if path.is_absolute():
            return str(path)
        return value.replace("\\", "/")

    @staticmethod
    def _is_wav_content_type(content_type: str) -> bool:
        return "audio/wav" in content_type or "audio/wave" in content_type

    @staticmethod
    def _read_wav(audio: bytes):
        try:
            import numpy as np
        except ImportError as exc:
            raise AsrNotConfiguredError(
                "Python 依赖 numpy 尚未安装，请先运行 pip install -r requirements.txt。"
            ) from exc

        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frame_count = wav.getnframes()
                raw = wav.readframes(frame_count)
        except wave.Error as exc:
            raise AsrProcessingError(
                "音频不是有效 WAV 文件。请重新录音或检查前端编码。"
            ) from exc

        if channels != 1:
            raise AsrProcessingError("ASR 需要单声道 WAV 音频。")

        if sample_width != 2:
            raise AsrProcessingError("ASR 需要 16-bit PCM WAV 音频。")

        samples_int16 = np.frombuffer(raw, dtype=np.int16)
        samples_float32 = samples_int16.astype(np.float32) / 32768.0
        return samples_float32, sample_rate

    @staticmethod
    def _extract_text(result: Any) -> str:
        text = getattr(result, "text", None)
        if isinstance(text, str):
            return text

        raw = str(result).strip()
        if not raw:
            return ""

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw

        text = payload.get("text")
        return text if isinstance(text, str) else raw
