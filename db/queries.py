import logging
from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool
from config import settings
from db.content import search_bot_places, search_bot_events_active

logger = logging.getLogger(__name__)


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
    cloudinary_url: Optional[str] = None


def _media_url(uuid_str: str, name: str) -> str:
    """Build Spatie MediaLibrary URL: /storage/other/{uuid[0:2]}/{uuid[2:4]}/conversions/{name}-feed.webp"""
    clean = uuid_str.replace("-", "")
    return f"{settings.MEDIA_BASE_URL}/storage/other/{clean[0:2]}/{clean[2:4]}/conversions/{name}-feed.webp"


# ── pg_trgm fuzzy search ───────────────────────────────────────────────────────

_trgm_enabled: bool | None = None


async def _ensure_trgm() -> bool:
    """Enable pg_trgm extension once per process. Returns True if available."""
    global _trgm_enabled
    if _trgm_enabled is not None:
        return _trgm_enabled
    try:
        pool = await get_pool()
        await pool.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        _trgm_enabled = True
    except Exception:
        _trgm_enabled = False
    return _trgm_enabled


# ── Products ──────────────────────────────────────────────────────────────────

async def search_products(
    category_names: list[str] | None = None,
    category_ids: list[int] | None = None,  # deprecated, ignored
    city_id: int | None = None,              # deprecated, ignored
    max_price: int | None = None,
    search_text: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[ProductResult]:
    """Search performers/venues from local egolist_products table (synced from API).
    Falls back to empty list if table not yet populated.
    """
    pool = await get_pool()

    # Check table exists and has data
    try:
        exists = await pool.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name='egolist_products'"
        )
        if not exists:
            return []
    except Exception:
        return []

    # Safety net: if no category AND no search_text → don't return everything.
    # This prevents the "random photographers" fallback when AI can't classify
    # the query (e.g. off-topic requests like "кальян" or "доставка").
    if not category_names and not search_text:
        return []

    params: list = []
    where = ["is_active = TRUE"]

    # Filter by category names
    if category_names:
        base = len(params)
        cat_conds = " OR ".join(
            f"category_name ILIKE ${base + i + 1}" for i in range(len(category_names))
        )
        params.extend(f"%{n}%" for n in category_names)
        where.append(f"({cat_conds})")

    if max_price:
        params.append(max_price)
        where.append(f"(price IS NULL OR price <= ${len(params)})")

    order_by = "is_top DESC, scraped_at DESC"

    if search_text:
        trgm = await _ensure_trgm()
        words = [w for w in search_text.split() if len(w) >= 3] or [search_text]
        base = len(params)
        word_conds = " OR ".join(
            f"(name ILIKE ${base + i + 1} OR COALESCE(description,'') ILIKE ${base + i + 1})"
            for i in range(len(words))
        )
        params.extend(f"%{w}%" for w in words)

        if trgm:
            trgm_idx = len(params) + 1
            where.append(f"({word_conds} OR similarity(name, ${trgm_idx}) > 0.2)")
            params.append(search_text)
            order_by = f"similarity(name, ${trgm_idx}) DESC, is_top DESC"
        else:
            where.append(f"({word_conds})")

    where_sql = " AND ".join(where)
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params += [limit, offset]

    try:
        rows = await pool.fetch(f"""
            SELECT api_id, name, description, category_name, city,
                   price, phone, instagram, telegram, website,
                   photo_url, product_url, is_top
            FROM egolist_products
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """, *params)
    except Exception:
        rows = []

    results: list[ProductResult] = [
        ProductResult(
            id=abs(hash(r["api_id"])) % 2_000_000_000,
            name=r["name"],
            description=(r["description"] or "")[:300],
            category=r["category_name"] or "",
            city=r["city"] or "Дніпро",
            price=r["price"],
            phone=r["phone"],
            instagram=r["instagram"],
            website=r["website"],
            telegram_contact=r["telegram"],
            photo_url=r["photo_url"],
            is_top=bool(r["is_top"]),
            product_url=r["product_url"],
        )
        for r in rows
    ]

    # ── Bot-managed places (featured shown first) ─────────────────────────
    try:
        bot_rows = await search_bot_places(
            search_text=search_text,
            max_price=max_price,
            limit=limit,
            offset=offset,
        )
        for r in bot_rows:
            p = ProductResult(
                id=-(r["id"]),
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
            )
            if r.get("is_featured"):
                results.insert(0, p)
            else:
                results.append(p)
    except Exception:
        pass

    return results[:limit]


