"""
Scraper for api.kino-teatr.ua
Fetches films currently showing in Dnipro (city_id=5).
API: https://api.kino-teatr.ua/api/v1/
Each film is stored as ONE row in kino_events (aggregated across cinemas).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date as date_type, datetime, timedelta
from typing import Optional

import httpx

from db.connection import get_pool

logger = logging.getLogger(__name__)

BASE_API = "https://api.kino-teatr.ua/api/v1"
BASE_SITE = "https://kino-teatr.ua"
CITY_ID = 5  # Dnipro

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9",
    "Referer": "https://kino-teatr.ua/",
}


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_kino_events() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS kino_events (
            id          SERIAL PRIMARY KEY,
            film_id     INTEGER,
            title       TEXT NOT NULL,
            description TEXT,
            genre       TEXT,
            date_from   DATE,
            date_to     DATE,
            price       TEXT,
            cinema_name TEXT,
            image_url   TEXT,
            source_url  TEXT UNIQUE NOT NULL,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            scraped_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


# ── Main entry point ──────────────────────────────────────────────────────────

async def scrape_all() -> dict:
    await init_kino_events()
    totals = {"new": 0, "updated": 0, "errors": 0}
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=15, follow_redirects=True
    ) as client:
        films = await _fetch_films(client)
        logger.info(f"kino-teatr: fetched {len(films)} films for Dnipro")

        # Process all films in parallel (max 10 concurrent)
        sem = asyncio.Semaphore(10)

        async def _safe_process(film):
            async with sem:
                try:
                    return await _process_film(client, film)
                except Exception as e:
                    title = film.get("title") or film.get("name") or "?"
                    logger.warning(f"kino-teatr film '{title}' error: {e}")
                    return 0, 0, None

        results = await asyncio.gather(*[_safe_process(f) for f in films])
        for n, u, url in results:
            totals["new"] += n
            totals["updated"] += u
            if url:
                seen_urls.add(url)

    pool = await get_pool()
    if seen_urls:
        await pool.execute(
            "UPDATE kino_events SET is_active = FALSE WHERE source_url != ALL($1::text[])",
            list(seen_urls),
        )
    else:
        # If we fetched nothing at all — leave existing rows active, don't wipe
        logger.warning("kino-teatr: no films fetched — skipping deactivation")

    totals["total_active"] = (
        await pool.fetchval("SELECT COUNT(*) FROM kino_events WHERE is_active = TRUE") or 0
    )
    logger.info(f"kino-teatr scrape done: {totals}")
    return totals


# ── Film fetch ────────────────────────────────────────────────────────────────

async def _fetch_films(client: httpx.AsyncClient) -> list[dict]:
    """Try multiple likely API endpoints to get films showing in Dnipro."""
    params_sets = [
        {"city_id": CITY_ID, "limit": 100},
        {"city_id": CITY_ID, "per_page": 100},
        {"city_id": CITY_ID},
    ]
    endpoints = [
        f"{BASE_API}/films/now-showing",
        f"{BASE_API}/films/showing",
        f"{BASE_API}/films",
        f"{BASE_API}/film",
    ]

    for url in endpoints:
        for params in params_sets:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                ct = resp.headers.get("content-type", "")
                if "json" not in ct:
                    logger.debug(f"kino-teatr: {url} returned non-JSON ({ct[:40]})")
                    continue
                data = resp.json()
                films = _extract_list(data, ("data", "films", "results", "items"))
                if films:
                    logger.info(f"kino-teatr: {len(films)} films from {url}")
                    return films
            except Exception as e:
                logger.debug(f"kino-teatr endpoint {url}: {e}")

    # Fallback: try schedule for today+7 days
    return await _fetch_schedule_films(client)


async def _fetch_schedule_films(client: httpx.AsyncClient) -> list[dict]:
    """Fetch today's + next 7 days schedule and deduplicate by film_id."""
    films_by_id: dict[int, dict] = {}
    today = datetime.now().date()

    for day_offset in range(8):  # today + 7 days
        date_str = (today + timedelta(days=day_offset)).isoformat()
        for url in [
            f"{BASE_API}/schedule",
            f"{BASE_API}/sessions",
            f"{BASE_API}/seances",
        ]:
            try:
                resp = await client.get(url, params={"city_id": CITY_ID, "date": date_str})
                if resp.status_code != 200:
                    continue
                ct = resp.headers.get("content-type", "")
                if "json" not in ct:
                    continue
                data = resp.json()
                items = _extract_list(data, ("data", "schedule", "sessions", "seances", "results"))
                for item in items:
                    film = item.get("film") or item.get("movie") or item
                    fid = film.get("id")
                    if fid and fid not in films_by_id:
                        films_by_id[fid] = film
                if items:
                    break  # found working endpoint
            except Exception as e:
                logger.debug(f"kino-teatr schedule {url} {date_str}: {e}")

    return list(films_by_id.values())


# ── Per-film processing ───────────────────────────────────────────────────────

