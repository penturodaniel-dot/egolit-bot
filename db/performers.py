"""
CRM-managed performers table.
Replaces egolist_products (API-based) with a manually curated database.
Covers all Egolist categories: specialists, locations, equipment.
"""
from __future__ import annotations
from db.connection import get_pool

# All Egolist category names (from cats_dump.txt)
ALL_CATEGORIES = [
    # Спеціалісти
    "ведучі", "музиканти", "фото та відеозйомка", "аніматори", "артисти та шоу",
    "кейтеринг та бар", "оформлення та декор", "організатори заходів",
    "візажисти та зачіски", "кондитери", "танцювальні шоу", "актори",
    "хостес", "персонал для заходів", "поліграфія", "оренда транспорту",
    "майстер-класи", "блогери", "перекладачі",
    # Локації
    "ресторани та банкетні зали", "розважальні заклади", "готелі та комплекси",
    "квест-кімнати", "нічні клуби та караоке", "фото та відеостудії",
    "конференц-зали", "бази відпочинку", "місця для весільних церемоній",
    "івент-простори", "альтанки та бесідки", "активний відпочинок",
    "студії звукозапису", "культурні локації",
    # Обладнання
    "звукове обладнання", "світлове обладнання", "конструкції та сцени",
    "спецефекти", "декор і фотозони", "проектори та екрани",
    "меблі для заходів", "інтерактив та атракціони", "прокат одягу",
    "фото-відеообладнання", "прокат інвентарю", "кліматичне обладнання",
    "обладнання для конференцій", "живлення та кабелі",
]


async def init_performers_table() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS performers (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            category     TEXT,
            description  TEXT,
            city         TEXT NOT NULL DEFAULT 'Дніпро',
            price_from   INT,
            price_to     INT,
            phone        TEXT,
            instagram    TEXT,
            telegram     TEXT,
            website      TEXT,
            photo_url    TEXT,
            tags         TEXT,
            experience   TEXT,
            is_published BOOLEAN NOT NULL DEFAULT TRUE,
            is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
            priority     INT NOT NULL DEFAULT 0,
            source       VARCHAR(50) NOT NULL DEFAULT 'manual',
            external_id  VARCHAR(255),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute(
        "CREATE INDEX IF NOT EXISTS idx_performers_category ON performers(category)"
    )
    await pool.execute(
        "CREATE INDEX IF NOT EXISTS idx_performers_published ON performers(is_published)"
    )


async def get_all_performers(published_only: bool = False) -> list[dict]:
    pool = await get_pool()
    where = "WHERE is_published = TRUE" if published_only else ""
    rows = await pool.fetch(f"""
        SELECT * FROM performers {where}
        ORDER BY priority DESC, is_featured DESC, updated_at DESC
    """)
    return [dict(r) for r in rows]


async def get_performer(performer_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM performers WHERE id = $1", performer_id)
    return dict(row) if row else None


async def create_performer(data: dict) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("""
        INSERT INTO performers
            (name, category, description, city, price_from, price_to,
             phone, instagram, telegram, website, photo_url, tags, experience,
             is_published, is_featured, priority)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        RETURNING *
    """,
        data.get("name"), data.get("category"), data.get("description"),
        data.get("city", "Дніпро"),
        _int(data.get("price_from")), _int(data.get("price_to")),
        data.get("phone"), data.get("instagram"), data.get("telegram"),
        data.get("website"), data.get("photo_url"), data.get("tags"),
        data.get("experience"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
    )
    return dict(row)


async def update_performer(performer_id: int, data: dict) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("""
        UPDATE performers SET
            name=$1, category=$2, description=$3, city=$4,
            price_from=$5, price_to=$6, phone=$7, instagram=$8,
            telegram=$9, website=$10, photo_url=$11, tags=$12,
            experience=$13, is_published=$14, is_featured=$15, priority=$16,
            updated_at=NOW()
        WHERE id=$17
        RETURNING *
    """,
        data.get("name"), data.get("category"), data.get("description"),
        data.get("city", "Дніпро"),
        _int(data.get("price_from")), _int(data.get("price_to")),
        data.get("phone"), data.get("instagram"), data.get("telegram"),
        data.get("website"), data.get("photo_url"), data.get("tags"),
        data.get("experience"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
        performer_id,
    )
    return dict(row)


async def delete_performer(performer_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM performers WHERE id = $1", performer_id)


async def toggle_performer_published(performer_id: int) -> bool:
    pool = await get_pool()
    new_val = await pool.fetchval("""
        UPDATE performers SET is_published = NOT is_published, updated_at = NOW()
        WHERE id = $1 RETURNING is_published
    """, performer_id)
    return bool(new_val)


async def search_performers(
    category_names: list[str] | None = None,
    search_text: str | None = None,
    max_price: int | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    pool = await get_pool()
    where = ["is_published = TRUE"]
    params: list = []

    if category_names:
        base = len(params)
        cat_conds = " OR ".join(
            f"category ILIKE ${base + i + 1}" for i in range(len(category_names))
        )
        params.extend(f"%{n}%" for n in category_names)
        where.append(f"({cat_conds})")

    if max_price:
        params.append(max_price)
        where.append(f"(price_from IS NULL OR price_from <= ${len(params)})")

    if search_text:
        words = [w for w in search_text.split() if len(w) >= 3] or [search_text]
        base = len(params)
        word_conds = " OR ".join(
            f"(name ILIKE ${base+i+1} OR COALESCE(description,'') ILIKE ${base+i+1} "
            f"OR COALESCE(tags,'') ILIKE ${base+i+1})"
            for i in range(len(words))
        )
        params.extend(f"%{w}%" for w in words)
        where.append(f"({word_conds})")

    where_sql = " AND ".join(where)
    params += [limit, offset]

    try:
        rows = await pool.fetch(f"""
            SELECT * FROM performers
            WHERE {where_sql}
            ORDER BY is_featured DESC, priority DESC, updated_at DESC
            LIMIT ${len(params)-1} OFFSET ${len(params)}
        """, *params)
        return [dict(r) for r in rows]
    except Exception:
        return []


def _int(v) -> int | None:
    try:
        return int(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None
