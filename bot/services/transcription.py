import asyncio
import logging
import os
import tempfile

import whisper

logger = logging.getLogger(__name__)

_model: whisper.Whisper | None = None
_model_name: str | None = None


def preload_model(model_name: str) -> None:
    """Load Whisper model at startup so OOM is detected early, not during request handling."""
    global _model, _model_name
    logger.info("Pre-loading Whisper model: %s", model_name)
    _model = whisper.load_model(model_name)
    _model_name = model_name
    logger.info("Whisper model '%s' loaded successfully", model_name)


def get_model(model_name: str) -> whisper.Whisper:
    global _model, _model_name
    if _model is None or _model_name != model_name:
        logger.info("Loading Whisper model: %s", model_name)
        _model = whisper.load_model(model_name)
        _model_name = model_name
    return _model


def _sync_transcribe(file_bytes: bytes, model_name: str) -> str:
    model = get_model(model_name)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        logger.info("Transcribing audio file: %s (%d bytes)", tmp_path, len(file_bytes))
        # fp16=False: required for CPU inference, avoids half-precision errors
        result = model.transcribe(tmp_path, language="ru", fp16=False)
        text = result["text"].strip()
        logger.info("Transcription complete: %d chars", len(text))
        return text
    finally:
        os.unlink(tmp_path)


async def transcribe_audio(file_bytes: bytes, model_name: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_transcribe, file_bytes, model_name)
