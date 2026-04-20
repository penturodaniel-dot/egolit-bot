"""
Другий LLM-виклик: генеруємо ТІЛЬКИ короткий вступ (1 речення).
Деталі по кожній позиції — в окремих картках, не тут.
"""
from openai import AsyncOpenAI
from db.queries import ProductResult, EventResult
from config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Ти — помічник Egolist. Відповідай по-українськи, дружньо, коротко.

Твоя задача: написати ОДНЕ коротке вступне речення до результатів пошуку.
НЕ перераховуй результати — вони вже будуть показані окремо.
НЕ описуй кожен варіант — тільки загальний вступ.

Приклади:
- "Знайшов кілька фотографів у Дніпрі 👇"
- "Ось аніматори, які підійдуть для дитячого свята 👇"
- "Знайшов варіанти для організації корпоративу 👇"

Якщо результатів немає — одне речення що нічого не знайдено і варто змінити запит або звернутись до менеджера."""


async def format_intro(
    user_query: str,
    has_results: bool,
    count: int = 0,
) -> str:
    if has_results:
        task = f'Запит: "{user_query}". Знайдено {count} варіантів. Напиши вступне речення.'
    else:
        task = f'Запит: "{user_query}". Нічого не знайдено. Напиши одне речення про це.'

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ],
        temperature=0.4,
        max_tokens=80,
    )

    return response.choices[0].message.content
