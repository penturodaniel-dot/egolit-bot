"""
Завантажує категорії з БД один раз і кешує в пам'яті.
AI використовує цей список щоб повертати точні category_id.
"""
from db.connection import get_pool

# Кеш — заповнюється при першому виклику
_categories: list[dict] = []
_prompt_text: str = ""


async def load_categories():
    """Завантажує всі категорії з продуктами. Викликати при старті."""
    global _categories, _prompt_text

    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT c.id, c.title, c.parent_id, c.active_products_counter,
               p.title as parent_title
        FROM categories c
        LEFT JOIN categories p ON p.id = c.parent_id
        WHERE c.deleted_at IS NULL
          AND c.is_hidden = false
          AND c.active_products_counter > 0
        ORDER BY c.active_products_counter DESC
    """)

    _categories = [dict(r) for r in rows]

    # Формуємо текст для AI промпту
    lines = []
    for c in _categories:
        parent = f" [{c['parent_title']}]" if c['parent_title'] else ""
        lines.append(f"  id={c['id']}: {c['title']}{parent} ({c['active_products_counter']} послуг)")

    _prompt_text = "\n".join(lines)


def get_categories_prompt() -> str:
    """Повертає список категорій для вставки в AI промпт."""
    return _prompt_text


def get_all_category_ids() -> list[int]:
    return [c['id'] for c in _categories]


def expand_category_ids(ids: list[int]) -> list[int]:
    """
    Розширює список ID — якщо передали батьківську категорію,
    додає всі її дочірні категорії теж.
    """
    result = set(ids)
    for cat_id in ids:
        for c in _categories:
            if c['parent_id'] == cat_id:
                result.add(c['id'])
    return list(result)
