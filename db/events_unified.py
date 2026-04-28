"""
Unified events table — single source of truth for all events (afisha).

Sources:
  'manual'      — created via admin CRM
  'egolist'     — synced from api.egolist.ua/api/events
  'kontramarka' — future: Kontramarka partner API
  'karabas'     — future: Karabas partner API

On startup, existing bot_events rows are migrated here (source='manual').
"""
from __future__ import annotations
import logging
from db.connection import get_pool

logger = logging.getLogger(__name__)

EVENT_CATEGORIES = [
    "концерти", "театр", "стендап", "для дітей", "фестивалі",
    "виставки", "кіно", "активний відпочинок", "майстер-класи",
    "спорт", "клуби", "інше",
]

# Maps unified category → egolist event_slug (for compat with old search)
_CATEGORY_TO_SLUG = {
    "концерти": "koncerti",
    "виставки": "vistavi",
    "кіно": "kino",
    "для дітей": "dlia-ditei",
    "активний відпочинок": "aktivnii-vidpocinok",
    "майстер-класи": "maister-klasi",
}


async def init_events_table() -> None:
    """Create unified events table and migrate existing bot_events data."""
    pool = await get_pool()

    await pool.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id             SERIAL PRIMARY KEY,
            source         VARCHAR(50) NOT NULL DEFAULT 'manual',
            external_id    VARCHAR(255),
            title          TEXT NOT NULL,
            description    TEXT,
            category       TEXT,
            event_slug     VARCHAR(50),
            date           DATE,
            time           TIME,
            price          TEXT,
            venue_name     TEXT,
            venue_address  TEXT,
            city           TEXT NOT NULL DEFAULT 'Дніпро',
            image_url      TEXT,
            cloudinary_url TEXT,
            source_url     TEXT,
            ticket_url     TEXT,
            affiliate_url  TEXT,
            is_published   BOOLEAN NOT NULL DEFAULT TRUE,
            is_featured    BOOLEAN NOT NULL DEFAULT FALSE,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            priority       INT NOT NULL DEFAULT 0,
            tags           TEXT,
            internal_notes TEXT,
            synced_at      TIMESTAMPTZ,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source_ext ON events(source, external_id) "
        "WHERE external_id IS NOT NULL"
    )
    await pool.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_date ON events(date) WHERE is_published = TRUE"
    )
    await pool.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)"
    )

    # Migrate bot_events → events (one-time, safe to re-run)
    try:
        bot_events_exist = await pool.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name='bot_events'"
        )
        if bot_events_exist:
            migrated = await pool.execute("""
                INSERT INTO events
                    (source, title, description, category, date, time, price,
                     venue_name, venue_address, city, image_url, source_url,
                     ticket_url, is_published, is_featured, priority,
                     tags, created_at, updated_at)
                SELECT
                    'manual', title, description, category, date, time, price,
                    place_name, place_address, city, photo_url, NULL,
                    ticket_url, is_published, is_featured, priority,
                    tags, created_at, updated_at
                FROM bot_events
                WHERE id NOT IN (
                    SELECT COALESCE(external_id::int, -1)
                    FROM events WHERE source = 'manual' AND external_id IS NOT NULL
                )
                ON CONFLICT DO NOTHING
            """)
            if migrated != "INSERT 0 0":
                logger.info("Migrated bot_events → events: %s", migrated)
    except Exception as e:
        logger.warning("bot_events migration skipped: %s", e)


# ── CRUD ─────────────────────────────────────────────────────────────────────

async def get_all_events(published_only: bool = False, source: str | None = None) -> list[dict]:
    pool = await get_pool()
    where_parts = []
    params = []
    if published_only:
        where_parts.append("is_published = TRUE")
    if source:
        params.append(source)
        where_parts.append(f"source = ${len(params)}")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = await pool.fetch(f"""
        SELECT * FROM events {where}
        ORDER BY priority DESC, is_featured DESC, date ASC NULLS LAST, updated_at DESC
    """)
    return [dict(r) for r in rows]


