from dataclasses import dataclass
from datetime import date

from bot.db.models import Category, Expense, SharedExpense
from bot.services.parser import ParsedExpense, ParsedParticipant

_MONTHS = ["янв", "фев", "мар", "апр", "май", "июн",
           "июл", "авг", "сен", "окт", "ноя", "дек"]


def _fmt_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]}"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_amount(amount: float | None) -> str:
    if amount is None:
        return "сумма неизвестна"
    whole = int(amount)
    if amount == whole:
        return f"{whole:,}₽".replace(",", "\u202f")
    return f"{amount:,.2f}₽".replace(",", "\u202f")


def format_participant(p: ParsedParticipant) -> str:
    if p.amount_owed is not None:
        return f"{p.name} ({format_amount(p.amount_owed)})"
    if p.item_description:
        return f"{p.name} ({p.item_description})"
    return p.name


def format_confirmation(
    parsed: ParsedExpense,
    category_emoji: str | None,
    transcription: str,
) -> str:
    note = parsed.note or "Трата"
    category_part = ""
    if parsed.category:
        prefix = f"{category_emoji} " if category_emoji else ""
        category_part = f", {prefix}{parsed.category}"

    first_line = f"{note}{category_part}, {format_amount(parsed.amount)} — верно?"
    lines = [first_line]

    if parsed.participants:
        parts = ", ".join(format_participant(p) for p in parsed.participants)
        lines.append(f"👥 {parts}")

    lines.append("")
    lines.append(f"<blockquote>{_escape_html(transcription)}</blockquote>")
    return "\n".join(lines)


# ── History ───────────────────────────────────────────────────────────────────

def format_expense_row(expense: Expense, category: Category | None) -> str:
    date_str = _fmt_date(expense.expense_date)
    if category:
        emoji = f"{category.emoji} " if category.emoji else ""
        cat_str = f"  {emoji}{category.name},"
    else:
        cat_str = ""
    amount_str = format_amount(float(expense.amount) if expense.amount is not None else None)
    note_str = f" — {_escape_html(expense.note)}" if expense.note else ""
    return f"<b>{date_str}</b>{cat_str} {amount_str}{note_str}"


def format_history_page(
    rows: list[tuple[Expense, Category | None]],
    page: int,
    total: int,
    page_size: int = 10,
) -> str:
    if not rows:
        return "📋 <b>История</b>\n\nТрат пока нет."
    total_pages = max(1, (total + page_size - 1) // page_size)
    header = f"📋 <b>История</b>  <i>(стр. {page + 1} из {total_pages})</i>"
    lines = [header, ""]
    for expense, category in rows:
        lines.append(format_expense_row(expense, category))
    return "\n".join(lines)


# ── Debts ─────────────────────────────────────────────────────────────────────

@dataclass
class DebtSummary:
    participant_name: str
    total_known: float
    count_unknown: int


def format_debts_summary(debts: list[DebtSummary]) -> str:
    if not debts:
        return "💸 <b>Долги</b>\n\nВсе долги погашены 🎉"
    lines = ["💸 <b>Долги</b>", ""]
    for d in debts:
        parts: list[str] = []
        if d.total_known > 0:
            parts.append(format_amount(d.total_known))
        if d.count_unknown > 0:
            suffix = f"+ {d.count_unknown} без суммы" if parts else f"{d.count_unknown} без суммы"
            parts.append(suffix)
        summary = ", ".join(parts) or "сумма неизвестна"
        lines.append(f"<b>{_escape_html(d.participant_name)}</b>: {summary}")
    return "\n".join(lines)


def format_debt_details(
    participant_name: str,
    items: list[tuple[SharedExpense, Expense]],
) -> str:
    lines = [f"📋 <b>Детали — {_escape_html(participant_name)}</b>", ""]
    for shared, expense in items:
        date_str = _fmt_date(expense.expense_date)
        amount_str = (
            format_amount(float(shared.amount_owed))
            if shared.amount_owed is not None
            else "сумма неизвестна"
        )
        desc = shared.item_description or expense.note or ""
        entry = f"{date_str} — {amount_str}"
        if desc:
            entry += f" ({_escape_html(desc)})"
        lines.append(f"• {entry}")
    return "\n".join(lines)
