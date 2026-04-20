"""
Перший LLM-виклик: витягуємо намір і параметри з вільного тексту.
"""
import json
from typing import Optional
from openai import AsyncOpenAI
from pydantic import BaseModel
from config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class ParsedIntent(BaseModel):
    intent: str                          # "service" | "event" | "lead" | "other"
    category_keywords: list[str]         # ["аніматор", "фотограф", ...]
    max_price: Optional[int]             # 1500
    needs_clarification: bool            # треба уточнення?
    clarification_question: Optional[str]  # питання якщо треба


SYSTEM_PROMPT = """Ти — асистент Egolist, маркетплейс послуг для організації заходів та дозвілля.
Твоя задача: проаналізувати запит користувача і повернути JSON.

Категорії послуг на платформі: аніматори, фотографи, відеографи, декоратори, флористи,
кейтеринг, торти, організатори свят, ведучі, DJ, дитячі локації, квести, конструкції для заходів,
ростові ляльки, клоуни, фокусники, makeup-майстри, бренд-шефи та інші.

Правила:
- intent = "service" якщо шукають виконавця/послугу
- intent = "event" якщо шукають події/заходи куди піти
- intent = "lead" якщо хочуть залишити заявку або поговорити з менеджером
- intent = "other" якщо незрозуміло
- needs_clarification = true тільки якщо ВЗАГАЛІ незрозуміло що потрібно
- category_keywords — ключові слова для пошуку (українською або російською)
- max_price — максимальний бюджет якщо вказано (число)

Відповідай ТІЛЬКИ валідним JSON без пояснень."""


async def parse_intent(user_text: str, history: list[dict] | None = None) -> ParsedIntent:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history[-4:])  # останні 2 обміни

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

    # Захист: AI може повернути рядок замість списку
    keywords = data.get("category_keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    return ParsedIntent(
        intent=data.get("intent", "other"),
        category_keywords=keywords,
        max_price=data.get("max_price"),
        needs_clarification=data.get("needs_clarification", False),
        clarification_question=data.get("clarification_question"),
    )
