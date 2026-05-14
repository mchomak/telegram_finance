# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Что это за проект

Telegram-бот для учёта личных расходов с голосовым вводом, GPT-категоризацией и отслеживанием совместных трат. Рассчитан на несколько пользователей одновременно.

---

## Стек

| Слой | Технология |
|---|---|
| Язык | Python 3.12 |
| Telegram | aiogram 3.x |
| База данных | PostgreSQL 16 + SQLAlchemy 2.x async + asyncpg |
| Миграции | Alembic |
| Транскрипция | openai-whisper (локально) |
| AI-парсинг | OpenAI API — gpt-4o-mini |
| Excel-экспорт | openpyxl |
| Конфигурация | pydantic-settings (.env) |
| Деплой | Docker + docker-compose |

---

## Структура проекта

```
expense-bot/
├── bot/
│   ├── main.py                  # Точка входа, запуск polling
│   ├── config.py                # Настройки через pydantic-settings
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py             # /start, онбординг, reply-клавиатура
│   │   ├── voice.py             # Приём голосовых сообщений
│   │   ├── confirm.py           # FSM: подтверждение и редактирование записи
│   │   ├── settings.py          # Управление категориями
│   │   ├── history.py           # История + пагинация + долги
│   │   └── export.py            # Экспорт в Excel
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcription.py     # Whisper: скачать audio → текст
│   │   └── parser.py            # GPT: текст → структурированный JSON
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py              # DeclarativeBase, engine, session factory
│   │   ├── middleware.py        # Прокидывает сессию в handlers
│   │   └── models.py            # Все модели: User, Category, Expense, SharedExpense
│   └── utils/
│       ├── __init__.py
│       ├── formatting.py        # Форматирование сообщений (суммы, даты, участники)
│       └── keyboards.py         # Все клавиатуры: reply и inline
├── migrations/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Переменные окружения (.env)

```env
BOT_TOKEN=                        # Telegram Bot Token
OPENAI_API_KEY=                   # OpenAI API Key
WHISPER_MODEL=base                # tiny | base | small | medium
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/expensebot
POSTGRES_USER=expensebot
POSTGRES_PASSWORD=secret
POSTGRES_DB=expensebot
```

---

## База данных — модели

### User
```
telegram_id  BIGINT  PRIMARY KEY
username     TEXT    nullable
created_at   TIMESTAMP
```

### Category
```
id           SERIAL  PRIMARY KEY
user_id      BIGINT  FK → User
name         TEXT
emoji        TEXT    nullable
is_active    BOOL    default true
```
При первом `/start` пользователю сидируются категории по умолчанию:
`Еда 🍎`, `Транспорт 🚗`, `Развлечения 🎉`, `Здоровье 💊`, `Прочее 📦`

### Expense
```
id            SERIAL   PRIMARY KEY
user_id       BIGINT   FK → User
amount        NUMERIC(10,2)  nullable  — может быть неизвестна
category_id   INT      FK → Category  nullable
transcription TEXT     — оригинальная расшифровка голосового
note          TEXT     nullable  — короткое описание от GPT
expense_date  DATE     — дата траты (из текста или дата сообщения)
created_at    TIMESTAMP
```

### SharedExpense
```
id                SERIAL   PRIMARY KEY
expense_id        INT      FK → Expense
participant_name  TEXT
amount_owed       NUMERIC(10,2)  nullable  — null если сумма неизвестна
item_description  TEXT     nullable  — например "пиво и шоколадка"
is_returned       BOOL     default false
```
Если `amount_owed IS NULL` — долг помечается как «сумма неизвестна», в сводке долгов показывается отдельно.

---

## Основные сценарии использования

### 1. Голосовое сообщение → запись

```
Пользователь отправляет voice →
  transcription.py: скачать файл → Whisper → текст →
  parser.py: текст + список категорий пользователя → GPT → JSON →
  confirm.py: показать подтверждение с inline-кнопками
```

Сообщение подтверждения выглядит так:
```
Пятёрочка, 🍎 Еда, 450₽ — верно?
👥 Серёга (500₽), Маша (пиво и шоколадка)

> [полная расшифровка голосового в блокцитате]

