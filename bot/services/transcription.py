import logging
import os
import tempfile

import whisper

logger = logging.getLogger(__name__)

_model: whisper.Whisper | None = None


def get_model(model_name: str) -> whisper.Whisper:
    global _model
    if _model is None:
        logger.info("Loading Whisper model: %s", model_name)
        _model = whisper.load_model(model_name)
    return _model


async def transcribe_audio(file_bytes: bytes, model_name: str) -> str:
    model = get_model(model_name)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        logger.info("Transcribing audio file: %s", tmp_path)
        result = model.transcribe(tmp_path, language="ru")
        text = result["text"].strip()
        logger.info("Transcription complete: %d chars", len(text))
        return text
    finally:
        os.unlink(tmp_path)
