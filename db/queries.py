from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool
from config import settings
from db.content import search_bot_places, search_bot_events_active


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
    product_url: Optional[str] = None


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
    source_url: Optional[str] = None


def _media_url(uuid_str: str, name: str) -> str:
    """Build Spatie MediaLibrary URL: /storage/other/{uuid[0:2]}/{uuid[2:4]}/conversions/{name}-feed.webp"""
    clean = uuid_str.replace("-", "")
    return f"{settings.MEDIA_BASE_URL}/storage/other/{clean[0:2]}/{clean[2:4]}/conversions/{name}-feed.webp"


async def search_products(
    category_ids: list[int] | None = None,
    city_id: int | None = None,
    max_price: int | None = None,
    search_text: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[ProductResult]:
    pool = await get_pool()
    city_id = city_id or settings.DEFAULT_CITY_ID

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

    # Точний пошук по category_id замість LIKE
    if category_ids:
        where_parts.append(f"p.category_id = ANY(${idx})")
        params.append(category_ids)
        idx += 1

    if search_text:
        where_parts.append(f"(p.name ILIKE ${idx} OR p.description ILIKE ${idx})")
        params.append(f"%{search_text}%")
        idx += 1

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT
            p.id, p.name,
            COALESCE(p.description, '') as description,
            COALESCE(c.title, '') as category,
            COALESCE(g.name_ua, '') as city,
            p.price, p.phone, p.instagram, p.website, p.telegram,
            p.is_top, p.is_recommended, p.slug_seo,
            m.uuid, m.name as media_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        LEFT JOIN geo_cities g ON g.id = p.city_id
        LEFT JOIN LATERAL (
            SELECT uuid::text, name FROM media
            WHERE model_id = p.id AND model_type = 'product'
            ORDER BY id LIMIT 1
        ) m ON true
        WHERE {where_sql}
        ORDER BY p.is_top DESC, p.is_recommended DESC, p.id DESC
        LIMIT ${idx} OFFSET ${idx+1}
    """
    params.extend([limit, offset])

    rows = await pool.fetch(query, *params)

    results = []
    for r in rows:
        photo = _media_url(r["uuid"], r["media_name"]) if r["uuid"] else None
        slug = r["slug_seo"]
        product_url = f"{settings.MEDIA_BASE_URL.replace('api.', '')}/products/{slug}" if slug else None
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
            product_url=product_url,
        ))

    # Also search bot-managed places (priority items shown first)
    try:
        bot_rows = await search_bot_places(
            search_text=search_text,
            max_price=max_price,
            limit=limit,
            offset=offset,
        )
        for r in bot_rows:
            results.insert(0 if r.get("is_featured") else len(results), ProductResult(
                id=-(r["id"]),  # negative id to avoid collision
                name=r["name"],
                description=(r.get("description") or "")[:300],
                category=r.get("category") or "",
                city=r.get("city") or "Дніпро",
                price=r.get("price_from"),
                phone=r.get("phone"),
                instagram=r.get("instagram"),
                website=r.get("website") or r.get("booking_url"),
                telegram_contact=r.get("telegram"),
                photo_url=r.get("photo_url"),
                is_top=bool(r.get("is_featured")),
                product_url=r.get("booking_url"),
            ))
    except Exception:
        pass

    return results[:limit]


async def search_karabas_events(
    category: str | None = None,
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search events scraped from Karabas.com. Falls back to empty list if table missing.

    date_filter: "today" | "weekend" | "week" | "month" | None (all future)
    """
    pool = await get_pool()

    # Check table exists
    exists = await pool.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name='karabas_events'"
    )
    if not exists:
        return []

    params: list = []
    where = ["is_active = TRUE"]

    if date_filter == "today":
        where.append("date = CURRENT_DATE")
    elif date_filter == "weekend":
        # Nearest Saturday and Sunday
        where.append(
            "date >= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '5 days' "
            "AND date <= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'"
        )
    elif date_filter == "week":
        where.append("date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '7 days'")
    elif date_filter == "month":
        where.append("date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '30 days'")
    else:
        where.append("date >= CURRENT_DATE")

    if category:
        where.append(f"category = ${len(params)+1}")
        params.append(category)

    if search_text:
        where.append(f"title ILIKE ${len(params)+1}")
        params.append(f"%{search_text}%")

    where_sql = " AND ".join(where)
    params += [limit, offset]

    rows = await pool.fetch(f"""
        SELECT id, title, date::text, time::text, price, place_name, image_url, source_url
        FROM karabas_events
        WHERE {where_sql}
        ORDER BY date ASC NULLS LAST
        LIMIT ${len(params)-1} OFFSET ${len(params)}
    """, *params)

    results = [
        EventResult(
            id=r["id"],
            title=r["title"],
            description="",
            date=r["date"] or "",
            time=r["time"] or None,
            price=r["price"],
            place_name=r["place_name"],
            place_address="Дніпро",
            city="Дніпро",
            photo_url=r["image_url"],
            source_url=r["source_url"],
        )
        for r in rows
    ]

    # Prepend bot-managed featured events
    try:
        bot_evs = await search_bot_events_active(
            search_text=search_text,
            category=category,
            date_filter=date_filter,
            limit=limit,
            offset=offset,
        )
        for e in bot_evs:
            date_str = str(e["date"]) if e.get("date") else ""
            time_str = str(e["time"]) if e.get("time") else None
            ev = EventResult(
                id=-(e["id"]),
                title=e["title"],
                description=(e.get("description") or "")[:300],
                date=date_str,
                time=time_str,
                price=e.get("price"),
                place_name=e.get("place_name"),
                place_address=e.get("place_address") or "Дніпро",
                city=e.get("city") or "Дніпро",
                photo_url=e.get("photo_url"),
                source_url=e.get("ticket_url"),
            )
            if e.get("is_featured"):
                results.insert(0, ev)
            else:
                results.append(ev)
    except Exception:
        pass

    return results[:limit]


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
