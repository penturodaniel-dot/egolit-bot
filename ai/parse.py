"""
Перший LLM-виклик: витягуємо намір і параметри з вільного тексту.
AI знає реальні категорії Egolist і повертає category_names (рядки).
"""
import json
from typing import Optional
from pydantic import BaseModel
from config import settings
from db.egolist_api import get_categories_prompt
from ai.client import client, build_completion_params

# Russian → Ukrainian character normalization (fallback if AI doesn't transliterate)
_RU_TO_UK = str.maketrans({
    'ы': 'и', 'Ы': 'И',
    'э': 'е', 'Э': 'Е',
    'ё': 'е', 'Ё': 'Е',
    'ъ': '',  'Ъ': '',
})

# Keyword → correct performers category (catches AI mis-classification)
# Keys are lowercase substrings to search in the user query
_KEYWORD_CATEGORY: list[tuple[str, str]] = [
    # Ведучі
    ("ведущ",        "ведучі"),
    ("ведуч",        "ведучі"),
    ("тамада",       "ведучі"),
    ("тамаду",       "ведучі"),
    # Аніматори
    ("аниматор",     "аніматори"),
    ("аніматор",     "аніматори"),
    ("клоун",        "аніматори"),
    # Фото / відео
    ("фотограф",     "фото та відеозйомка"),
    ("відеограф",    "фото та відеозйомка"),
    ("видеограф",    "фото та відеозйомка"),
    ("фотозйомк",    "фото та відеозйомка"),
    # Музиканти / DJ
    ("диджей",       "музиканти"),
    ("ді-джей",      "музиканти"),
    ("dj ",          "музиканти"),
    ("музикант",     "музиканти"),
    ("музыкант",     "музиканти"),
    # Декор
    ("декор",        "оформлення та декор"),
    ("оформлен",     "оформлення та декор"),
    # Кейтеринг
    ("кейтеринг",    "кейтеринг та бар"),
    ("кейтерінг",    "кейтеринг та бар"),
    # Кондитери
    ("кондитер",     "кондитери"),
    ("торт",         "кондитери"),
    # Візажисти
    ("визажист",     "візажисти та зачіски"),
    ("візажист",     "візажисти та зачіски"),
    ("макіяж",       "візажисти та зачіски"),
    ("макияж",       "візажисти та зачіски"),
    ("зачіск",       "візажисти та зачіски"),
    # Ресторани
    ("ресторан",     "ресторани та банкетні зали"),
    ("банкет",       "ресторани та банкетні зали"),
    ("кафе",         "ресторани та банкетні зали"),
    # Локації
    ("квест",        "квест-кімнати"),
    ("готель",       "готелі та комплекси"),
    ("отель",        "готелі та комплекси"),
    ("фотостудія",   "фото та відеостудії"),
    ("фотостудия",   "фото та відеостудії"),
]


def _fix_categories(user_text: str, category_names: list[str]) -> list[str]:
    """If AI returned wrong/empty categories, correct them using keyword matching."""
    low = user_text.lower()
    matched: list[str] = []
    for kw, cat in _KEYWORD_CATEGORY:
        if kw in low:
            if cat not in matched:
                matched.append(cat)
    # Only override if we found a confident keyword match
    if matched:
        return matched
    return category_names


def _normalize_search(text: str | None) -> str | None:
    """Transliterate common Russian characters to Ukrainian equivalents."""
    if not text:
        return text
    return text.translate(_RU_TO_UK)


class ParsedIntent(BaseModel):
    intent: str                            # "service" | "event" | "lead" | "other"
    category_names: list[str]             # ["ведучі", "музиканти"] — назви з нашого списку
    event_category: Optional[str]         # "концерти"|"виставки"|"кіно"|"для дітей"|"активний відпочинок"|"майстер-класи"|null
    date_filter: Optional[str]            # "today" | "weekend" | "week" | "month" | null
    search_text: Optional[str]            # конкретне ім'я або ключове слово (нормалізоване до укр)
    max_price: Optional[int]              # 1500
    needs_clarification: bool
    clarification_question: Optional[str]


BASE_PROMPT_TEXT = """\
Проаналізуй запит користувача і поверни JSON з такими полями:

intent        — "service" | "event" | "lead" | "other"
category_names — масив рядків (назви категорій послуг), або []
event_category — рядок (тип події) або null
date_filter   — "today"|"weekend"|"week"|"month" або null
search_text   — конкретне ім'я або ключове слово, або null. Транслітеруй рос→укр: ы→и, э→е, ё→е, ъ→""
max_price     — максимальний бюджет числом, або null
needs_clarification   — true або false
clarification_question — рядок або null

Відповідай ТІЛЬКИ валідним JSON без пояснень."""


def _build_system_prompt(extra_instructions: str = "") -> str:
    extra = extra_instructions.strip() if extra_instructions.strip() else ""
    return BASE_PROMPT_TEXT + (f"\n\n{extra}" if extra else "")


async def parse_intent(user_text: str, history: list[dict] | None = None) -> ParsedIntent:
    try:
        from db.settings import get_setting
        extra = await get_setting("ai_prompt_extra", "")
    except Exception:
        extra = ""

    messages = [{"role": "system", "content": _build_system_prompt(extra)}]

    if history:
        messages.extend(history[-4:])

    messages.append({"role": "user", "content": user_text})

    response = await client.chat.completions.create(
        messages=messages,
        **build_completion_params(max_tokens=600, temperature=0.1, json_mode=True),
    )

    raw = response.choices[0].message.content
    if not raw:
        # Fallback on empty response from model
        raw = '{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"Уточни, будь ласка, що саме шукаєш?"}'
    data = json.loads(raw)

    # category_names — масив рядків
    raw_names = data.get("category_names", [])
    if isinstance(raw_names, str):
        raw_names = [raw_names] if raw_names else []
    category_names = [str(n).strip().lower() for n in raw_names if n]

    # Override AI categories with keyword-based correction when intent=service
    if data.get("intent") == "service":
        category_names = _fix_categories(user_text, category_names)

    return ParsedIntent(
        intent=data.get("intent", "other"),
        category_names=category_names,
        event_category=data.get("event_category") or None,
        date_filter=data.get("date_filter") or None,
        search_text=_normalize_search(data.get("search_text") or None),
        max_price=data.get("max_price"),
        needs_clarification=data.get("needs_clarification", False),
        clarification_question=data.get("clarification_question"),
    )