# ── Egolist events (replaces karabas_events + kino_events) ───────────────────

# Maps old event_category values (from AI) → egolist event_slug
_CATEGORY_TO_SLUG: dict[str, str | None] = {
    "концерти":            "koncerti",
    "театр":               None,
    "діти":                "dlia-ditei",
    "для дітей":           "dlia-ditei",
    "стендап":             None,
    "фестивалі":           "koncerti",
    "клуби":               "aktivnii-vidpocinok",
    "виставки":            "vistavi",
    "спорт":               "aktivnii-vidpocinok",
    "цирк":                None,
    "активний відпочинок": "aktivnii-vidpocinok",
    "майстер-класи":       "maister-klasi",
    "кіно":                "kino",
}


async def _search_egolist_events(
    event_slug: str | None = None,
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
    fallback_search: str | None = None,   # extra text search when slug=None
) -> list[EventResult]:
    """Core query against egolist_events table."""
    pool = await get_pool()

    exists = await pool.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name='egolist_events'"
    )
    if not exists:
        return []

    params: list = []
    where = ["is_active = TRUE", "date >= CURRENT_DATE"]

    if date_filter == "today":
        where[-1] = "date = CURRENT_DATE"
    elif date_filter == "weekend":
        where[-1] = (
            "date >= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '5 days' "
            "AND date <= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'"
        )
    elif date_filter == "week":
        where[-1] = "date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '7 days'"
    elif date_filter == "month":
        where[-1] = "date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '30 days'"

    if event_slug:
        params.append(event_slug)
        where.append(f"event_slug = ${len(params)}")

    order_by = "date ASC NULLS LAST"

    # Combine search_text + fallback_search
    combined_text = search_text or fallback_search
    if combined_text:
        trgm = await _ensure_trgm()
        words = [w for w in combined_text.split() if len(w) >= 3] or [combined_text]
        base = len(params)
        word_conds = " OR ".join(
            f"(title ILIKE ${base+i+1} OR COALESCE(description,'') ILIKE ${base+i+1})"
            for i in range(len(words))
        )
        params.extend(f"%{w}%" for w in words)

        if trgm:
            trgm_idx = len(params) + 1
            where.append(f"({word_conds} OR similarity(title, ${trgm_idx}) > 0.25)")
            params.append(combined_text)
            order_by = f"similarity(title, ${trgm_idx}) DESC, date ASC NULLS LAST"
        else:
            where.append(f"({word_conds})")

    where_sql = " AND ".join(where)
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params += [limit, offset]

    try:
        rows = await pool.fetch(f"""
            SELECT id, title, description, date::text, time::text,
                   price, place_name, image_url, cloudinary_url, source_url, event_type
            FROM egolist_events
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """, *params)
    except Exception as e:
        logger.warning("egolist_events query error: %s", e)
        return []

    return [
        EventResult(
            id=r["id"],
            title=r["title"],
            description=(r["description"] or "")[:300],
            date=r["date"] or "",
            time=r["time"] or None,
            price=r["price"],
            place_name=r["place_name"],
            place_address="Дніпро",
            city="Дніпро",
            photo_url=r["cloudinary_url"] or r["image_url"],
            source_url=r["source_url"],
            cloudinary_url=r["cloudinary_url"],
        )
        for r in rows
    ]


async def search_karabas_events(
    category: str | None = None,
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search events from egolist_events (replaces Karabas scraper).
    category maps to event_slug; None = all non-kino events.
    """
    event_slug = _CATEGORY_TO_SLUG.get(category or "", None) if category else None
    fallback = category if (category and not event_slug) else None

    results = await _search_egolist_events(
        event_slug=event_slug,
        limit=limit,
        offset=offset,
        date_filter=date_filter,
        search_text=search_text,
        fallback_search=fallback,
    )

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


async def search_kino_events(
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search cinema events from egolist_events (replaces kino-teatr.ua scraper)."""
    return await _search_egolist_events(
        event_slug="kino",
        limit=limit,
        offset=offset,
        date_filter=date_filter,
        search_text=search_text,
    )


# ── Fallback events ───────────────────────────────────────────────────────────

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