async def get_event(event_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    return dict(row) if row else None


async def create_event(data: dict) -> dict:
    pool = await get_pool()
    import datetime
    row = await pool.fetchrow("""
        INSERT INTO events
            (source, title, description, category, event_slug, date, time, price,
             venue_name, venue_address, city, image_url, source_url, ticket_url,
             is_published, is_featured, priority, tags, internal_notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
        RETURNING *
    """,
        data.get("source", "manual"),
        data.get("title"), data.get("description"),
        data.get("category"),
        _category_to_slug(data.get("category")),
        _date(data.get("date")), _time(data.get("time")),
        data.get("price"),
        data.get("venue_name"), data.get("venue_address"),
        data.get("city", "Дніпро"),
        data.get("image_url") or data.get("photo_url"),
        data.get("source_url"),
        data.get("ticket_url"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
        data.get("tags"), data.get("internal_notes"),
    )
    return dict(row)


async def update_event(event_id: int, data: dict) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("""
        UPDATE events SET
            title=$1, description=$2, category=$3, event_slug=$4,
            date=$5, time=$6, price=$7,
            venue_name=$8, venue_address=$9, city=$10,
            image_url=$11, source_url=$12, ticket_url=$13,
            is_published=$14, is_featured=$15, priority=$16,
            tags=$17, internal_notes=$18, updated_at=NOW()
        WHERE id=$19
        RETURNING *
    """,
        data.get("title"), data.get("description"),
        data.get("category"),
        _category_to_slug(data.get("category")),
        _date(data.get("date")), _time(data.get("time")),
        data.get("price"),
        data.get("venue_name"), data.get("venue_address"),
        data.get("city", "Дніпро"),
        data.get("image_url") or data.get("photo_url"),
        data.get("source_url"), data.get("ticket_url"),
        data.get("is_published", True), data.get("is_featured", False),
        _int(data.get("priority", 0)) or 0,
        data.get("tags"), data.get("internal_notes"),
        event_id,
    )
    return dict(row)


async def delete_event(event_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM events WHERE id = $1", event_id)


async def toggle_event_published(event_id: int) -> bool:
    pool = await get_pool()
    new_val = await pool.fetchval("""
        UPDATE events SET is_published = NOT is_published, updated_at = NOW()
        WHERE id = $1 RETURNING is_published
    """, event_id)
    return bool(new_val)


async def toggle_event_featured(event_id: int) -> bool:
    pool = await get_pool()
    new_val = await pool.fetchval("""
        UPDATE events SET is_featured = NOT is_featured, updated_at = NOW()
        WHERE id = $1 RETURNING is_featured
    """, event_id)
    return bool(new_val)


async def search_manual_events(
    search_text: str | None = None,
    category: str | None = None,
    date_filter: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[dict]:
    """Search published manual events (source='manual') for bot use."""
    pool = await get_pool()
    where = ["is_published = TRUE", "source = 'manual'"]
    params: list = []

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
        where.append("(date IS NULL OR date >= CURRENT_DATE)")

    if search_text:
        where.append(f"(title ILIKE ${len(params)+1} OR COALESCE(description,'') ILIKE ${len(params)+1})")
        params.append(f"%{search_text}%")

    if category:
        where.append(f"category ILIKE ${len(params)+1}")
        params.append(f"%{category}%")

    params += [limit, offset]
    where_sql = " AND ".join(where)

    try:
        rows = await pool.fetch(f"""
            SELECT * FROM events WHERE {where_sql}
            ORDER BY is_featured DESC, priority DESC, date ASC NULLS LAST
            LIMIT ${len(params)-1} OFFSET ${len(params)}
        """, *params)
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Upsert for partner sync (future use) ─────────────────────────────────────

async def upsert_event(source: str, external_id: str, data: dict) -> None:
    """Insert or update an event from a partner source."""
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO events
            (source, external_id, title, description, category, event_slug,
             date, time, price, venue_name, city,
             image_url, source_url, ticket_url, affiliate_url,
             is_published, synced_at, updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,TRUE,NOW(),NOW())
        ON CONFLICT (source, external_id) DO UPDATE SET
            title=EXCLUDED.title, description=EXCLUDED.description,
            category=EXCLUDED.category, event_slug=EXCLUDED.event_slug,
            date=EXCLUDED.date, time=EXCLUDED.time, price=EXCLUDED.price,
            venue_name=EXCLUDED.venue_name, image_url=EXCLUDED.image_url,
            source_url=EXCLUDED.source_url, ticket_url=EXCLUDED.ticket_url,
            synced_at=NOW(), updated_at=NOW()
    """,
        source, external_id,
        data.get("title"), data.get("description"),
        data.get("category"), _category_to_slug(data.get("category")),
        _date(data.get("date")), _time(data.get("time")),
        data.get("price"), data.get("venue_name"),
        data.get("city", "Дніпро"),
        data.get("image_url"), data.get("source_url"), data.get("ticket_url"),
        data.get("affiliate_url"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _category_to_slug(category: str | None) -> str | None:
    if not category:
        return None
    return _CATEGORY_TO_SLUG.get(category.lower().strip())


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
