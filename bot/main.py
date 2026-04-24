import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db.middleware import DbSessionMiddleware
from bot.handlers.confirm import router as confirm_router
from bot.handlers.history import router as history_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.voice import router as voice_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting bot")
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(history_router)
    dp.include_router(confirm_router)
    dp.include_router(voice_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
