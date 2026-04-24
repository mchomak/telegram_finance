import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Expense, SharedExpense
from bot.utils.formatting import (
    DebtSummary,
    format_debt_details,
    format_debts_summary,
    format_history_page,
)
from bot.utils.keyboards import debt_details_keyboard, debts_keyboard, history_keyboard

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 10


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _fetch_history_page(
    session: AsyncSession, user_id: int, page: int
) -> tuple[list[tuple[Expense, Category | None]], int]:
    total: int = (
        await session.execute(
            select(func.count()).select_from(Expense).where(Expense.user_id == user_id)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(Expense, Category)
            .outerjoin(Category, Expense.category_id == Category.id)
            .where(Expense.user_id == user_id)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .limit(PAGE_SIZE)
            .offset(page * PAGE_SIZE)
        )
    ).all()

    return [(e, c) for e, c in rows], total


async def _fetch_debts(session: AsyncSession, user_id: int) -> list[DebtSummary]:
    rows = (
        await session.execute(
            select(SharedExpense)
            .join(Expense, SharedExpense.expense_id == Expense.id)
            .where(
                Expense.user_id == user_id,
                SharedExpense.is_returned.is_(False),
            )
        )
    ).scalars().all()

    grouped: dict[str, DebtSummary] = {}
    for s in rows:
        name = s.participant_name
        if name not in grouped:
            grouped[name] = DebtSummary(name, 0.0, 0)
        if s.amount_owed is not None:
            grouped[name].total_known += float(s.amount_owed)
        else:
            grouped[name].count_unknown += 1

    return list(grouped.values())


async def _fetch_debt_details(
    session: AsyncSession, user_id: int, participant_name: str
) -> list[tuple[SharedExpense, Expense]]:
    rows = (
        await session.execute(
            select(SharedExpense, Expense)
            .join(Expense, SharedExpense.expense_id == Expense.id)
            .where(
                Expense.user_id == user_id,
                SharedExpense.participant_name == participant_name,
                SharedExpense.is_returned.is_(False),
            )
            .order_by(Expense.expense_date.desc())
        )
    ).all()
    return [(s, e) for s, e in rows]


# ── Render helpers ────────────────────────────────────────────────────────────

async def _render_history(
    target: Message,
    session: AsyncSession,
    user_id: int,
    page: int,
    *,
    edit: bool,
) -> None:
    rows, total = await _fetch_history_page(session, user_id, page)
    text = format_history_page(rows, page, total, PAGE_SIZE)
    kb = history_keyboard(page, total, PAGE_SIZE)
    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


async def _render_debts(
    target: Message,
    session: AsyncSession,
    user_id: int,
    *,
    edit: bool,
) -> None:
    debts = await _fetch_debts(session, user_id)
    text = format_debts_summary(debts)
    kb = debts_keyboard(debts)
    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.message(F.text == "📋 История")
async def cmd_history(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await _render_history(message, session, message.from_user.id, page=0, edit=False)


@router.message(Command("debts"))
async def cmd_debts(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await _render_debts(message, session, message.from_user.id, edit=False)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("hist:page:"))
async def cb_history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(callback.data.split(":")[2])
    await _render_history(
        callback.message, session, callback.from_user.id, page, edit=True
    )
    await callback.answer()


@router.callback_query(F.data == "hist:debts")
async def cb_debts_from_history(callback: CallbackQuery, session: AsyncSession) -> None:
    await _render_debts(callback.message, session, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "debts:back")
async def cb_debts_back(callback: CallbackQuery, session: AsyncSession) -> None:
    await _render_debts(callback.message, session, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("debts:paid:"))
async def cb_debt_paid(callback: CallbackQuery, session: AsyncSession) -> None:
    participant_name = callback.data[len("debts:paid:"):]
    user_id = callback.from_user.id

    await session.execute(
        update(SharedExpense)
        .where(
            SharedExpense.expense_id.in_(
                select(Expense.id).where(Expense.user_id == user_id)
            ),
            SharedExpense.participant_name == participant_name,
            SharedExpense.is_returned.is_(False),
        )
        .values(is_returned=True)
    )
    await session.commit()
    logger.info("Marked all debts from '%s' as returned for user %s", participant_name, user_id)

    await _render_debts(callback.message, session, user_id, edit=True)
    await callback.answer(f"Долги от {participant_name} отмечены как полученные ✅")


@router.callback_query(F.data.startswith("debts:details:"))
async def cb_debt_details(callback: CallbackQuery, session: AsyncSession) -> None:
    participant_name = callback.data[len("debts:details:"):]
    items = await _fetch_debt_details(session, callback.from_user.id, participant_name)
    text = format_debt_details(participant_name, items)
    await callback.message.edit_text(
        text,
        reply_markup=debt_details_keyboard(participant_name),
        parse_mode="HTML",
    )
    await callback.answer()
