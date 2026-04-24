"""
Перший LLM-виклик: витягуємо намір і параметри з вільного тексту.
AI знає реальні категорії Egolist і повертає category_names (рядки).
"""
import json
from typing import Optional
from openai import AsyncOpenAI
from pydantic import BaseModel
from config import settings
from db.egolist_api import get_categories_prompt

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Russian → Ukrainian character normalization (fallback if AI doesn't transliterate)
_RU_TO_UK = str.maketrans({
    'ы': 'и', 'Ы': 'И',
    'э': 'е', 'Э': 'Е',
    'ё': 'е', 'Ё': 'Е',
    'ъ': '',  'Ъ': '',
})


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
Ти — асистент Egolist, маркетплейс послуг для організації заходів та дозвілля в Дніпрі (Україна).
Твоя задача: проаналізувати запит і повернути JSON.

ВАЖЛИВО: Ми працюємо ТІЛЬКИ в місті Дніпро. НІКОЛИ не питай про місто — воно завжди Дніпро.
НІКОЛИ не питай уточнень якщо є хоч якийсь натяк на категорію послуги чи події — відразу шукай.
needs_clarification = true ЛИШЕ якщо запит абсолютно беззмістовний (наприклад, "привіт", "тест", "?").

ДОСТУПНІ КАТЕГОРІЇ ПОСЛУГ:
{categories}

ПРАВИЛА intent:
- "service" — шукають виконавця або послугу, яка Є У НАШОМУ СПИСКУ КАТЕГОРІЙ ВИЩЕ
  (фотограф, ді-джей, аніматор, ведучий, тамада, живий звук, кейтеринг, ресторани тощо)
- "event"   — шукають подію або захід куди піти (концерт, вистава, фестиваль, стендап, фільм у кіно тощо)
- "lead"    — хочуть залишити заявку, поговорити з менеджером, дізнатись ціну, замовити
- "other"   — запит НЕ співпадає з нашим списком категорій (кальян, салони краси,
              автосервіс, доставка їжі, таксі, готелі тощо) АБО абсолютно
              беззмістовний (привіт, тест, 1234). Egolist — маркетплейс по всій
              Україні, можливо ми колись додамо такі послуги, тому НЕ кажи
              категорично "ми цим не займаємось".

              Для "other" постав needs_clarification=true і в clarification_question
              напиши коротко та ввічливо:
              "На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись
              до менеджера — натисни кнопку 'Живий чат' або '📝 Залишити заявку'
              і ми підберемо варіант для вас."

ПРАВИЛА полів:
- category_names — масив рядків з назвами категорій ТІЛЬКИ якщо intent=service.
  Вибирай з наведеного списку. Можна кілька. Порожній масив якщо не підходить жодна.
- event_category — якщо intent=event: "концерти"|"виставки"|"кіно"|"для дітей"|"активний відпочинок"|"майстер-класи" або null (null = всі категорії)
- date_filter — якщо intent=event: "today"|"weekend"|"week"|"month" або null (всі майбутні)
- search_text — конкретне ім'я виконавця, артиста, назва події або ключове слово.
  ЗАВЖДИ нормалізуй до **української** мови: якщо написано по-російськи — транслітеруй.
  Правила транслітерації рос→укр: "ы"→"и", "э"→"е", "ё"→"е", "ъ"→"".
  Приклади: "Оля Цыбульская"→"Оля Цибульська", "Григорий Чапкис"→"Григорій Чапкіс".
  Якщо запит уже українською — залишай без змін. Інакше null.
- max_price — максимальний бюджет якщо вказано (ціле число або null)
- needs_clarification — true ТІЛЬКИ якщо запит повністю беззмістовний
- clarification_question — коротке питання ТІЛЬКИ якщо needs_clarification=true

ПРИКЛАДИ:
"фотограф" → {{"intent":"service","category_names":["фото та відеозйомка"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"ді-джей до 3000 грн" → {{"intent":"service","category_names":["музиканти"],"event_category":null,"search_text":null,"date_filter":null,"max_price":3000,"needs_clarification":false,"clarification_question":null}}
"аніматор для дітей" → {{"intent":"service","category_names":["аніматори"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"ведучий на весілля" → {{"intent":"service","category_names":["ведучі"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"концерт Ольги Тополі" → {{"intent":"event","category_names":[],"event_category":"концерти","search_text":"Ольга Тополя","date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"куди сьогодні піти" → {{"intent":"event","category_names":[],"event_category":null,"search_text":null,"date_filter":"today","max_price":null,"needs_clarification":false,"clarification_question":null}}
"що йде в кіно" → {{"intent":"event","category_names":[],"event_category":"кіно","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"дитячий спектакль або розвага для дітей" → {{"intent":"event","category_names":[],"event_category":"для дітей","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"концерти та фестивалі найближчим часом" → {{"intent":"event","category_names":[],"event_category":"концерти","search_text":null,"date_filter":"week","max_price":null,"needs_clarification":false,"clarification_question":null}}
"виставка або галерея" → {{"intent":"event","category_names":[],"event_category":"виставки","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"активний відпочинок або спорт" → {{"intent":"event","category_names":[],"event_category":"активний відпочинок","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"майстер-клас або воркшоп" → {{"intent":"event","category_names":[],"event_category":"майстер-класи","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"романтичний захід або вечір для двох" → {{"intent":"event","category_names":[],"event_category":null,"search_text":"романтика","date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"вечірка або концерт для друзів" → {{"intent":"event","category_names":[],"event_category":"концерти","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"знайди виконавця або артиста для свята" → {{"intent":"service","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"хочу залишити заявку" → {{"intent":"lead","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"ресторан для корпоративу" → {{"intent":"service","category_names":["ресторани та банкетні зали"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"де покурити кальян в центрі Києва?" → {{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."}}
"доставка піци" → {{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."}}
"салон краси" → {{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."}}

Відповідай ТІЛЬКИ валідним JSON без пояснень."""


def _build_system_prompt(extra_instructions: str = "") -> str:
    categories = get_categories_prompt()
    extra = f"\nДОДАТКОВІ ІНСТРУКЦІЇ ВІД АДМІНА:\n{extra_instructions.strip()}\n" if extra_instructions.strip() else ""
    return BASE_PROMPT_TEXT.format(categories=categories) + extra


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
        model="gpt-4o-mini",
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=300,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    # category_names — масив рядків
    raw_names = data.get("category_names", [])
    if isinstance(raw_names, str):
        raw_names = [raw_names] if raw_names else []
    category_names = [str(n).strip().lower() for n in raw_names if n]

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
