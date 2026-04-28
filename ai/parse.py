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
Ти — асистент платформи Egolist, каталог послуг для організації заходів у Дніпрі (Україна).
Задача: проаналізувати запит і повернути JSON.

МІСТО: завжди Дніпро. НІКОЛИ не питай про місто.
needs_clarification=true ЛИШЕ якщо запит абсолютно беззмістовний ("привіт", "тест", "?", "1234").

══════════════════════════════════════════════════
КЛЮЧОВЕ ПРАВИЛО РОЗМЕЖУВАННЯ intent:
══════════════════════════════════════════════════
"service" — людина НАЙМАЄ/ШУКАЄ виконавця, спеціаліста, локацію або обладнання ДЛЯ СВОГО ЗАХОДУ.
            Запитання типу: "знайди X", "потрібен X", "є X?", "аніматори", "фотограф".
            → category_names = відповідна категорія з нашого списку.

"event"   — людина хоче СХОДИТИ НА ЗАХІД як ГЛЯДАЧ/ВІДВІДУВАЧ.
            Запитання типу: "куди піти", "що відбувається", "концерт", "вистава",
            "що в кіно", "фестиваль цього тижня".
            → event_category = тип події.

!!! КРИТИЧНО: "аніматор", "аніматори", "клоун" — це ЗАВЖДИ intent="service", НІКОЛИ не "event".
!!! "майстер-клас" як ПОСЛУГА (хочу провести/замовити) → intent="service", category="майстер-класи"
!!! "майстер-клас" як ЗАХІД (хочу відвідати) → intent="event", event_category="майстер-класи"
!!! Якщо є слова "знайди", "потрібен", "є?", "наймаю", "шукаю виконавця" → завжди "service".

ДОСТУПНІ КАТЕГОРІЇ ПОСЛУГ:
{categories}

══════════════════════════════════════════════════
СИНОНІМИ (рос/укр → назва категорії)
══════════════════════════════════════════════════
"аніматор"/"аниматор"/"клоун"/"аніматори" → "аніматори" (intent=service!)
"парикмахер"/"перукар"/"стиліст"/"барбер"/"зачіска" → "візажисти та зачіски"
"визажист"/"макіяж"/"мейк"/"make-up" → "візажисти та зачіски"
"свадьба"/"весілля"/"wedding" → ["ведучі","музиканти","фото та відеозйомка","ресторани та банкетні зали","місця для весільних церемоній"]
"день народження"/"день рождения"/"ДР" → ["ведучі","аніматори","кейтеринг та бар"]
"корпоратив" → ["ведучі","музиканти","ресторани та банкетні зали","артисти та шоу"]
"ресторан"/"кафе"/"банкет" → "ресторани та банкетні зали"
"фотограф"/"відеограф"/"фото"/"видео" → "фото та відеозйомка"
"ді-джей"/"dj"/"диджей" → "музиканти"
"тамада"/"ведущий"/"ведуча" → "ведучі"
"декор"/"оформлення"/"шарики"/"кульки" → "оформлення та декор"
"торт"/"кондитер"/"солодкий стіл" → "кондитери"
"кейтеринг"/"catering"/"фуршет" → "кейтеринг та бар"
"звук"/"колонки"/"мікрофон" → "звукове обладнання"
"світло"/"прожектор"/"освітлення" → "світлове обладнання"
"квест"/"escape room" → "квест-кімнати"
"караоке"/"нічний клуб"/"клуб" → "нічні клуби та караоке"
"готель"/"отель" → "готелі та комплекси"
"фотостудія"/"фотозона" → "фото та відеостудії"
"блогер"/"інфлюенсер" → "блогери"
"танці"/"танцюристи"/"шоу-балет" → "танцювальні шоу"
"музикант" → "музиканти"
"салон краси"/"б'юті" → "візажисти та зачіски"

