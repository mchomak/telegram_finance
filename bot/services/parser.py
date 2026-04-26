import json
import logging
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

from bot.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # Route OpenAI requests through the configured SOCKS5 proxy so the bot
        # can reach api.openai.com from servers where direct access is blocked.
        http_client = (
            httpx.AsyncClient(proxy=settings.proxy_url)
            if settings.proxy_url
            else None
        )
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=http_client,
            timeout=60.0,  # fail after 60 s instead of hanging for 10 minutes
        )
        if settings.proxy_url:
            logger.info("OpenAI client using proxy: %s", settings.proxy_url.split("@")[-1])
    return _client


_SYSTEM_PROMPT = """Ты — ассистент для учёта личных расходов. Разбираешь русскоязычные транскрипции голосовых сообщений в JSON.

Извлеки следующие поля:
- amount: число (float) или null, если сумма не упомянута
- category: строка — выбери ТОЛЬКО из предоставленного списка категорий, или null если ни одна не подходит
- expense_date: "YYYY-MM-DD" или null, если дата не упомянута
- note: короткое описание траты на русском (1-2 слова, например "Пятёрочка, продукты")
- participants: список объектов {name, amount_owed, item_description}
  - name: имя человека
  - amount_owed: float или null, если сумма не известна
  - item_description: строка или null — что купили для этого человека (если сумма не известна)

Правила:
- Если у участника нет суммы, но есть описание товаров — ставь amount_owed=null, заполняй item_description
- Возвращай ТОЛЬКО валидный JSON без markdown, без пояснений
- Все текстовые поля — на русском языке"""


@dataclass
class ParsedParticipant:
    name: str
    amount_owed: float | None
    item_description: str | None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "amount_owed": self.amount_owed,
            "item_description": self.item_description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParsedParticipant":
        return cls(
            name=d["name"],
            amount_owed=d.get("amount_owed"),
            item_description=d.get("item_description"),
        )


@dataclass
class ParsedExpense:
    amount: float | None
    category: str | None
    expense_date: str | None  # ISO "YYYY-MM-DD" or None
    note: str | None
    participants: list[ParsedParticipant] = field(default_factory=list)


async def parse_expense(transcription: str, categories: list[str]) -> ParsedExpense:
    client = _get_client()
    category_list = ", ".join(categories) if categories else "нет категорий"
    user_msg = f"Категории: {category_list}\n\nТранскрипция: {transcription}"

    logger.info("Sending transcription to GPT for parsing")
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content
    logger.info("GPT response: %s", raw)
    data = json.loads(raw)

    participants = [
        ParsedParticipant(
            name=p["name"],
            amount_owed=p.get("amount_owed"),
            item_description=p.get("item_description"),
        )
        for p in data.get("participants") or []
    ]

    return ParsedExpense(
        amount=data.get("amount"),
        category=data.get("category"),
        expense_date=data.get("expense_date"),
        note=data.get("note"),
        participants=participants,
    )
