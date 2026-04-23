"""
Scraper for dnipro.karabas.com — fetches events by category,
parses JSON-LD structured data (cleanest source), saves to karabas_events table.

Usage:
    from scrapers.karabas import scrape_all
    stats = await scrape_all()   # {"new": 42, "updated": 10, "errors": 0}
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from db.connection import get_pool

logger = logging.getLogger(__name__)

BASE = "https://dnipro.karabas.com"

# All categories available on Karabas Dnipro
CATEGORIES = [
    ("concerts",    "концерти"),
    ("theatres",    "театр"),
    ("child",       "діти"),
    ("stand-up",    "стендап"),
    ("festivals",   "фестивалі"),
    ("clubs",       "клуби"),
    ("exhibitions", "виставки"),
    ("sport",       "спорт"),
    ("circus",      "цирк"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
}


# ── DB init ───────────────────────────────────────────────────────────────

async def init_karabas_events() -> None:
    """Create karabas_events table if it doesn't exist."""
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS karabas_events (
            id         SERIAL PRIMARY KEY,
            title      TEXT NOT NULL,
            date       DATE,
            time       TIME,
            price      TEXT,
            place_name TEXT,
            image_url  TEXT,
            source_url TEXT UNIQUE NOT NULL,
            category   TEXT,
            is_active  BOOLEAN NOT NULL DEFAULT TRUE,
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


# ── Main entry point ──────────────────────────────────────────────────────

async def scrape_all() -> dict:
    """
    Scrape all categories. Marks events no longer on site as inactive.
    Returns {"new": N, "updated": N, "errors": N, "total_active": N}
    """
    await init_karabas_events()

    totals = {"new": 0, "updated": 0, "errors": 0}
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20, follow_redirects=True
    ) as client:
        for slug, category_ua in CATEGORIES:
            try:
                stats, urls = await _scrape_category(client, slug, category_ua)
                totals["new"]     += stats["new"]
                totals["updated"] += stats["updated"]
                seen_urls.update(urls)
            except Exception as e:
                logger.error(f"Karabas scrape error [{slug}]: {e}")
                totals["errors"] += 1

    # Deactivate events no longer found on the site
    pool = await get_pool()
    if seen_urls:
        await pool.execute("""
            UPDATE karabas_events SET is_active = FALSE
            WHERE source_url NOT IN (SELECT unnest($1::text[]))
        """, list(seen_urls))

    totals["total_active"] = await pool.fetchval(
        "SELECT COUNT(*) FROM karabas_events WHERE is_active = TRUE"
    )
    logger.info(f"Karabas scrape done: {totals}")
    return totals


# ── Per-category scrape ───────────────────────────────────────────────────

async def _scrape_category(
    client: httpx.AsyncClient, slug: str, category_ua: str
) -> tuple[dict, list[str]]:
    url = f"{BASE}/ua/{slug}/"
    resp = await client.get(url)
    if resp.status_code != 200:
        logger.warning(f"Karabas /{slug}/: HTTP {resp.status_code}")
        return {"new": 0, "updated": 0}, []

    soup = BeautifulSoup(resp.text, "html.parser")
    jsonld_events = _extract_jsonld(soup)

    # Build image map from HTML (JSON-LD sometimes lacks image)
    image_map: dict[str, str] = {}
    for card in soup.find_all("div", class_="result-event"):
        a = card.find("a", class_="section-title-h3")
        img = card.find("img")
        if a and img:
            href = a.get("href", "")
            src = img.get("src") or img.get("data-src", "")
            if href and src and not src.endswith("placeholder.png"):
                image_map[href] = src

    pool = await get_pool()
    new_count, updated_count = 0, 0
    scraped_urls: list[str] = []

    for evt in jsonld_events:
        try:
            src_url, result = await _upsert_event(
                pool, evt, category_ua, image_map
            )
            if src_url:
                scraped_urls.append(src_url)
            if result == "new":
                new_count += 1
            elif result == "updated":
                updated_count += 1
        except Exception as e:
            logger.warning(f"Save error '{evt.get('name', '?')}': {e}")

    logger.info(f"  [{slug}] {new_count} new / {updated_count} updated")
    return {"new": new_count, "updated": updated_count}, scraped_urls


# ── Helpers ───────────────────────────────────────────────────────────────

def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and "startDate" in data and "name" in data:
                events.append(data)
        except Exception:
            pass
    return events


def _parse_iso(iso: str) -> tuple[Optional[str], Optional[str]]:
    """'2026-07-04T17:00:00+03:00' → ('2026-07-04', '17:00')"""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return None, None


async def _upsert_event(
    pool, evt: dict, category_ua: str, image_map: dict
) -> tuple[Optional[str], str]:
    """Insert or update one event. Returns (source_url, 'new'|'updated'|'skip')."""
    title = (evt.get("name") or "").strip()
    source_url = (evt.get("url") or "").strip()
    if not title or not source_url:
        return None, "skip"

    # Skip past events
    date_str, time_str = _parse_iso(evt.get("startDate", ""))
    if date_str and date_str < datetime.now().strftime("%Y-%m-%d"):
        return source_url, "skip"

    # Price
    price: Optional[str] = None
    offers = evt.get("offers") or {}
    if isinstance(offers, dict):
        availability = offers.get("availability", "")
        if "SoldOut" in availability or "Rescheduled" in availability:
            return source_url, "skip"
        low  = offers.get("lowPrice")
        high = offers.get("highPrice")
        cur  = offers.get("priceCurrency", "UAH")
        if low and high and str(low) != str(high):
            price = f"{low}–{high} {cur}"
        elif low:
            price = f"від {low} {cur}"

    # Venue
    place_name: Optional[str] = None
    location = evt.get("location") or {}
    if isinstance(location, dict):
        place_name = location.get("name")

    # Image: prefer JSON-LD, fall back to HTML card
    image_url = evt.get("image") or image_map.get(source_url)

    existing = await pool.fetchval(
        "SELECT id FROM karabas_events WHERE source_url = $1", source_url
    )

    if existing:
        await pool.execute("""
            UPDATE karabas_events
               SET title=$1, date=$2, time=$3, price=$4,
                   place_name=$5, image_url=$6, category=$7,
                   is_active=TRUE, scraped_at=NOW()
             WHERE source_url=$8
        """, title, date_str, time_str, price,
             place_name, image_url, category_ua, source_url)
        return source_url, "updated"
    else:
        await pool.execute("""
            INSERT INTO karabas_events
                (title, date, time, price, place_name, image_url, source_url, category)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """, title, date_str, time_str, price,
             place_name, image_url, source_url, category_ua)
        return source_url, "new"
