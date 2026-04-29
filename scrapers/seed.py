"""
One-time seed helpers — loads test data into CRM tables.

  seed_karabas_events(limit)   → scrapes dnipro.karabas.com → events table (source='karabas')
  seed_egolist_performers(limit) → calls Egolist API → performers table (source='egolist')

Designed to be called from admin API endpoints (POST /api/seed-karabas, /api/seed-egolist).
Safe to re-run: uses ON CONFLICT / deduplication so no doubles.
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
from db.egolist_api import CATEGORIES, DNIPRO_CITY_SLUGS, HEADERS as EGO_HEADERS, _parse_products, _extract_list

logger = logging.getLogger(__name__)


# ── Karabas → events table ────────────────────────────────────────────────────

KARABAS_BASE = "https://dnipro.karabas.com"
KARABAS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9",
}
KARABAS_CATEGORIES = [
    ("concerts",    "концерти"),
    ("theatres",    "театр"),
    ("child",       "для дітей"),
    ("stand-up",    "стендап"),
    ("festivals",   "фестивалі"),
    ("clubs",       "клуби"),
    ("exhibitions", "виставки"),
    ("sport",       "спорт"),
]


async def seed_karabas_events(limit: int = 50) -> dict:
    """Scrape Karabas Dnipro events and insert up to `limit` into events table."""
    pool = await get_pool()
    collected: list[dict] = []
    today = datetime.now().date()

    async with httpx.AsyncClient(
        headers=KARABAS_HEADERS, timeout=30, follow_redirects=True
    ) as client:
        for slug, category_ua in KARABAS_CATEGORIES:
            if len(collected) >= limit:
                break
            try:
                url = f"{KARABAS_BASE}/{slug}/"
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("Karabas [%s] HTTP %s", slug, resp.status_code)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                events = _karabas_extract_jsonld(soup)
                if not events:
                    events = _karabas_extract_html(soup)

                logger.info("Karabas [%s] found %d events", slug, len(events))

                for evt in events:
                    if len(collected) >= limit:
                        break
                    parsed = _karabas_parse(evt, category_ua, today)
                    if parsed:
                        collected.append(parsed)

            except Exception as e:
                logger.error("Karabas [%s] error: %s", slug, e)

    # Insert or update events table
    inserted = 0
    updated = 0
    skipped = 0
    for ev in collected:
        try:
            existing = await pool.fetchrow(
                "SELECT id, description FROM events WHERE source='karabas' AND source_url=$1",
                ev["source_url"],
            )
            if existing:
                # Update fields that may have been empty on first seed
                new_desc = ev.get("description", "")
                await pool.execute("""
                    UPDATE events SET
                        title       = $1,
                        description = CASE WHEN (description IS NULL OR description = '') THEN $2 ELSE description END,
                        date        = $3,
                        time        = $4,
                        price       = COALESCE(NULLIF($5,''), price),
                        venue_name  = COALESCE(NULLIF($6,''), venue_name),
                        image_url   = COALESCE(NULLIF($7,''), image_url)
                    WHERE id = $8
                """,
                    ev["title"], new_desc,
                    ev.get("date"), ev.get("time"),
                    ev.get("price") or "", ev.get("venue_name") or "",
                    ev.get("image_url") or "", existing["id"],
                )
                updated += 1
                continue
            await pool.execute("""
                INSERT INTO events
                    (source, title, description, category, date, time, price,
                     venue_name, venue_address, city,
                     image_url, source_url, ticket_url,
                     is_published, is_featured, priority)
                VALUES ('karabas',$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11,TRUE,FALSE,0)
            """,
                ev["title"], ev.get("description", ""), ev["category"],
                ev.get("date"), ev.get("time"),
                ev.get("price"), ev.get("venue_name"),
                "Дніпро", "Дніпро",
                ev.get("image_url"), ev["source_url"],
            )
            inserted += 1
        except Exception as e:
            logger.warning("Karabas insert error '%s': %s", ev.get("title"), e)

    logger.info("Karabas seed done: %d inserted, %d updated, %d skipped", inserted, updated, skipped)
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total_parsed": len(collected)}


def _karabas_extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            text = re.sub(r",\s*([}\]])", r"\1", script.string or "")
            data = json.loads(text)
            if isinstance(data, dict) and "startDate" in data and "name" in data:
                events.append(data)
        except Exception:
            pass
    return events


def _karabas_extract_html(soup: BeautifulSoup) -> list[dict]:
    events = []
    for card in soup.find_all("div", class_="result-event"):
        try:
            title_tag = card.find("a", class_="section-title-h3")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            url   = title_tag.get("href", "")

            dt_tag = card.find("span", class_="date-time")
            start_date = None
            if dt_tag and dt_tag.get("data-event-time"):
                ts = int(dt_tag["data-event-time"])
                start_date = datetime.fromtimestamp(ts).isoformat()

            venue_tag = card.find("a", class_="dotted-link")
            place_name = venue_tag.get_text(strip=True) if venue_tag else None

            img_tag = card.find("img")
            image = img_tag.get("src") if img_tag else None

            price_tag = card.find("div", class_="ev-buy")
            price_text = None
            if price_tag:
                strong = price_tag.find("strong")
                if strong and strong.get_text(strip=True):
                    price_text = strong.get_text(strip=True) + " UAH"

            if title and url:
                events.append({
                    "name": title, "url": url, "startDate": start_date,
                    "image": image,
                    "location": {"name": place_name} if place_name else {},
                    "offers": {"lowPrice": price_text, "priceCurrency": "UAH"} if price_text else {},
                })
        except Exception:
            continue
    return events


def _karabas_parse(evt: dict, category_ua: str, today) -> Optional[dict]:
    title      = (evt.get("name") or "").strip()
    source_url = (evt.get("url")  or "").strip()
    if not title or not source_url:
        return None

    date_obj = time_obj = None
    raw_date = evt.get("startDate") or ""
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date)
            date_obj = dt.date()
            time_obj = dt.time()
        except Exception:
            pass

    if date_obj and date_obj < today:
        return None  # skip past events

    price: Optional[str] = None
    offers = evt.get("offers") or {}
    if isinstance(offers, dict):
        if "SoldOut" in (offers.get("availability") or ""):
            return None
        low = offers.get("lowPrice")
        high = offers.get("highPrice")
        cur  = offers.get("priceCurrency", "UAH")
        if low and high and str(low) != str(high):
            price = f"{low}–{high} {cur}"
        elif low:
            price = f"від {low} {cur}"

    venue_name: Optional[str] = None
    location = evt.get("location") or {}
    if isinstance(location, dict):
        venue_name = location.get("name")

    description = (evt.get("description") or "").strip()

    return {
        "title":       title,
        "category":    category_ua,
        "description": description,
        "date":        date_obj,
        "time":        time_obj,
        "price":       price,
        "venue_name":  venue_name,
        "image_url":   evt.get("image"),
        "source_url":  source_url,
    }


# ── Egolist → performers table ────────────────────────────────────────────────

# Categories to seed (mix of specialists and locations)
SEED_CATEGORIES = [
    "ведучі", "музиканти", "фото та відеозйомка", "аніматори",
    "артисти та шоу", "оформлення та декор", "ресторани та банкетні зали",
    "кондитери", "танцювальні шоу", "організатори заходів",
]

EGOLIST_BASE = "https://api.egolist.ua/api"


async def seed_egolist_performers(limit: int = 50) -> dict:
    """Fetch performers from Egolist API and insert up to `limit` into performers table."""
    pool = await get_pool()
    collected: list[dict] = []
    per_cat = max(5, limit // len(SEED_CATEGORIES))  # ~5 per category

    async with httpx.AsyncClient(
        headers=EGO_HEADERS, timeout=20, follow_redirects=True
    ) as client:
        for cat_name in SEED_CATEGORIES:
            if len(collected) >= limit:
                break
            uuid = CATEGORIES.get(cat_name)
            if not uuid:
                continue
            try:
                resp = await client.get(
                    f"{EGOLIST_BASE}/products/by-subcategory",
                    params={"category_id": uuid, "city_slug": "dnipro",
                            "page": 1, "per_page": 50},
                )
                if resp.status_code != 200:
                    logger.warning("Egolist API [%s] HTTP %s", cat_name, resp.status_code)
                    continue

                items = _extract_list(resp.json())
                products = _parse_products(items)
                logger.info("Egolist [%s] got %d products", cat_name, len(products))

                count = 0
                for p in products:
                    if count >= per_cat or len(collected) >= limit:
                        break
                    collected.append({
                        "name":        p.name,
                        "category":    cat_name,
                        "description": p.description or "",
                        "city":        p.city or "Дніпро",
                        "price_from":  p.price,
                        "phone":       p.phone,
                        "instagram":   p.instagram,
                        "telegram":    p.telegram_contact,
                        "website":     p.website or p.product_url,
                        "photo_url":   p.photo_url,
                        "is_featured": p.is_top,
                    })
                    count += 1

            except Exception as e:
                logger.error("Egolist seed [%s] error: %s", cat_name, e)

    # Insert into performers table (deduplicate by name+category)
    inserted = 0
    skipped = 0
    for p in collected:
        try:
            existing = await pool.fetchval(
                "SELECT id FROM performers WHERE name=$1 AND source='egolist'", p["name"]
            )
            if existing:
                skipped += 1
                continue
            await pool.execute("""
                INSERT INTO performers
                    (name, category, description, city, price_from,
                     phone, instagram, telegram, website, photo_url,
                     is_published, is_featured, priority, source)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,TRUE,$11,0,'egolist')
            """,
                p["name"], p["category"], p["description"],
                p["city"], p["price_from"],
                p["phone"], p["instagram"], p["telegram"],
                p["website"], p["photo_url"], p["is_featured"],
            )
            inserted += 1
        except Exception as e:
            logger.warning("Egolist performer insert error '%s': %s", p.get("name"), e)

    logger.info("Egolist performers seed done: %d inserted, %d skipped", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "total_parsed": len(collected)}
