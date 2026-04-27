import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    logger.info("Received voice from user %s, file_id=%s", message.from_user.id, message.voice.file_id)
    status_msg = await message.reply("Распознаю голосовое сообщение…")

    try:
        file = await message.bot.get_file(message.voice.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        audio_data = file_bytes.read()
        logger.info("Downloaded audio: %d bytes", len(audio_data))
        transcription = await transcribe_audio(audio_data)
    except Exception as exc:
        logger.error("Transcription failed for user %s: %s", message.from_user.id, exc, exc_info=True)
        await status_msg.edit_text("Ошибка при распознавании речи. Попробуйте ещё раз.")
        return

    if not transcription:
        await status_msg.edit_text("Не удалось распознать речь. Попробуйте ещё раз.")
        return

    logger.info("Transcription result for user %s: %r", message.from_user.id, transcription[:100])
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

    try:
        parsed = await parse_expense(transcription, category_names)
    except Exception as exc:
        logger.error("GPT parsing failed for user %s: %s", message.from_user.id, exc, exc_info=True)
        await status_msg.edit_text("Ошибка при анализе траты. Попробуйте ещё раз.")
        return

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
