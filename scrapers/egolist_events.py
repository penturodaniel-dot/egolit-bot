"""
Scraper for api.egolist.ua/api/events
Fetches all upcoming events for Dnipro (city_slug=dnipro) across 6 categories.
Stores in egolist_events table — replaces karabas_events + kino_events.

API: GET /api/events?city_slug=dnipro&per_page=50&page=N
     GET /api/event-types  → 6 types with slugs
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, date as date_type, time as time_type
from typing import Optional

import httpx

from db.connection import get_pool

logger = logging.getLogger(__name__)

BASE = "https://api.egolist.ua/api"
CITY_SLUG = "dnipro"
PER_PAGE = 50
MAX_PAGES = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Egolist event_type slug → Ukrainian name used in DB and AI matching
EVENT_TYPE_MAP: dict[str, str] = {
    "koncerti":            "концерти",
    "vistavi":             "виставки",
    "kino":                "кіно",
    "dlia-ditei":          "для дітей",
    "aktivnii-vidpocinok": "активний відпочинок",
    "maister-klasi":       "майстер-класи",
}


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_egolist_events() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS egolist_events (
            id          SERIAL PRIMARY KEY,
            api_id      TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            date        DATE,
            time        TIME,
            price       TEXT,
            place_name  TEXT,
            image_url   TEXT,
            source_url  TEXT,
            event_type  TEXT,
            event_slug  TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            scraped_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS egolist_events_date_idx
        ON egolist_events (date) WHERE is_active = TRUE
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS egolist_events_slug_idx
        ON egolist_events (event_slug) WHERE is_active = TRUE
    """)
    await pool.execute("""
        CREATE EXTENSION IF NOT EXISTS pg_trgm
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS egolist_events_title_trgm_idx
        ON egolist_events USING gin(to_tsvector('simple', title))
    """)


# ── Main entry ────────────────────────────────────────────────────────────────

async def scrape_all(progress_cb=None) -> dict:
    """Fetch all Dnipro events and sync to egolist_events table."""
    await init_egolist_events()
    totals = {"new": 0, "updated": 0, "errors": 0, "skipped_past": 0}
    seen_ids: set[str] = set()
    today = datetime.now().date()

    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        # Get total pages first
        total_pages = MAX_PAGES
        total_items = 0
        try:
            resp = await client.get(f"{BASE}/events", params={
                "city_slug": CITY_SLUG, "per_page": 1, "page": 1
            })
            if resp.status_code == 200:
                meta = resp.json().get("meta", {})
                total_pages = min(meta.get("last_page", MAX_PAGES), MAX_PAGES)
                total_items = meta.get("total", 0)
        except Exception as e:
            logger.warning("egolist_events: failed to get meta: %s", e)

        if progress_cb:
            await progress_cb(0, total_pages,
                              f"Знайдено ~{total_items} подій, завантажуємо…")

        for page in range(1, total_pages + 1):
            try:
                resp = await client.get(f"{BASE}/events", params={
                    "city_slug": CITY_SLUG,
                    "per_page": PER_PAGE,
                    "page": page,
                })
                if resp.status_code != 200:
                    logger.warning("egolist_events page %d: HTTP %d", page, resp.status_code)
                    break

                data = resp.json()
                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    api_id = str(item.get("id") or "")
                    if not api_id:
                        continue

                    # Skip past events early
                    d = _parse_date(item.get("date") or "")
                    if d and d < today:
                        totals["skipped_past"] += 1
                        continue

                    n, u = await _upsert(item)
                    totals["new"] += n
                    totals["updated"] += u
                    if n or u:
                        seen_ids.add(api_id)

                # Check if truly last page
                meta = data.get("meta", {})
                if page >= meta.get("last_page", page):
                    break

                if progress_cb:
                    await progress_cb(page, total_pages,
                                      f"Сторінка {page}/{total_pages}")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("egolist_events page %d: %s", page, e)
                totals["errors"] += 1
                break

    # Deactivate events not seen in this scrape
    pool = await get_pool()
    if seen_ids:
        await pool.execute(
            "UPDATE egolist_events SET is_active = FALSE "
            "WHERE api_id != ALL($1::text[]) AND date >= CURRENT_DATE",
            list(seen_ids),
        )
    else:
        logger.warning("egolist_events: no events fetched — skipping deactivation")

    totals["total_active"] = int(
        await pool.fetchval(
            "SELECT COUNT(*) FROM egolist_events WHERE is_active = TRUE"
        ) or 0
    )
    logger.info("egolist_events scrape done: %s", totals)
    return totals


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> Optional[date_type]:
    """Parse DD.MM.YYYY or YYYY-MM-DD."""
    if not date_str:
        return None
    s = date_str.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(time_str: str) -> Optional[time_type]:
    """Parse HH:MM."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str.strip(), "%H:%M").time()
    except Exception:
        return None


def _strip_html(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── DB upsert ─────────────────────────────────────────────────────────────────

async def _upsert(item: dict) -> tuple[int, int]:
    api_id = str(item.get("id") or "")
    title = (item.get("title") or "").strip()
    if not title:
        return 0, 0

    description = _strip_html((item.get("description") or "").strip())
    description = re.sub(r'\s{2,}', ' ', description).strip()[:500]

    date_obj = _parse_date(item.get("date") or "")
    time_obj = _parse_time(item.get("time") or "")

    price_raw = (item.get("price") or "").strip()
    price: Optional[str] = f"{price_raw} грн" if price_raw else None

    place_name = (item.get("place_name") or "").strip() or None

    image_url: Optional[str] = None
    images = item.get("image_links") or []
    if images and isinstance(images, list) and isinstance(images[0], str):
        image_url = images[0]

    source_url = (item.get("source_url") or "").strip() or None
    if not source_url:
        slug = item.get("slug") or ""
        source_url = f"https://egolist.ua/afisha/{slug}" if slug else None

    event_type_obj = item.get("event_type") or {}
    event_slug = (event_type_obj.get("slug") or "").strip()
    event_type = EVENT_TYPE_MAP.get(
        event_slug,
        (event_type_obj.get("title") or "").strip() or None
    )

    pool = await get_pool()
    existing = await pool.fetchval(
        "SELECT id FROM egolist_events WHERE api_id = $1", api_id
    )

    if existing:
        await pool.execute("""
            UPDATE egolist_events
               SET title=$1, description=$2, date=$3, time=$4, price=$5,
                   place_name=$6, image_url=$7, source_url=$8,
                   event_type=$9, event_slug=$10,
                   is_active=TRUE, scraped_at=NOW()
             WHERE api_id=$11
        """, title, description, date_obj, time_obj, price,
             place_name, image_url, source_url,
             event_type, event_slug, api_id)
        return 0, 1
    else:
        await pool.execute("""
            INSERT INTO egolist_events
                (api_id, title, description, date, time, price,
                 place_name, image_url, source_url, event_type, event_slug)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """, api_id, title, description, date_obj, time_obj, price,
             place_name, image_url, source_url, event_type, event_slug)
        return 1, 0
