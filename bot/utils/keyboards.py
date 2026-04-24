from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.db.models import Category


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="📋 История"),
                KeyboardButton(text="📤 Экспорт"),
            ]
        ],
        resize_keyboard=True,
        persistent=True,
    )


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📂 Мои категории", callback_data="settings:list")],
            [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="settings:add")],
            [InlineKeyboardButton(text="🗑 Удалить категорию", callback_data="settings:delete")],
        ]
    )


def categories_delete_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{cat.emoji or ''} {cat.name}".strip(),
                callback_data=f"cat_del:{cat.id}",
            )
        ]
        for cat in categories
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_emoji_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="settings:skip_emoji")]
        ]
    )


def history_keyboard(page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + page_size - 1) // page_size)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="← Назад", callback_data=f"hist:page:{page - 1}"))
    nav.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"hist:page:{page + 1}"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav,
            [InlineKeyboardButton(text="💸 Долги", callback_data="hist:debts")],
        ]
    )


def debts_keyboard(debts: list) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✅ Получил(а)", callback_data=f"debts:paid:{d.participant_name}"),
            InlineKeyboardButton(text=f"📋 {d.participant_name}", callback_data=f"debts:details:{d.participant_name}"),
        ]
        for d in debts
    ]
    rows.append([InlineKeyboardButton(text="◀️ История", callback_data="hist:page:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def debt_details_keyboard(participant_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к долгам", callback_data="debts:back")]
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm:save"),
                InlineKeyboardButton(text="✏️ Править", callback_data="confirm:edit"),
            ]
        ]
    )


def edit_fields_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сумма", callback_data="edit:amount"),
                InlineKeyboardButton(text="Категория", callback_data="edit:category"),
            ],
            [
                InlineKeyboardButton(text="Участники", callback_data="edit:participants"),
                InlineKeyboardButton(text="Дата", callback_data="edit:date"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="confirm:back"),
            ],
        ]
    )
