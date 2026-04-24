import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, DEFAULT_CATEGORIES, User
from bot.utils.keyboards import main_keyboard

logger = logging.getLogger(__name__)
router = Router()

_WELCOME = (
    "Привет! Я помогу вести учёт расходов 💰\n\n"
    "Просто отправь голосовое сообщение, и я сам запишу трату. Например:\n\n"
    "<blockquote>Потратил 1500 рублей в ресторане, платил за Серёгу и Машу, "
    "каждый должен по 500</blockquote>\n\n"
    "Я распознаю сумму, категорию и участников — и попрошу подтвердить.\n\n"
    "Используй кнопки внизу для управления ботом 👇"
)

_WELCOME_BACK = "С возвращением! Используй кнопки внизу 👇"


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    tg_user = message.from_user
    result = await session.execute(
        select(User).where(User.telegram_id == tg_user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(telegram_id=tg_user.id, username=tg_user.username)
        session.add(user)
        await session.flush()

        session.add_all(
            [
                Category(user_id=user.telegram_id, name=name, emoji=emoji)
                for name, emoji in DEFAULT_CATEGORIES
            ]
        )
        await session.commit()
        logger.info("Registered new user %s", tg_user.id)
        await message.answer(_WELCOME, reply_markup=main_keyboard(), parse_mode="HTML")
    else:
        await message.answer(_WELCOME_BACK, reply_markup=main_keyboard())
