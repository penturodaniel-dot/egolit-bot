"""
Scraper for dnipro.karabas.com
URL pattern: https://dnipro.karabas.com/{category}/  (no /ua/ prefix — Ukrainian is default)
Data source: JSON-LD <script> tags that appear after each div.result-event card
"""
from __future__ import annotations
import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from db.connection import get_pool

logger = logging.getLogger(__name__)

BASE = "https://dnipro.karabas.com"

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
    "Accept-Language": "uk-UA,uk;q=0.9",
}

# ── DB init ───────────────────────────────────────────────────────────────

async def init_karabas_events() -> None:
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
    await init_karabas_events()

    totals = {"new": 0, "updated": 0, "errors": 0}
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=30, follow_redirects=True
    ) as client:
        for slug, category_ua in CATEGORIES:
            try:
                stats, urls = await _scrape_category(client, slug, category_ua)
                totals["new"]     += stats["new"]
                totals["updated"] += stats["updated"]
                seen_urls.update(urls)
            except Exception as e:
                logger.error(f"Karabas [{slug}] error: {e}")
                totals["errors"] += 1

    # Deactivate events no longer on site
    pool = await get_pool()
    if seen_urls:
        await pool.execute("""
            UPDATE karabas_events
            SET is_active = FALSE
            WHERE source_url != ALL($1::text[])
        """, list(seen_urls))

    totals["total_active"] = await pool.fetchval(
        "SELECT COUNT(*) FROM karabas_events WHERE is_active = TRUE"
    ) or 0

    logger.info(f"Karabas scrape done: {totals}")
    return totals


# ── Per-category scrape ───────────────────────────────────────────────────

async def _scrape_category(
    client: httpx.AsyncClient, slug: str, category_ua: str
) -> tuple[dict, list[str]]:
    # Ukrainian is default locale — no /ua/ prefix needed
    url = f"{BASE}/{slug}/"
    resp = await client.get(url)

    if resp.status_code != 200:
        logger.warning(f"  [{slug}] HTTP {resp.status_code} for {url}")
        return {"new": 0, "updated": 0}, []

    soup = BeautifulSoup(resp.text, "html.parser")

    # JSON-LD blocks appear as siblings after each div.result-event
    events = _extract_jsonld(soup)
    logger.info(f"  [{slug}] found {len(events)} JSON-LD events")

    if not events:
        # Fallback: try parsing HTML cards directly
        events = _extract_from_html(soup, category_ua)
        logger.info(f"  [{slug}] HTML fallback: {len(events)} events")

    pool = await get_pool()
    new_count, updated_count = 0, 0
    scraped_urls: list[str] = []

    for evt in events:
        try:
            src_url, result = await _upsert_event(pool, evt, category_ua)
            if src_url:
                scraped_urls.append(src_url)
            if result == "new":
                new_count += 1
            elif result == "updated":
                updated_count += 1
        except Exception as e:
            logger.warning(f"  Save error '{evt.get('name', '?')}': {e}")

    logger.info(f"  [{slug}] {new_count} new / {updated_count} updated")
    return {"new": new_count, "updated": updated_count}, scraped_urls


# ── Parsers ───────────────────────────────────────────────────────────────

def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    """Extract all JSON-LD event objects from the page."""
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            text = script.string or ""
            # Fix trailing commas (Karabas has invalid JSON sometimes)
            text = re.sub(r",\s*([}\]])", r"\1", text)
            data = json.loads(text)
            if isinstance(data, dict) and "startDate" in data and "name" in data:
                events.append(data)
        except Exception as e:
            logger.debug(f"JSON-LD parse error: {e}")
    return events


def _extract_from_html(soup: BeautifulSoup, category_ua: str) -> list[dict]:
    """Fallback: parse event cards from HTML directly."""
    events = []
    for card in soup.find_all("div", class_="result-event"):
        try:
            title_tag = card.find("a", class_="section-title-h3")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            url   = title_tag.get("href", "")

            # Date/time from data-event-time (Unix timestamp)
            dt_tag = card.find("span", class_="date-time")
            start_date = None
            if dt_tag and dt_tag.get("data-event-time"):
                ts = int(dt_tag["data-event-time"])
                start_date = datetime.fromtimestamp(ts).isoformat()

            # Venue
            venue_tag = card.find("a", class_="dotted-link")
            place_name = venue_tag.get_text(strip=True) if venue_tag else None

            # Image
            img_tag = card.find("img")
            image = img_tag.get("src") if img_tag else None

            # Price
            price_tag = card.find("div", class_="ev-buy")
            price_text = None
            if price_tag:
                strong = price_tag.find("strong")
                if strong and strong.get_text(strip=True):
                    price_text = strong.get_text(strip=True) + " UAH"

            if title and url:
                events.append({
                    "name": title,
                    "url": url,
                    "startDate": start_date,
                    "image": image,
                    "location": {"name": place_name} if place_name else {},
                    "offers": {"lowPrice": price_text, "priceCurrency": "UAH",
                               "availability": "InStock"} if price_text else {},
                })
        except Exception:
            continue
    return events


def _parse_iso(iso: str) -> tuple[Optional[str], Optional[str]]:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return None, None


async def _upsert_event(pool, evt: dict, category_ua: str) -> tuple[Optional[str], str]:
    title      = (evt.get("name") or "").strip()
    source_url = (evt.get("url")  or "").strip()
    if not title or not source_url:
        return None, "skip"

    date_str, time_str = _parse_iso(evt.get("startDate") or "")

    # Skip past events
    if date_str and date_str < datetime.now().strftime("%Y-%m-%d"):
        return source_url, "skip"

    # Price
    price: Optional[str] = None
    offers = evt.get("offers") or {}
    if isinstance(offers, dict):
        availability = offers.get("availability", "")
        # Only skip truly sold-out events, keep rescheduled
        if "SoldOut" in availability:
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

    image_url = evt.get("image")

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
