"""
Bot-managed content: bot_places and bot_events.
These are created and edited directly through the admin panel,
independent of the main Egolist platform DB.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool


# ── Init ─────────────────────────────────────────────────────────────────────

async def init_content_tables() -> None:
    pool = await get_pool()

    await pool.execute("""
        CREATE TABLE IF NOT EXISTS bot_places (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            category     TEXT,
            description  TEXT,
            district     TEXT,
            address      TEXT,
            price_from   INT,
            price_to     INT,
            for_who      TEXT,
            tags         TEXT,               -- comma-separated
            phone        TEXT,
            instagram    TEXT,
            website      TEXT,
            telegram     TEXT,
            booking_url  TEXT,
            photo_url    TEXT,
            city         TEXT NOT NULL DEFAULT 'Дніпро',
            is_published BOOLEAN NOT NULL DEFAULT TRUE,
            is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
            priority     INT NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pool.execute("""
        CREATE TABLE IF NOT EXISTS bot_events (
            id           SERIAL PRIMARY KEY,
            title        TEXT NOT NULL,
            description  TEXT,
            category     TEXT,
            date         DATE,
            time         TIME,
            price        TEXT,
            place_name   TEXT,
            place_address TEXT,
            tags         TEXT,
            photo_url    TEXT,
            ticket_url   TEXT,
            city         TEXT NOT NULL DEFAULT 'Дніпро',
            is_published BOOLEAN NOT NULL DEFAULT TRUE,
            is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
            priority     INT NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


# ── Places CRUD ───────────────────────────────────────────────────────────────

async def get_all_places(published_only: bool = False) -> list[dict]:
    pool = await get_pool()
    where = "WHERE is_published = TRUE" if published_only else ""
    rows = await pool.fetch(f"""
        SELECT * FROM bot_places {where}
        ORDER BY priority DESC, is_featured DESC, updated_at DESC
    """)
    return [dict(r) for r in rows]


async def get_place(place_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM bot_places WHERE id = $1", place_id)
    return dict(row) if row else None


async def create_place(data: dict) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO bot_places
            (name, category, description, district, address, price_from, price_to,
             for_who, tags, phone, instagram, website, telegram, booking_url, photo_url,
             city, is_published, is_featured, priority)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
        RETURNING id
    """,
        data.get("name"), data.get("category"), data.get("description"),
        data.get("district"), data.get("address"),
        _int(data.get("price_from")), _int(data.get("price_to")),
        data.get("for_who"), data.get("tags"),
        data.get("phone"), data.get("instagram"), data.get("website"),
        data.get("telegram"), data.get("booking_url"), data.get("photo_url"),
        data.get("city", "Дніпро"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
    )


async def update_place(place_id: int, data: dict) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE bot_places SET
            name=$1, category=$2, description=$3, district=$4, address=$5,
            price_from=$6, price_to=$7, for_who=$8, tags=$9,
            phone=$10, instagram=$11, website=$12, telegram=$13,
            booking_url=$14, photo_url=$15, city=$16,
            is_published=$17, is_featured=$18, priority=$19,
            updated_at=NOW()
        WHERE id=$20
    """,
        data.get("name"), data.get("category"), data.get("description"),
        data.get("district"), data.get("address"),
        _int(data.get("price_from")), _int(data.get("price_to")),
        data.get("for_who"), data.get("tags"),
        data.get("phone"), data.get("instagram"), data.get("website"),
        data.get("telegram"), data.get("booking_url"), data.get("photo_url"),
        data.get("city", "Дніпро"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
        place_id,
    )


async def delete_place(place_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM bot_places WHERE id = $1", place_id)


async def toggle_place_published(place_id: int) -> bool:
    """Flips is_published and returns new state."""
    pool = await get_pool()
    new_val = await pool.fetchval("""
        UPDATE bot_places SET is_published = NOT is_published, updated_at = NOW()
        WHERE id = $1 RETURNING is_published
    """, place_id)
    return bool(new_val)


# ── Events CRUD ───────────────────────────────────────────────────────────────

async def get_all_bot_events(published_only: bool = False) -> list[dict]:
    pool = await get_pool()
    where = "WHERE is_published = TRUE" if published_only else ""
    rows = await pool.fetch(f"""
        SELECT * FROM bot_events {where}
        ORDER BY priority DESC, date ASC NULLS LAST, updated_at DESC
    """)
    return [dict(r) for r in rows]


async def get_bot_event(event_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM bot_events WHERE id = $1", event_id)
    return dict(row) if row else None


async def create_bot_event(data: dict) -> int:
    pool = await get_pool()
    import datetime
    return await pool.fetchval("""
        INSERT INTO bot_events
            (title, description, category, date, time, price,
             place_name, place_address, tags, photo_url, ticket_url,
             city, is_published, is_featured, priority)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        RETURNING id
    """,
        data.get("title"), data.get("description"), data.get("category"),
        _date(data.get("date")), _time(data.get("time")),
        data.get("price"), data.get("place_name"), data.get("place_address"),
        data.get("tags"), data.get("photo_url"), data.get("ticket_url"),
        data.get("city", "Дніпро"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
    )


async def update_bot_event(event_id: int, data: dict) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE bot_events SET
            title=$1, description=$2, category=$3, date=$4, time=$5, price=$6,
            place_name=$7, place_address=$8, tags=$9, photo_url=$10, ticket_url=$11,
            city=$12, is_published=$13, is_featured=$14, priority=$15, updated_at=NOW()
        WHERE id=$16
    """,
        data.get("title"), data.get("description"), data.get("category"),
        _date(data.get("date")), _time(data.get("time")),
        data.get("price"), data.get("place_name"), data.get("place_address"),
        data.get("tags"), data.get("photo_url"), data.get("ticket_url"),
        data.get("city", "Дніпро"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
        event_id,
    )


async def delete_bot_event(event_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM bot_events WHERE id = $1", event_id)


async def toggle_bot_event_published(event_id: int) -> bool:
    pool = await get_pool()
    new_val = await pool.fetchval("""
        UPDATE bot_events SET is_published = NOT is_published, updated_at = NOW()
        WHERE id = $1 RETURNING is_published
    """, event_id)
    return bool(new_val)


# ── Search for bot (used by queries.py) ───────────────────────────────────────

async def search_bot_places(
    search_text: str | None = None,
    category: str | None = None,
    max_price: int | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    pool = await get_pool()
    where = ["is_published = TRUE"]
    params: list = []

    if search_text:
        where.append(f"(name ILIKE ${len(params)+1} OR description ILIKE ${len(params)+1} OR tags ILIKE ${len(params)+1})")
        params.append(f"%{search_text}%")

    if category:
        where.append(f"category ILIKE ${len(params)+1}")
        params.append(f"%{category}%")

    if max_price:
        where.append(f"(price_from IS NULL OR price_from <= ${len(params)+1})")
        params.append(max_price)

    params += [limit, offset]
    where_sql = " AND ".join(where)

    rows = await pool.fetch(f"""
        SELECT * FROM bot_places WHERE {where_sql}
        ORDER BY priority DESC, is_featured DESC, id DESC
        LIMIT ${len(params)-1} OFFSET ${len(params)}
    """, *params)
    return [dict(r) for r in rows]


async def search_bot_events_active(
    search_text: str | None = None,
    category: str | None = None,
    date_filter: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    pool = await get_pool()
    where = ["is_published = TRUE"]
    params: list = []

    if date_filter == "today":
        where.append("date = CURRENT_DATE")
    elif date_filter == "weekend":
        where.append("date >= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '5 days' AND date <= DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'")
    elif date_filter == "week":
        where.append("date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '7 days'")
    elif date_filter == "month":
        where.append("date >= CURRENT_DATE AND date <= CURRENT_DATE + INTERVAL '30 days'")
    else:
        where.append("(date IS NULL OR date >= CURRENT_DATE)")

    if search_text:
        where.append(f"(title ILIKE ${len(params)+1} OR description ILIKE ${len(params)+1})")
        params.append(f"%{search_text}%")

    if category:
        where.append(f"category ILIKE ${len(params)+1}")
        params.append(f"%{category}%")

    params += [limit, offset]
    where_sql = " AND ".join(where)

    rows = await pool.fetch(f"""
        SELECT * FROM bot_events WHERE {where_sql}
        ORDER BY priority DESC, date ASC NULLS LAST
        LIMIT ${len(params)-1} OFFSET ${len(params)}
    """, *params)
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _int(v) -> int | None:
    try:
        return int(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def _date(v):
    if not v:
        return None
    import datetime
    try:
        return datetime.date.fromisoformat(str(v))
    except Exception:
        return None


def _time(v):
    if not v:
        return None
    import datetime
    try:
        return datetime.time.fromisoformat(str(v))
    except Exception:
        return None