async def _process_film(
    client: httpx.AsyncClient, film: dict
) -> tuple[int, int, Optional[str]]:
    film_id = film.get("id")
    title = (film.get("title") or film.get("name") or "").strip()
    if not title:
        return 0, 0, None

    description = (
        film.get("description") or film.get("synopsis") or film.get("about") or ""
    ).strip()[:500]

    genre = _extract_genre(film)

    # Poster image
    image_url = (
        film.get("poster") or film.get("poster_url") or
        film.get("image") or film.get("image_url") or
        _nested(film, "images", 0, "url") or ""
    ).strip() or None

    # Source URL for tickets
    source_url = (
        film.get("url") or film.get("ticket_url") or
        film.get("link") or
        (f"{BASE_SITE}/uk/film/{film_id}/" if film_id else None)
    )
    if not source_url:
        return 0, 0, None

    # Get sessions to determine date range + cinemas + price
    sessions = await _fetch_film_sessions(client, film_id)
    date_from, date_to, price, cinema_names = _aggregate_sessions(sessions)

    # If no sessions found but film is in list — use next 14 days as range
    if not date_from:
        date_from = datetime.now().date()
        date_to = date_from + timedelta(days=14)

    cinema_str = ", ".join(sorted(cinema_names)) if cinema_names else None

    return await _upsert(
        film_id=film_id,
        title=title,
        description=description,
        genre=genre,
        date_from=date_from,
        date_to=date_to,
        price=price,
        cinema_name=cinema_str,
        image_url=image_url,
        source_url=source_url,
    )


async def _fetch_film_sessions(
    client: httpx.AsyncClient, film_id: Optional[int]
) -> list[dict]:
    if not film_id:
        return []
    today = datetime.now().date()
    end_date = today + timedelta(days=14)

    for url in [
        f"{BASE_API}/films/{film_id}/sessions",
        f"{BASE_API}/films/{film_id}/seances",
        f"{BASE_API}/sessions",
        f"{BASE_API}/seances",
    ]:
        try:
            params = {"city_id": CITY_ID, "film_id": film_id,
                      "from": today.isoformat(), "to": end_date.isoformat()}
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                continue
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                continue
            data = resp.json()
            items = _extract_list(data, ("data", "sessions", "seances", "schedule", "results"))
            if items:
                return items
        except Exception as e:
            logger.debug(f"kino-teatr sessions {url} film={film_id}: {e}")
    return []


def _aggregate_sessions(sessions: list[dict]) -> tuple[
    Optional[date_type], Optional[date_type], Optional[str], set[str]
]:
    """Extract date_from, date_to, price, set of cinema names from sessions list."""
    dates: list[date_type] = []
    prices: list[str] = []
    cinema_names: set[str] = set()
    today = datetime.now().date()

    for s in sessions:
        # Date
        date_str = (
            s.get("date") or s.get("session_date") or s.get("start_date") or
            s.get("datetime") or s.get("time") or ""
        )
        if date_str:
            try:
                d = date_type.fromisoformat(str(date_str)[:10])
                if d >= today:
                    dates.append(d)
            except Exception:
                pass

        # Price
        price_raw = (
            s.get("price") or s.get("min_price") or s.get("price_from") or
            _nested(s, "prices", "min") or ""
        )
        if price_raw:
            p = str(price_raw).strip()
            if p and p not in prices:
                prices.append(p)

        # Cinema name
        cinema = s.get("cinema") or s.get("theatre") or {}
        if isinstance(cinema, dict):
            name = cinema.get("name") or cinema.get("title") or ""
        else:
            name = str(cinema)
        name = (s.get("cinema_name") or name or "").strip()
        if name:
            cinema_names.add(name)

    date_from = min(dates) if dates else None
    date_to = max(dates) if dates else None

    price: Optional[str] = None
    if prices:
        try:
            nums = [float(str(p).replace(" ", "").replace(",", ".")) for p in prices if str(p).replace(".", "").replace(",", "").isdigit()]
            if nums:
                price = f"від {int(min(nums))} грн"
        except Exception:
            price = f"від {prices[0]} грн"

    return date_from, date_to, price, cinema_names


# ── DB upsert ─────────────────────────────────────────────────────────────────

async def _upsert(
    film_id, title, description, genre,
    date_from, date_to, price, cinema_name, image_url, source_url,
) -> tuple[int, int, str]:
    pool = await get_pool()
    existing = await pool.fetchval(
        "SELECT id FROM kino_events WHERE source_url = $1", source_url
    )
    if existing:
        await pool.execute("""
            UPDATE kino_events
               SET film_id=$1, title=$2, description=$3, genre=$4,
                   date_from=$5, date_to=$6, price=$7,
                   cinema_name=$8, image_url=$9,
                   is_active=TRUE, scraped_at=NOW()
             WHERE source_url=$10
        """, film_id, title, description, genre,
             date_from, date_to, price,
             cinema_name, image_url, source_url)
        return 0, 1, source_url
    else:
        await pool.execute("""
            INSERT INTO kino_events
                (film_id, title, description, genre, date_from, date_to,
                 price, cinema_name, image_url, source_url)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """, film_id, title, description, genre,
             date_from, date_to, price,
             cinema_name, image_url, source_url)
        return 1, 0, source_url


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_list(data, keys: tuple) -> list:
    """Extract a list from a JSON response using a priority list of keys."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
    return []


def _extract_genre(film: dict) -> Optional[str]:
    genre = film.get("genre") or film.get("genres") or film.get("genre_name") or ""
    if isinstance(genre, list):
        parts = []
        for g in genre:
            if isinstance(g, dict):
                parts.append(g.get("name") or g.get("title") or "")
            else:
                parts.append(str(g))
        return ", ".join(p for p in parts if p) or None
    return str(genre).strip() or None


def _nested(obj: dict, *keys):
    """Safely navigate nested dict/list."""
    cur = obj
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list) and isinstance(k, int) and k < len(cur):
            cur = cur[k]
        else:
            return None
    return cur
