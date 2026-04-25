import asyncio
import logging
import subprocess
import sys

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import text

from bot.config import settings
from bot.db.base import engine
from bot.db.middleware import DbSessionMiddleware
from bot.handlers.confirm import router as confirm_router
from bot.handlers.export import router as export_router
from bot.handlers.history import router as history_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.voice import router as voice_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_DB_RETRIES = 10
_DB_RETRY_DELAY = 2.0


async def _wait_for_db() -> None:
    for attempt in range(1, _DB_RETRIES + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("DB is ready")
            return
        except Exception as exc:
            logger.warning("DB not ready (attempt %d/%d): %s", attempt, _DB_RETRIES, exc)
            if attempt < _DB_RETRIES:
                await asyncio.sleep(_DB_RETRY_DELAY)
    logger.error("Could not reach DB after %d attempts — exiting", _DB_RETRIES)
    sys.exit(1)


def _run_migrations() -> None:
    logger.info("Running alembic upgrade head")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logger.info(result.stdout.strip())
    if result.returncode != 0:
        logger.error("Migration failed: %s", result.stderr.strip())
        sys.exit(1)


async def main() -> None:
    logger.info("Starting bot")
    await _wait_for_db()
    _run_migrations()

    session = AiohttpSession(
        timeout=aiohttp.ClientTimeout(total=30, connect=10, sock_connect=10)
    )
    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(history_router)
    dp.include_router(export_router)
    dp.include_router(confirm_router)
    dp.include_router(voice_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
