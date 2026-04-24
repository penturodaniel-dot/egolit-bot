"""
AI-відповіді: вступний текст + пояснення чому кожен варіант підходить.
"""
import json
from openai import AsyncOpenAI
from db.queries import ProductResult, EventResult
from config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

INTRO_PROMPT = """Ти — помічник Egolist. Відповідай по-українськи, дружньо, коротко.

Твоя задача: написати ОДНЕ коротке вступне речення до результатів пошуку.
НЕ перераховуй результати — вони вже будуть показані окремо.
НЕ описуй кожен варіант — тільки загальний вступ.

Приклади:
- "Знайшов кілька фотографів у Дніпрі 👇"
- "Ось аніматори, які підійдуть для дитячого свята 👇"
- "Знайшов варіанти для організації корпоративу 👇"

Якщо результатів немає — одне речення що нічого не знайдено і варто змінити запит або звернутись до менеджера."""

REASONS_PROMPT = """Ти — помічник Egolist. Відповідай по-українськи.

Тобі дають запит користувача і список знайдених варіантів.
Для кожного варіанту напиши 1 коротке речення (15-25 слів) — чому саме він підходить під цей запит.
Фокусуйся на конкретній причині відповідності, а не загальному описі.

Відповідай ТІЛЬКИ валідним JSON-масивом рядків, без пояснень:
["причина для варіанту 1", "причина для варіанту 2", ...]

Якщо варіантів більше ніж у списку — поверни стільки елементів скільки варіантів."""


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
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": INTRO_PROMPT},
            {"role": "user", "content": task},
        ],
        max_completion_tokens=200,
        reasoning_effort="minimal",
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        # Fallback if model returns empty
        text = "Ось що знайшов 👇" if has_results else "На жаль, нічого не знайдено. Спробуй інший запит або натисни '📝 Залишити заявку'."
    return text


async def generate_match_reasons(
    user_query: str,
    products: list[ProductResult] | None = None,
    events: list[EventResult] | None = None,
) -> list[str]:
    """Generate one-sentence 'why this fits' for each result. Returns list aligned to results."""
    items = products or events or []
    if not items:
        return []

    # Build a compact list for the AI
    lines = []
    for i, item in enumerate(items, 1):
        if isinstance(item, ProductResult):
            desc = f"{item.name} — {item.category or ''}"
            if item.price:
                desc += f", від {item.price} грн"
            if item.description:
                desc += f". {item.description[:120]}"
        else:  # EventResult
            desc = f"{item.title}"
            if item.date:
                desc += f" ({item.date})"
            if item.price:
                desc += f", {item.price}"
            if item.place_name:
                desc += f" @ {item.place_name}"

        lines.append(f"{i}. {desc}")

    task = (
        f'Запит: "{user_query}"\n\n'
        f'Варіанти:\n' + "\n".join(lines) +
        "\n\nПоясни для кожного чому він підходить під запит."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": REASONS_PROMPT},
                {"role": "user", "content": task},
            ],
            max_completion_tokens=800,
            reasoning_effort="minimal",
        )
        raw = response.choices[0].message.content.strip()
        reasons = json.loads(raw)
        if isinstance(reasons, list):
            # Pad or trim to match items count
            while len(reasons) < len(items):
                reasons.append("")
            return reasons[:len(items)]
    except Exception:
        pass

    return [""] * len(items)