══════════════════════════════════════════════════
ПРАВИЛА ПОЛІВ
══════════════════════════════════════════════════
category_names — масив категорій ТІЛЬКИ якщо intent=service. Можна кілька.
event_category — ТІЛЬКИ якщо intent=event: "концерти"|"виставки"|"кіно"|"для дітей"|"активний відпочинок"|"майстер-класи"|null
date_filter    — ТІЛЬКИ якщо intent=event: "today"|"weekend"|"week"|"month"|null
search_text    — конкретне ім'я або ключове слово. Транслітеруй рос→укр: ы→и, э→е, ё→е, ъ→"". Або null.
max_price      — бюджет якщо вказано (число або null)
needs_clarification — true ТІЛЬКИ якщо запит беззмістовний
clarification_question — ТІЛЬКИ якщо needs_clarification=true

Для intent="other" постав needs_clarification=true і clarification_question:
"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."

══════════════════════════════════════════════════
ПРИКЛАДИ
══════════════════════════════════════════════════
"Нужны аниматоры" → {{"intent":"service","category_names":["аніматори"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"аніматор для дітей" → {{"intent":"service","category_names":["аніматори"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"потрібен аніматор на день народження" → {{"intent":"service","category_names":["аніматори","ведучі"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"фотограф" → {{"intent":"service","category_names":["фото та відеозйомка"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"ді-джей до 3000 грн" → {{"intent":"service","category_names":["музиканти"],"event_category":null,"search_text":null,"date_filter":null,"max_price":3000,"needs_clarification":false,"clarification_question":null}}
"ведучий на весілля" → {{"intent":"service","category_names":["ведучі","музиканти","фото та відеозйомка"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"ресторан для корпоративу" → {{"intent":"service","category_names":["ресторани та банкетні зали"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"організувати день народження дитини" → {{"intent":"service","category_names":["аніматори","кейтеринг та бар","оформлення та декор"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"нужен звук и свет" → {{"intent":"service","category_names":["звукове обладнання","світлове обладнання"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"квест-комната для компании" → {{"intent":"service","category_names":["квест-кімнати"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"потрібен торт на ювілей" → {{"intent":"service","category_names":["кондитери"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"нужен визажист на свадьбу" → {{"intent":"service","category_names":["візажисти та зачіски"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"А свадьбу можно организовать?" → {{"intent":"service","category_names":["ведучі","музиканти","фото та відеозйомка","ресторани та банкетні зали","місця для весільних церемоній"],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"замовити майстер-клас з кераміки" → {{"intent":"service","category_names":["майстер-класи"],"event_category":null,"search_text":"кераміка","date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"концерт Ольги Тополі" → {{"intent":"event","category_names":[],"event_category":"концерти","search_text":"Ольга Тополя","date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"куди сьогодні піти" → {{"intent":"event","category_names":[],"event_category":null,"search_text":null,"date_filter":"today","max_price":null,"needs_clarification":false,"clarification_question":null}}
"що йде в кіно" → {{"intent":"event","category_names":[],"event_category":"кіно","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"дитячий спектакль" → {{"intent":"event","category_names":[],"event_category":"для дітей","search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"концерти на вихідних" → {{"intent":"event","category_names":[],"event_category":"концерти","search_text":null,"date_filter":"weekend","max_price":null,"needs_clarification":false,"clarification_question":null}}
"відвідати майстер-клас з малювання" → {{"intent":"event","category_names":[],"event_category":"майстер-класи","search_text":"малювання","date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"хочу залишити заявку" → {{"intent":"lead","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":false,"clarification_question":null}}
"доставка піци" → {{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."}}
"де покурити кальян?" → {{"intent":"other","category_names":[],"event_category":null,"search_text":null,"date_filter":null,"max_price":null,"needs_clarification":true,"clarification_question":"На жаль, за цим запитом нічого не знайдено. Рекомендуємо звернутись до менеджера — натисни '📝 Залишити заявку' або 'Живий чат' і ми підберемо варіант для вас."}}

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
