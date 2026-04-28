"""
Bot search — works EXCLUSIVELY with our CRM database tables:
  - performers  → service/performer searches
  - events      → event/afisha searches (unified table, all sources)
No external API calls. No egolist_products. No egolist_events. No karabas.
"""
import logging
from dataclasses import dataclass
from typing import Optional
from db.performers import search_performers
from db.events_unified import search_crm_events

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


# ── Performers / Services ─────────────────────────────────────────────────────

async def search_products(
    category_names: list[str] | None = None,
    category_ids: list[int] | None = None,  # ignored (legacy param)
    city_id: int | None = None,              # ignored (legacy param)
    max_price: int | None = None,
    search_text: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[ProductResult]:
    """Search performers/venues exclusively from CRM performers table."""
    if not category_names and not search_text:
        return []

    rows = await search_performers(
        category_names=category_names,
        search_text=search_text,
        max_price=max_price,
        limit=limit,
        offset=offset,
    )

    return [
        ProductResult(
            id=r["id"],
            name=r["name"],
            description=(r.get("description") or "")[:300],
            category=r.get("category") or "",
            city=r.get("city") or "Дніпро",
            price=r.get("price_from"),
            phone=r.get("phone"),
            instagram=r.get("instagram"),
            website=r.get("website"),
            telegram_contact=r.get("telegram"),
            photo_url=r.get("photo_url"),
            is_top=bool(r.get("is_featured")),
            product_url=r.get("website"),
        )
        for r in rows
    ]


# ── Events / Afisha ───────────────────────────────────────────────────────────

def _row_to_event(e: dict) -> EventResult:
    return EventResult(
        id=e["id"],
        title=e["title"],
        description=(e.get("description") or "")[:300],
        date=str(e["date"]) if e.get("date") else "",
        time=str(e["time"]) if e.get("time") else None,
        price=e.get("price"),
        place_name=e.get("venue_name"),
        place_address=e.get("venue_address") or "Дніпро",
        city=e.get("city") or "Дніпро",
        photo_url=e.get("image_url"),
        source_url=e.get("ticket_url") or e.get("source_url"),
    )


async def search_karabas_events(
    category: str | None = None,
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search events from CRM unified events table only."""
    rows = await search_crm_events(
        search_text=search_text,
        category=category,
        date_filter=date_filter,
        limit=limit,
        offset=offset,
    )
    return [_row_to_event(r) for r in rows]


async def search_kino_events(
    limit: int = 5,
    offset: int = 0,
    date_filter: str | None = None,
    search_text: str | None = None,
) -> list[EventResult]:
    """Search cinema events from CRM unified events table."""
    rows = await search_crm_events(
        search_text=search_text,
        category="кіно",
        date_filter=date_filter,
        limit=limit,
        offset=offset,
    )
    return [_row_to_event(r) for r in rows]
