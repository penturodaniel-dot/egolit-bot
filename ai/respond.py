"""
Другий LLM-виклик: форматуємо людську відповідь на основі даних з БД.
"""
import json
from openai import AsyncOpenAI
from db.queries import ProductResult, EventResult
from config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Ти — міський помічник Egolist. Відповідаєш дружньо, лаконічно, по-українськи.

Правила:
- Використовуй ТІЛЬКИ дані які надані. Нічого не вигадуй.
- Для кожної позиції: назва жирним, коротко чому підходить, ціна якщо є.
- Максимум 3-4 речення на позицію.
- Не використовуй слова "звичайно", "безперечно", "чудово" — будь природним.
- Emoji помірно: 1-2 на відповідь, не більше.
- Якщо результатів немає — чесно скажи і запропонуй змінити запит."""


def _format_products_for_prompt(products: list[ProductResult]) -> str:
    items = []
    for p in products:
        item = f"- {p.name} ({p.category})"
        if p.price:
            item += f", від {p.price} грн"
        if p.description:
            item += f". {p.description[:150]}"
        items.append(item)
    return "\n".join(items)


def _format_events_for_prompt(events: list[EventResult]) -> str:
    items = []
    for e in events:
        item = f"- {e.title}, {e.date}"
        if e.time:
            item += f" о {e.time}"
        if e.price:
            item += f", {e.price}"
        if e.place_name:
            item += f", {e.place_name}"
        items.append(item)
    return "\n".join(items)


async def format_response(
    user_query: str,
    products: list[ProductResult] | None = None,
    events: list[EventResult] | None = None,
) -> str:
    if products:
        data_block = f"Знайдені послуги:\n{_format_products_for_prompt(products)}"
        task = f'Користувач шукав: "{user_query}". Склади відповідь з рекомендаціями.'
    elif events:
        data_block = f"Знайдені події:\n{_format_events_for_prompt(events)}"
        task = f'Користувач шукав: "{user_query}". Склади відповідь про найближчі події.'
    else:
        data_block = "Результатів не знайдено."
        task = f'Користувач шукав: "{user_query}". Повідом що нічого не знайдено і запропонуй 2 варіанти: змінити запит або поговорити з менеджером.'

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{data_block}\n\n{task}"},
    ]

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,
        max_tokens=600,
    )

    return response.choices[0].message.content
