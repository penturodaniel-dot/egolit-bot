"""
Перший LLM-виклик: витягуємо намір і параметри з вільного тексту.
AI знає реальні категорії з БД і повертає точні category_ids.
"""
import json
from typing import Optional
from openai import AsyncOpenAI
from pydantic import BaseModel
from config import settings
from db.categories_cache import get_categories_prompt, expand_category_ids

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class ParsedIntent(BaseModel):
    intent: str                            # "service" | "event" | "lead" | "other"
    category_ids: list[int]               # [100, 155] — точні ID з БД
    max_price: Optional[int]              # 1500
    needs_clarification: bool
    clarification_question: Optional[str]


def _build_system_prompt() -> str:
    categories = get_categories_prompt()
    return f"""Ти — асистент Egolist, маркетплейс послуг для організації заходів та дозвілля в Україні.
Твоя задача: проаналізувати запит і повернути JSON.

ДОСТУПНІ КАТЕГОРІЇ (використовуй ТІЛЬКИ ці id):
{categories}

ПРАВИЛА:
- intent = "service" — шукають виконавця або послугу
- intent = "event"   — шукають події або заходи куди піти
- intent = "lead"    — хочуть залишити заявку або поговорити з менеджером
- intent = "other"   — незрозуміло що потрібно
- category_ids — список id категорій з таблиці вище (масив цілих чисел, НЕ порожній якщо intent=service)
- max_price — максимальний бюджет якщо вказано (ціле число або null)
- needs_clarification = true ТІЛЬКИ якщо взагалі неможливо визначити що потрібно
- clarification_question — коротке питання якщо needs_clarification=true

ПРИКЛАДИ:
"фотограф на весілля" → {{"intent":"service","category_ids":[155],"max_price":null,"needs_clarification":false,"clarification_question":null}}
"аніматор для дитини до 2000 грн" → {{"intent":"service","category_ids":[100],"max_price":2000,"needs_clarification":false,"clarification_question":null}}
"організувати корпоратив" → {{"intent":"service","category_ids":[339,331,325],"max_price":null,"needs_clarification":false,"clarification_question":null}}
"хочу залишити заявку" → {{"intent":"lead","category_ids":[],"max_price":null,"needs_clarification":false,"clarification_question":null}}

Відповідай ТІЛЬКИ валідним JSON без пояснень."""


async def parse_intent(user_text: str, history: list[dict] | None = None) -> ParsedIntent:
    messages = [{"role": "system", "content": _build_system_prompt()}]

    if history:
        messages.extend(history[-4:])

    messages.append({"role": "user", "content": user_text})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=300,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    # Захист: AI може повернути рядки замість чисел
    raw_ids = data.get("category_ids", [])
    if isinstance(raw_ids, str):
        raw_ids = []
    category_ids = [int(i) for i in raw_ids if str(i).isdigit()]

    # Розширюємо: якщо вибрана батьківська категорія — додаємо всі дочірні
    if category_ids:
        category_ids = expand_category_ids(category_ids)

    return ParsedIntent(
        intent=data.get("intent", "other"),
        category_ids=category_ids,
        max_price=data.get("max_price"),
        needs_clarification=data.get("needs_clarification", False),
        clarification_question=data.get("clarification_question"),
    )
