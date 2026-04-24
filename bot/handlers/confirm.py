import logging
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Expense, SharedExpense
from bot.services.parser import ParsedExpense, ParsedParticipant, parse_expense
from bot.utils.formatting import format_confirmation
from bot.utils.keyboards import confirm_keyboard, edit_fields_keyboard

logger = logging.getLogger(__name__)
router = Router()


class EditStates(StatesGroup):
    editing_amount = State()
    editing_category = State()
    editing_participants = State()
    editing_date = State()


async def _active_categories(session: AsyncSession, user_id: int) -> list[Category]:
    result = await session.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


def _find_category(categories: list[Category], name: str | None) -> Category | None:
    if not name:
        return None
    for cat in categories:
        if cat.name.lower() == name.lower():
            return cat
    return None


async def _render_confirmation(
    fsm_data: dict,
    categories: list[Category],
) -> str:
    category = _find_category(categories, fsm_data.get("category"))
    parsed = ParsedExpense(
        amount=fsm_data.get("amount"),
        category=fsm_data.get("category"),
        expense_date=fsm_data.get("expense_date"),
        note=fsm_data.get("note"),
        participants=[
            ParsedParticipant.from_dict(p) for p in fsm_data.get("participants", [])
        ],
    )
    return format_confirmation(
        parsed=parsed,
        category_emoji=category.emoji if category else None,
        transcription=fsm_data["transcription"],
    )


async def _restore_confirmation_from_message(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """After text input: edit the stored confirmation message, delete user's message."""
    data = await state.get_data()
    categories = await _active_categories(session, message.from_user.id)
    text = await _render_confirmation(data, categories)

    try:
        await message.bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=data["confirm_message_id"],
            reply_markup=confirm_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to edit confirmation message")

    try:
        await message.delete()
    except Exception:
        pass


# ── Confirm / Edit callbacks ──────────────────────────────────────────────────

@router.callback_query(F.data == "confirm:save")
async def cb_save(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    user_id = callback.from_user.id

    categories = await _active_categories(session, user_id)
    category = _find_category(categories, data.get("category"))

    raw_date = data.get("expense_date") or data.get("message_date")
    try:
        expense_date = date.fromisoformat(raw_date)
    except (TypeError, ValueError):
        expense_date = date.today()

    expense = Expense(
        user_id=user_id,
        amount=data.get("amount"),
        category_id=category.id if category else None,
        transcription=data["transcription"],
        note=data.get("note"),
        expense_date=expense_date,
    )
    session.add(expense)
    await session.flush()

    for p in data.get("participants", []):
        session.add(
            SharedExpense(
                expense_id=expense.id,
                participant_name=p["name"],
                amount_owed=p.get("amount_owed"),
                item_description=p.get("item_description"),
            )
        )

    await session.commit()
    await state.clear()

    await callback.message.edit_text("Записано ✅")
    await callback.answer()
    logger.info("Saved expense id=%s for user %s", expense.id, user_id)


@router.callback_query(F.data == "confirm:edit")
async def cb_edit(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=edit_fields_keyboard())
    await callback.answer()


@router.callback_query(F.data == "confirm:back")
async def cb_back(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    categories = await _active_categories(session, callback.from_user.id)
    text = await _render_confirmation(data, categories)
    await callback.message.edit_text(text, reply_markup=confirm_keyboard(), parse_mode="HTML")
    await callback.answer()


# ── Field selection callbacks ─────────────────────────────────────────────────

@router.callback_query(F.data == "edit:amount")
async def cb_edit_amount(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditStates.editing_amount)
    await callback.answer("Введите новую сумму (число):", show_alert=True)


@router.callback_query(F.data == "edit:category")
async def cb_edit_category(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    categories = await _active_categories(session, callback.from_user.id)
    names = ", ".join(c.name for c in categories)
    await state.set_state(EditStates.editing_category)
    await callback.answer(f"Введите категорию:\n{names}", show_alert=True)


@router.callback_query(F.data == "edit:participants")
async def cb_edit_participants(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditStates.editing_participants)
    await callback.answer(
        "Введите участников в свободной форме.\n"
        "Пример: Серёга 500, Маша пиво и шоколадка",
        show_alert=True,
    )


@router.callback_query(F.data == "edit:date")
async def cb_edit_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditStates.editing_date)
    await callback.answer("Введите дату в формате ГГГГ-ММ-ДД:", show_alert=True)


# ── Text input handlers ───────────────────────────────────────────────────────

@router.message(EditStates.editing_amount)
async def input_amount(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    raw = message.text.strip().replace(",", ".").replace("\u00a0", "").replace(" ", "")
    try:
        amount = float(raw)
    except ValueError:
        await message.reply("Введите число, например: 450 или 1500.50")
        return

    await state.update_data(amount=amount)
    await state.set_state(None)
    await _restore_confirmation_from_message(message, state, session)


@router.message(EditStates.editing_category)
async def input_category(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    name = message.text.strip()
    categories = await _active_categories(session, message.from_user.id)
    matched = _find_category(categories, name)

    if matched is None:
        names = ", ".join(c.name for c in categories)
        await message.reply(f"Категория не найдена. Доступные: {names}")
        return

    await state.update_data(category=matched.name)
    await state.set_state(None)
    await _restore_confirmation_from_message(message, state, session)


@router.message(EditStates.editing_participants)
async def input_participants(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    categories = await _active_categories(session, message.from_user.id)
    category_names = [c.name for c in categories]

    reparsed = await parse_expense(f"Участники: {message.text.strip()}", category_names)
    participants = [p.to_dict() for p in reparsed.participants]

    await state.update_data(participants=participants)
    await state.set_state(None)
    await _restore_confirmation_from_message(message, state, session)


@router.message(EditStates.editing_date)
async def input_date(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    raw = message.text.strip()
    try:
        date.fromisoformat(raw)
    except ValueError:
        await message.reply(
            "Неверный формат. Введите дату как ГГГГ-ММ-ДД, например: 2025-04-10"
        )
        return

    await state.update_data(expense_date=raw)
    await state.set_state(None)
    await _restore_confirmation_from_message(message, state, session)
