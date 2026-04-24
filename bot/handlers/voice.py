import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Category
from bot.handlers.confirm import EditStates
from bot.services.parser import parse_expense
from bot.services.transcription import transcribe_audio
from bot.utils.formatting import format_confirmation
from bot.utils.keyboards import confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(StateFilter(None), lambda m: m.voice is not None)
async def handle_voice(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    logger.info("Received voice from user %s", message.from_user.id)
    status_msg = await message.reply("Распознаю голосовое сообщение…")

    file = await message.bot.get_file(message.voice.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    transcription = await transcribe_audio(file_bytes.read(), settings.whisper_model)

    if not transcription:
        await status_msg.edit_text("Не удалось распознать речь. Попробуйте ещё раз.")
        return

    await status_msg.edit_text("Анализирую трату…")

    result = await session.execute(
        select(Category).where(
            Category.user_id == message.from_user.id,
            Category.is_active.is_(True),
        )
    )
    categories = list(result.scalars().all())
    category_names = [c.name for c in categories]
    category_map = {c.name: c for c in categories}

    parsed = await parse_expense(transcription, category_names)

    category_emoji: str | None = None
    if parsed.category and parsed.category in category_map:
        category_emoji = category_map[parsed.category].emoji

    await state.set_data(
        {
            "transcription": transcription,
            "amount": parsed.amount,
            "category": parsed.category,
            "expense_date": parsed.expense_date,
            "note": parsed.note,
            "participants": [p.to_dict() for p in parsed.participants],
            "message_date": message.date.date().isoformat(),
        }
    )

    text = format_confirmation(parsed, category_emoji, transcription)
    await status_msg.delete()
    confirm_msg = await message.reply(text, reply_markup=confirm_keyboard(), parse_mode="HTML")
    await state.update_data(confirm_message_id=confirm_msg.message_id)
