from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool
from config import settings
from db.content import search_bot_places, search_bot_events_active
from db.egolist_api import search_products_api


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
    city_id: int | None = None,              # deprecated, ignored (always Dnipro via API)
    max_price: int | None = None,
    search_text: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[ProductResult]:
    """Search products via Egolist public API (api.egolist.ua).
    category_ids and city_id are kept for backward compat but ignored.
    """
    # ── Egolist public API ────────────────────────────────────────────────
    results = await search_products_api(
        category_names=category_names or [],
        max_price=max_price,
        search_text=search_text,
        limit=limit,
        offset=offset,
    )

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


# ── Karabas events ────────────────────────────────────────────────────────────

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

    trgm_idx: int | None = None
    order_by = "date ASC NULLS LAST"

    if search_text:
        trgm = await _ensure_trgm()
        words = [w for w in search_text.split() if len(w) >= 3] or [search_text]
        base = len(params)
        word_conds = " OR ".join(
            f"title ILIKE ${base+i+1}" for i in range(len(words))
        )
        params.extend(f"%{w}%" for w in words)

        if trgm:
            trgm_idx = len(params) + 1
            where.append(f"({word_conds} OR similarity(title, ${trgm_idx}) > 0.25)")
            params.append(search_text)
            order_by = f"similarity(title, ${trgm_idx}) DESC, date ASC NULLS LAST"
        else:
            where.append(f"({word_conds})")

    where_sql = " AND ".join(where)
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params += [limit, offset]

    rows = await pool.fetch(f"""
        SELECT id, title, date::text, time::text, price, place_name, image_url, source_url
        FROM karabas_events
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ${limit_idx} OFFSET ${offset_idx}
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


# ── Cinema (kino-teatr.ua) events ────────────────────────────────────────────

async def search_kino_events(
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search cinema films scraped from kino-teatr.ua. Returns [] if table missing."""
    pool = await get_pool()

    exists = await pool.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name='kino_events'"
    )
    if not exists:
        return []

    params: list = []
    where = ["is_active = TRUE"]
    today_clause = "CURRENT_DATE"

    if date_filter == "today":
        where.append(f"date_from <= {today_clause} AND (date_to >= {today_clause} OR date_to IS NULL)")
    elif date_filter == "weekend":
        where.append(
            f"date_from <= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days' "
            f"AND (date_to >= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '5 days' OR date_to IS NULL)"
        )
    elif date_filter == "week":
        where.append(f"date_from <= CURRENT_DATE + INTERVAL '7 days' AND (date_to >= CURRENT_DATE OR date_to IS NULL)")
    elif date_filter == "month":
        where.append(f"date_from <= CURRENT_DATE + INTERVAL '30 days' AND (date_to >= CURRENT_DATE OR date_to IS NULL)")
    else:
        where.append(f"(date_to >= CURRENT_DATE OR date_to IS NULL OR date_from >= CURRENT_DATE)")

    trgm_idx: int | None = None
    order_by = "date_from ASC NULLS LAST"

    if search_text:
        trgm = await _ensure_trgm()
        words = [w for w in search_text.split() if len(w) >= 3] or [search_text]
        base = len(params)
        word_conds = " OR ".join(
            f"(title ILIKE ${base+i+1} OR COALESCE(genre,'') ILIKE ${base+i+1})"
            for i in range(len(words))
        )
        params.extend(f"%{w}%" for w in words)

        if trgm:
            trgm_idx = len(params) + 1
            where.append(f"({word_conds} OR similarity(title, ${trgm_idx}) > 0.25)")
            params.append(search_text)
            order_by = f"similarity(title, ${trgm_idx}) DESC, date_from ASC NULLS LAST"
        else:
            where.append(f"({word_conds})")

    where_sql = " AND ".join(where)
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    params += [limit, offset]

    rows = await pool.fetch(f"""
        SELECT id, title, description, genre,
               date_from::text, date_to::text,
               price, cinema_name, image_url, source_url
        FROM kino_events
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """, *params)

    results = []
    for r in rows:
        # Format date range as readable string
        d_from = r["date_from"] or ""
        d_to = r["date_to"] or ""
        if d_from and d_to and d_from != d_to:
            date_str = f"{d_from} — {d_to}"
        else:
            date_str = d_from or d_to

        # Description: prepend genre if present
        desc = ""
        if r["genre"]:
            desc = f"🎬 {r['genre']}"
        if r["description"]:
            desc = (desc + "\n" + r["description"][:200]).strip() if desc else r["description"][:200]

        results.append(EventResult(
            id=r["id"],
            title=r["title"],
            description=desc,
            date=date_str,
            time=None,
            price=r["price"],
            place_name=r["cinema_name"],
            place_address="Дніпро",
            city="Дніпро",
            photo_url=r["image_url"],
            source_url=r["source_url"],
        ))
    return results


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