[✅ Подтвердить]  [✏️ Править]
```

### 2. Редактирование (нажал "Править")

FSM-состояния:
- Показать inline-кнопки: `Сумма | Категория | Участники | Дата`
- Пользователь нажимает поле → вводит новое значение текстом
- После ввода — снова показать подтверждение с обновлёнными данными

### 3. Reply-клавиатура (всегда видна)

```
[⚙️ Настройки]  [📋 История]  [📤 Экспорт]
```

---

## GPT-парсинг — формат ответа

parser.py отправляет в GPT системный промпт + транскрипцию.
GPT **всегда** возвращает чистый JSON без markdown-обёртки:

```json
{
  "amount": 450.00,
  "category": "Еда",
  "expense_date": null,
  "note": "Пятёрочка, продукты",
  "participants": [
    {
      "name": "Серёга",
      "amount_owed": 500.00,
      "item_description": null
    },
    {
      "name": "Маша",
      "amount_owed": null,
      "item_description": "пиво и шоколадка"
    }
  ]
}
```

Правила для GPT:
- `category` выбирается **только** из переданного списка категорий пользователя. Никаких своих категорий.
- Если сумма не упомянута — `amount: null`
- Если дата не упомянута — `expense_date: null` (будет использована дата сообщения)
- Если участник есть, но сумма неизвестна — `amount_owed: null`, заполнить `item_description`
- Весь текст на русском, хранить как есть (UTF-8)

---

## Excel-экспорт — структура файла

**Лист 1 — «Сводка»**
- Строки = дни периода (только те, где есть траты)
- Колонки = категории пользователя
- Ячейки = сумма трат за день по категории
- Последняя строка = итого по категории
- Последняя колонка = итого за день

**Лист 2 — «История»**
Колонки: `Дата | Время | Расшифровка | Описание | Категория | Сумма | Участники | Статус возврата`
- Участники: `Серёга (500₽), Маша (пиво и шоколадка)`
- Статус: `ожидается` / `получен`
- Сортировка по дате по убыванию

Имя файла: `расходы_апрель_2025.xlsx`
Кодировка: UTF-8, шрифт Calibri (поддерживает кириллицу по умолчанию).

---

## Команды и навигация

| Триггер | Действие |
|---|---|
| `/start` | Регистрация, сидирование категорий, онбординг, reply-клавиатура |
| `/debts` | Сводка долгов: кто сколько должен |
| `⚙️ Настройки` | Управление категориями (список / добавить / удалить) |
| `📋 История` | Последние 10 трат с пагинацией + кнопка долгов |
| `📤 Экспорт` | Выбор периода → скачать .xlsx |
| `voice message` | Главный сценарий — транскрипция → подтверждение |

---

## Соглашения по коду

- Весь код и комментарии — **на английском**
- Все строки, которые видит пользователь в боте — **на русском**
- Async везде: handlers, db-запросы, вызовы API
- Сессия БД прокидывается через `middleware` — не создавать сессии внутри handlers вручную
- FSM-состояния хранить в `handlers/confirm.py` (для редактирования записи) и `handlers/settings.py` (для добавления категории)
- Клавиатуры собирать в `utils/keyboards.py`, не inline прямо в handlers
- Форматирование сумм, дат, списков участников — в `utils/formatting.py`
- При старте: дождаться готовности БД (retry loop), затем `alembic upgrade head`

---

## Docker

Запуск:
```bash
cp .env.example .env
# заполнить .env
docker compose up -d
```

Обновление:
```bash
git pull
docker compose up -d --build
```

Сервисы:
- `bot` — основной контейнер, зависит от `db`
- `db` — postgres:16-alpine, named volume `pgdata`, healthcheck

---

## Порядок реализации (промпты)

1. **Скелет + голос** — бот принимает voice, возвращает расшифровку Whisper
2. **БД** — модели, миграции, middleware с сессией
3. **GPT + подтверждение** — парсинг, FSM редактирования, сохранение в БД
4. **Настройки + /start** — онбординг, управление категориями, reply-клавиатура
5. **История + долги** — список трат с пагинацией, /debts
6. **Экспорт** — генерация .xlsx с двумя листами
7. **Docker** — Dockerfile, docker-compose, README