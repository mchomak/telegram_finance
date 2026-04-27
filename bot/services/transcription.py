import logging

import httpx
from openai import AsyncOpenAI

from bot.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        http_client = (
            httpx.AsyncClient(proxy=settings.proxy_url)
            if settings.proxy_url
            else None
        )
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=http_client,
            timeout=120.0,
        )
    return _client


async def transcribe_audio(file_bytes: bytes) -> str:
    client = _get_client()
    logger.info("Transcribing %d bytes via OpenAI Whisper API", len(file_bytes))
    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.ogg", file_bytes, "audio/ogg"),
        language="ru",
    )
    text = response.text.strip()
    logger.info("Transcription complete: %d chars", len(text))
    return text
