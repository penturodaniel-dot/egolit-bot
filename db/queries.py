from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool
from config import settings


@dataclass
class ProductResult:
    id: int
    name: str
    description: str
    category: str
    city: str
    price: Optional[int]
    phone: Optional[str]
    instagram: Optional[str]
    website: Optional[str]
    telegram_contact: Optional[str]
    photo_url: Optional[str]
    is_top: bool


@dataclass
class EventResult:
    id: int
    title: str
    description: str
    date: str
    time: Optional[str]
    price: Optional[str]
    place_name: Optional[str]
    place_address: Optional[str]
    city: str
    photo_url: Optional[str]


def _media_url(media_id: int, file_name: str) -> str:
    return f"{settings.MEDIA_BASE_URL}/storage/{media_id}/{file_name}"


async def search_products(
    category_keywords: list[str] | None = None,
    city_id: int | None = None,
    max_price: int | None = None,
    limit: int = 5,
) -> list[ProductResult]:
    pool = await get_pool()
    city_id = city_id or settings.DEFAULT_CITY_ID

    # Строим условия
    where_parts = [
        "p.state = 'PUBLISHED'",
        "p.deleted_at IS NULL",
        "p.city_id = $1",
    ]
    params: list = [city_id]
    idx = 2

    if max_price:
        where_parts.append(f"(p.price IS NULL OR p.price <= ${idx})")
        params.append(max_price)
        idx += 1

    if category_keywords:
        kw_conditions = []
        for kw in category_keywords:
            kw_conditions.append(f"(LOWER(c.title) LIKE ${idx} OR LOWER(p.name) LIKE ${idx} OR LOWER(p.description) LIKE ${idx})")
            params.append(f"%{kw.lower()}%")
            idx += 1
        where_parts.append(f"({' OR '.join(kw_conditions)})")

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT
            p.id, p.name,
            COALESCE(p.description, '') as description,
            COALESCE(c.title, '') as category,
            COALESCE(g.name_ua, '') as city,
            p.price, p.phone, p.instagram, p.website, p.telegram,
            p.is_top, p.is_recommended,
            m.id as media_id, m.file_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        LEFT JOIN geo_cities g ON g.id = p.city_id
        LEFT JOIN LATERAL (
            SELECT id, file_name FROM media
            WHERE model_id = p.id AND model_type LIKE '%Product%'
            ORDER BY id LIMIT 1
        ) m ON true
        WHERE {where_sql}
        ORDER BY p.is_top DESC, p.is_recommended DESC, p.id DESC
        LIMIT ${idx}
    """
    params.append(limit)

    rows = await pool.fetch(query, *params)

    results = []
    for r in rows:
        photo = _media_url(r["media_id"], r["file_name"]) if r["media_id"] else None
        results.append(ProductResult(
            id=r["id"],
            name=r["name"],
            description=r["description"][:300] if r["description"] else "",
            category=r["category"],
            city=r["city"],
            price=r["price"],
            phone=r["phone"],
            instagram=r["instagram"],
            website=r["website"],
            telegram_contact=r["telegram"],
            photo_url=photo,
            is_top=r["is_top"] or False,
        ))
    return results


async def search_events(
    city_id: int | None = None,
    limit: int = 5,
) -> list[EventResult]:
    pool = await get_pool()
    city_id = city_id or settings.DEFAULT_CITY_ID

    query = """
        SELECT
            e.id, e.title,
            COALESCE(e.description, '') as description,
            COALESCE(e.date::text, '') as date,
            COALESCE(e.time::text, '') as time,
            e.price, e.place_name, e.place_address,
            COALESCE(g.name_ua, '') as city
        FROM events e
        LEFT JOIN geo_cities g ON g.id = e.city_id
        WHERE e.deleted_at IS NULL
          AND e.city_id = $1
          AND e.date >= CURRENT_DATE
        ORDER BY e.date ASC
        LIMIT $2
    """

    rows = await pool.fetch(query, city_id, limit)

    results = []
    for r in rows:
        results.append(EventResult(
            id=r["id"],
            title=r["title"],
            description=r["description"][:300] if r["description"] else "",
            date=r["date"],
            time=r["time"] if r["time"] else None,
            price=r["price"],
            place_name=r["place_name"],
            place_address=r["place_address"],
            city=r["city"],
            photo_url=None,
        ))
    return results


async def get_categories_list() -> list[dict]:
    pool = await get_pool()
    query = """
        SELECT id, title, parent_id, active_products_counter
        FROM categories
        WHERE deleted_at IS NULL AND is_hidden = false
          AND active_products_counter > 0
        ORDER BY active_products_counter DESC
        LIMIT 30
    """
    rows = await pool.fetch(query)
    return [dict(r) for r in rows]
