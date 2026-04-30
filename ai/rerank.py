"""
AI-powered search re-ranking + explanation in one LLM call.

Flow:
  DB fetch N candidates  →  GPT-5-mini picks best matches
                         →  writes reason for each
                         →  writes intro sentence
                         →  returns RerankResult

This replaces two separate calls (format_intro + generate_match_reasons)
with ONE combined call, while also dramatically improving result quality
by letting GPT read full descriptions and reason semantically.
"""
import json
import logging
from dataclasses import dataclass, field

from db.queries import ProductResult, EventResult
from ai.client import client, build_completion_params

logger = logging.getLogger(__name__)

# How many DB rows to fetch as candidates for re-ranking
CANDIDATE_FETCH = 15

RERANK_PROMPT = """\
Ти — пошуковий асистент платформи Egolist (Дніпро, Україна).
Допомагаєш підбирати виконавців і афішу подій.

Тобі дають запит користувача і список кандидатів з бази даних.
Проаналізуй кожного кандидата семантично й поверни JSON:

{{
  "top_ids": [id1, id2],
  "reasons": ["чому id1 підходить", "чому id2 підходить"],
  "intro": "Одне вступне речення по-українськи"
}}

ПРАВИЛА:
1. "top_ids" — масив ID найрелевантніших кандидатів, впорядкованих від кращого до гіршого.
   Максимум {top_n} ID. Включай тільки тих, хто ДІЙСНО відповідає запиту.
2. Читай опис кандидата уважно — він важливіший за назву.
   "романтичний вечір" → шукай ресторани/локації з атмосферою, а не просто слово "романтик".
3. "reasons" — по одному реченню (10-20 слів) для кожного вибраного ID.
   ТІЛЬКИ факти з опису, нічого не вигадуй, ніяких "можливо" чи "якщо".
4. "intro" — одне дружнє коротке речення по-українськи. Приклади:
   "Знайшов кількох фотографів, які спеціалізуються на весіллях 👇"
   "Ось аніматори для дитячого свята 👇"
5. Якщо жоден кандидат не підходить — поверни:
   {{"top_ids": [], "reasons": [], "intro": "😔 На жаль, нічого підходящого не знайдено."}}

Відповідай ТІЛЬКИ валідним JSON, без пояснень."""


@dataclass
class RerankResult:
    top_ids: list[int] = field(default_factory=list)
    reasons: dict[int, str] = field(default_factory=dict)   # id → reason
    intro: str = ""


def _build_candidates_text(
    candidates: list[ProductResult] | list[EventResult],
) -> str:
    """Serialize candidates into a compact text block for the prompt."""
    lines = []
    for c in candidates:
        if isinstance(c, ProductResult):
            parts = [f"ID:{c.id}", c.name, c.category or ""]
            if c.price:
                parts.append(f"від {c.price} грн")
            if c.description:
                parts.append(f"Опис: {c.description[:500]}")
        else:  # EventResult
            parts = [f"ID:{c.id}", c.title]
            if c.date:
                parts.append(c.date)
            if c.price:
                parts.append(c.price)
            if c.place_name:
                parts.append(c.place_name)
            if c.description:
                parts.append(f"Опис: {c.description[:500]}")
        lines.append(" | ".join(p for p in parts if p))
    return "\n".join(lines)


async def rerank_and_explain(
    user_query: str,
    candidates: list[ProductResult] | list[EventResult],
    top_n: int = 2,
) -> RerankResult:
    """
    Single LLM call: re-rank candidates + generate reasons + intro.

    Returns RerankResult with:
      - top_ids: ordered list of best-matching IDs (up to top_n)
      - reasons: {id: explanation_text}
      - intro: short Ukrainian intro sentence
    """
    if not candidates:
        return RerankResult(intro="😔 На жаль, нічого не знайдено за твоїм запитом.")

    # If only one candidate (or fewer than top_n) — still go through AI for reason + intro
    candidates_text = _build_candidates_text(candidates)
    prompt = RERANK_PROMPT.format(top_n=top_n)

    task = (
        f'Запит користувача: "{user_query}"\n\n'
        f'Кандидати:\n{candidates_text}'
    )

    try:
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": task},
            ],
            **build_completion_params(max_tokens=400, temperature=0.2),
        )
        raw = (response.choices[0].message.content or "").strip()

        # Strip markdown fences if model wraps output
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)

        top_ids = [int(i) for i in (data.get("top_ids") or []) if str(i).isdigit() or isinstance(i, int)]
        raw_reasons = data.get("reasons") or []
        intro = (data.get("intro") or "Ось що знайшов 👇").strip()

        # Map id → reason (align by position)
        reasons_map: dict[int, str] = {}
        for idx, tid in enumerate(top_ids):
            if idx < len(raw_reasons):
                reasons_map[tid] = raw_reasons[idx] or ""

        return RerankResult(top_ids=top_ids[:top_n], reasons=reasons_map, intro=intro)

    except Exception as e:
        logger.warning("rerank_and_explain failed for query %r: %s", user_query, e)
        # Graceful fallback: return first top_n as-is, no reasons
        fallback_ids = [c.id for c in candidates[:top_n]]
        return RerankResult(
            top_ids=fallback_ids,
            reasons={},
            intro="Ось що знайшов 👇",
        )
