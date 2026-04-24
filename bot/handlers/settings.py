import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category
from bot.utils.keyboards import (
    categories_delete_keyboard,
    settings_menu_keyboard,
    skip_emoji_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


class AddCategoryStates(StatesGroup):
    waiting_name = State()
    waiting_emoji = State()


async def _active_categories(session: AsyncSession, user_id: int) -> list[Category]:
    result = await session.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


# ── Reply keyboard trigger — registered first so it overrides FSM states ──────

@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Настройки категорий:", reply_markup=settings_menu_keyboard())


# ── Settings menu callbacks ───────────────────────────────────────────────────

@router.callback_query(F.data == "settings:back")
async def cb_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Настройки категорий:", reply_markup=settings_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "settings:list")
async def cb_list(callback: CallbackQuery, session: AsyncSession) -> None:
    categories = await _active_categories(session, callback.from_user.id)
    if categories:
        lines = [
            f"{cat.emoji or '▪️'} {cat.name}" for cat in categories
        ]
        text = "Ваши категории:\n\n" + "\n".join(lines)
    else:
        text = "У вас пока нет активных категорий."
    await callback.message.edit_text(text, reply_markup=settings_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "settings:add")
async def cb_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategoryStates.waiting_name)
    await callback.answer()
    await callback.message.answer("Введите название новой категории:")


@router.callback_query(F.data == "settings:delete")
async def cb_delete_list(callback: CallbackQuery, session: AsyncSession) -> None:
    categories = await _active_categories(session, callback.from_user.id)
    if not categories:
        await callback.answer("Нет активных категорий.", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите категорию для удаления:",
        reply_markup=categories_delete_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_del:"))
async def cb_delete_category(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    cat_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Category).where(
            Category.id == cat_id,
            Category.user_id == callback.from_user.id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    category.is_active = False
    await session.commit()
    logger.info("Deactivated category %s for user %s", cat_id, callback.from_user.id)

    # Refresh the delete list
    categories = await _active_categories(session, callback.from_user.id)
    if categories:
        await callback.message.edit_text(
            f"Категория «{category.name}» удалена.\n\nВыберите ещё или вернитесь назад:",
            reply_markup=categories_delete_keyboard(categories),
        )
    else:
        await callback.message.edit_text(
            f"Категория «{category.name}» удалена.\n\nАктивных категорий больше нет.",
            reply_markup=settings_menu_keyboard(),
        )
    await callback.answer()


# ── FSM: add category ─────────────────────────────────────────────────────────

@router.message(AddCategoryStates.waiting_name)
async def input_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name:
        await message.reply("Название не может быть пустым. Введите название:")
        return

    await state.update_data(new_category_name=name)
    await state.set_state(AddCategoryStates.waiting_emoji)
    await message.reply(
        f"Название: <b>{name}</b>\n\nТеперь отправьте эмодзи для категории "
        f"или нажмите «Пропустить»:",
        reply_markup=skip_emoji_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "settings:skip_emoji", AddCategoryStates.waiting_emoji)
async def cb_skip_emoji(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await _save_new_category(callback.from_user.id, emoji=None, state=state, session=session)
    data = await state.get_data()
    name = data.get("new_category_name", "")
    await state.clear()
    await callback.message.edit_text(f"Категория «{name}» добавлена ✅")
    await callback.answer()


@router.message(AddCategoryStates.waiting_emoji)
async def input_emoji(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    emoji = message.text.strip() if message.text else None
    data = await state.get_data()
    name = data.get("new_category_name", "")

    session.add(
        Category(user_id=message.from_user.id, name=name, emoji=emoji or None)
    )
    await session.commit()
    await state.clear()

    label = f"{emoji} {name}" if emoji else name
    logger.info("Created category '%s' for user %s", name, message.from_user.id)
    await message.reply(f"Категория «{label}» добавлена ✅")


async def _save_new_category(
    user_id: int, emoji: str | None, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    name = data.get("new_category_name", "")
    session.add(Category(user_id=user_id, name=name, emoji=emoji))
    await session.commit()
    logger.info("Created category '%s' for user %s", name, user_id)
