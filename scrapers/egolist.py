"""
Scraper for api.egolist.ua
Fetches ALL performers/venues/equipment for Dnipro (city.slug == 'dnipro')
across all 47 subcategories and stores them in egolist_products table.

API hard-limits per_page to 9 items; city_slug param is ignored server-side.
We fetch every page of every category in parallel, filter client-side.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from db.connection import get_pool
from db.egolist_api import CATEGORIES, CITY_SLUG, HEADERS, _parse_products, BASE

logger = logging.getLogger(__name__)

API_PER_PAGE = 9          # Hard server cap
MAX_PAGES = 50            # Safety limit per category
CONCURRENCY = 15          # Max parallel HTTP requests


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_egolist_products() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS egolist_products (
            api_id      TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            category_name TEXT,
            category_id TEXT,
            city        TEXT DEFAULT 'Дніпро',
            price       INTEGER,
            is_price_from BOOLEAN DEFAULT FALSE,
            is_negotiable BOOLEAN DEFAULT FALSE,
            phone       TEXT,
            instagram   TEXT,
            telegram    TEXT,
            website     TEXT,
            photo_url   TEXT,
            product_url TEXT,
            is_top      BOOLEAN DEFAULT FALSE,
            is_active   BOOLEAN DEFAULT TRUE,
            scraped_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Index for fast search
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS egolist_products_name_idx
        ON egolist_products USING gin(to_tsvector('simple', name))
    """)


# ── Main entry ────────────────────────────────────────────────────────────────

async def scrape_all() -> dict:
    """Scrape all 47 categories and sync Dnipro products to egolist_products."""
    await init_egolist_products()

    totals = {"new": 0, "updated": 0, "errors": 0, "skipped_city": 0}
    seen_ids: set[str] = set()
    sem = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20, follow_redirects=True
    ) as client:
        tasks = []
        for cat_name, cat_uuid in CATEGORIES.items():
            tasks.append(_scrape_category(client, sem, cat_name, cat_uuid, totals, seen_ids))

        await asyncio.gather(*tasks)

    # Deactivate products not seen in this scrape
    pool = await get_pool()
    if seen_ids:
        await pool.execute(
            "UPDATE egolist_products SET is_active = FALSE WHERE api_id != ALL($1::text[])",
            list(seen_ids),
        )
    else:
        logger.warning("egolist: no products fetched — skipping deactivation")

    totals["total_active"] = int(
        await pool.fetchval("SELECT COUNT(*) FROM egolist_products WHERE is_active = TRUE") or 0
    )
    logger.info("egolist scrape done: %s", totals)
    return totals


async def _scrape_category(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    cat_name: str,
    cat_uuid: str,
    totals: dict,
    seen_ids: set[str],
) -> None:
    """Fetch all pages of one category and upsert Dnipro products."""
    for page in range(1, MAX_PAGES + 1):
        async with sem:
            try:
                resp = await client.get(
                    f"{BASE}/products/by-subcategory",
                    params={
                        "category_id": cat_uuid,
                        "page": page,
                        "per_page": API_PER_PAGE,
                    },
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                items = _extract_raw(data)
                if not items:
                    break

                # Filter Dnipro client-side
                dnipro_items = [
                    it for it in items
                    if _city_slug(it) == CITY_SLUG
                ]
                totals["skipped_city"] += len(items) - len(dnipro_items)

                for item in dnipro_items:
                    api_id = item.get("id") or ""
                    if not api_id:
                        continue
                    n, u = await _upsert_product(item, cat_name, cat_uuid)
                    totals["new"] += n
                    totals["updated"] += u
                    seen_ids.add(str(api_id))

                # Check if last page
                meta = data.get("meta") or {}
                last_page = meta.get("last_page") or meta.get("lastPage") or page
                if page >= last_page:
                    break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("egolist category %s page %d: %s", cat_name, page, e)
                totals["errors"] += 1
                break


def _city_slug(item: dict) -> str:
    city = item.get("city") or {}
    if isinstance(city, dict):
        return (city.get("slug") or "").lower()
    return ""


def _extract_raw(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "products", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


# ── DB upsert ─────────────────────────────────────────────────────────────────

async def _upsert_product(item: dict, cat_name: str, cat_uuid: str) -> tuple[int, int]:
    api_id = str(item.get("id") or "")
    name = (item.get("name") or "").strip()
    if not name:
        return 0, 0

    desc_raw = (item.get("description") or "").strip()
    import re
    desc = re.sub(r'<[^>]+>', ' ', desc_raw).strip()
    desc = re.sub(r'\s{2,}', ' ', desc)[:500]

    # Price
    price: Optional[int] = None
    raw_price = item.get("price")
    if raw_price is not None:
        try:
            price = int(float(str(raw_price)))
        except Exception:
            pass

    is_price_from = bool(item.get("is_price_from"))
    is_negotiable = bool(item.get("is_negotiable"))

    # Contacts
    user = item.get("user") or {}
    phone = _first(item.get("phone"), user.get("contractor_phone"))
    instagram = _first(item.get("instagram"))
    telegram = _first(item.get("telegram"))
    website = _first(item.get("website"))

    # Photo
    photo_url: Optional[str] = item.get("first_image") or None
    if not photo_url:
        images = item.get("images") or []
        for img in images:
            if isinstance(img, dict):
                conv = img.get("conversions") or {}
                photo_url = conv.get("feed") or conv.get("view") or img.get("path")
                if photo_url:
                    break

    # URL
    slug = item.get("slug_seo") or item.get("slug") or ""
    product_url = f"https://egolist.ua/products/{slug}" if slug else None

    is_top = bool(item.get("is_top") or item.get("is_recommended"))

    city_obj = item.get("city") or {}
    city_name = (city_obj.get("name") if isinstance(city_obj, dict) else None) or "Дніпро"

    pool = await get_pool()
    existing = await pool.fetchval(
        "SELECT api_id FROM egolist_products WHERE api_id = $1", api_id
    )

    if existing:
        await pool.execute("""
            UPDATE egolist_products
               SET name=$1, description=$2, category_name=$3, category_id=$4,
                   city=$5, price=$6, is_price_from=$7, is_negotiable=$8,
                   phone=$9, instagram=$10, telegram=$11, website=$12,
                   photo_url=$13, product_url=$14, is_top=$15,
                   is_active=TRUE, scraped_at=NOW()
             WHERE api_id=$16
        """, name, desc, cat_name, cat_uuid,
             city_name, price, is_price_from, is_negotiable,
             phone, instagram, telegram, website,
             photo_url, product_url, is_top, api_id)
        return 0, 1
    else:
        await pool.execute("""
            INSERT INTO egolist_products
                (api_id, name, description, category_name, category_id,
                 city, price, is_price_from, is_negotiable,
                 phone, instagram, telegram, website,
                 photo_url, product_url, is_top)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        """, api_id, name, desc, cat_name, cat_uuid,
             city_name, price, is_price_from, is_negotiable,
             phone, instagram, telegram, website,
             photo_url, product_url, is_top)
        return 1, 0


def _first(*values) -> Optional[str]:
    for v in values:
        s = (v or "").strip() if v else ""
        if s:
            return s
    return None
