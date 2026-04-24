"""
Egolist public API client — замінює прямі asyncpg запити до Egolist БД.
API: https://api.egolist.ua/api/
Категорії отримано з: GET /api/tree-categories
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from db.queries import ProductResult

logger = logging.getLogger(__name__)

BASE = "https://api.egolist.ua/api"
CITY_SLUG = "dnipro"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ── Категорії (з GET /api/tree-categories) ────────────────────────────────────
# key = коротка назва для AI-промпту, value = UUID для API запиту

CATEGORIES: dict[str, str] = {
    # ── Спеціалісти ──────────────────────────────────────────────────────────
    "ведучі":                         "5859fdca-2d6e-4c78-9ddf-70ac63836196",
    "музиканти":                      "ff5ec0a6-0008-4d9d-ab63-6f70bc949d64",
    "фото та відеозйомка":            "cd27618a-153f-4eee-99c9-3a636f325d59",
    "аніматори":                      "5647ac68-2b38-49d0-9ee3-6c652a3ad214",
    "артисти та шоу":                 "6fe5b888-4d6f-4ea7-987f-2779d3e22b16",
    "кейтеринг та бар":               "8780e124-c767-4844-b7f1-bb876aef5481",
    "оформлення та декор":            "7476b52b-d129-4fce-9169-ee5912a992a2",
    "організатори заходів":           "556cdaf1-0eb9-468f-be9f-8641b08d3972",
    "візажисти та зачіски":           "30979323-dd86-495a-9e2b-ac1962be275f",
    "кондитери":                      "4ae324b2-09ab-43bc-a133-5e38baca50cb",
    "танцювальні шоу":                "fba0ff82-1647-4c8c-ac4e-74fdad5ae1ee",
    "актори":                         "7c2908c3-c87c-42e3-9e57-98d19a7cf72f",
    "хостес":                         "3d087f38-ac37-4927-a48c-6152121cdc31",
    "персонал для заходів":           "752117d7-bc8b-4661-951b-948236eb429d",
    "поліграфія":                     "0327a21b-81ec-4c43-9560-a16aaf0ee2d4",
    "оренда транспорту":              "3246c57a-8086-46b7-ba64-f0aaaa00babf",
    "майстер-класи":                  "f0a9a579-dc59-4bf5-a39a-de361a594a03",
    "блогери":                        "0c747137-209e-455a-85f4-ebc071ea52fe",
    "перекладачі":                    "1dfda953-5813-4afb-a954-ecbe85e6742c",
    # ── Локації ──────────────────────────────────────────────────────────────
    "ресторани та банкетні зали":     "8fb9522c-ca0e-4e2a-8825-f964ee57876b",
    "розважальні заклади":            "1980a219-7cec-4f20-9d15-9e69f881902c",
    "готелі та комплекси":            "4e143c3d-90d8-47cf-9f3f-a65b013207f1",
    "квест-кімнати":                  "4cf55326-283a-41e7-9407-fad2b0ed073e",
    "нічні клуби та караоке":         "478fc1cd-5f60-4268-95e0-82e77de77bbe",
    "фото та відеостудії":            "826f6b55-1de4-4358-9796-542a26fb4058",
    "конференц-зали":                 "8b319dee-c26a-4dbe-a907-4b550e9d72bc",
    "бази відпочинку":                "3f4878e2-440b-4776-8f33-cd034db93732",
    "місця для весільних церемоній":  "dd158f8c-a194-4db1-ba6a-6f5f3f7139d0",
    "івент-простори":                 "bac6d731-1b64-450b-8e5c-d8302ec4a891",
    "альтанки та бесідки":            "3c7a3b0b-fe28-4937-8942-0eded2d9bdd4",
    "активний відпочинок":            "f4e32455-e4d3-4d95-b107-4002c4651cdb",
    "студії звукозапису":             "52d9d949-3fe1-478a-bb73-603155d126e4",
    "культурні локації":              "2f7ed976-4144-4ea4-8f5f-95337aff7ad2",
    # ── Обладнання ───────────────────────────────────────────────────────────
    "звукове обладнання":             "7e14c6f8-1ec1-4160-bbd7-400ec8f4cba1",
    "світлове обладнання":            "4f9a8d0e-5818-4fe3-8b3a-179311c761e1",
    "конструкції та сцени":           "846f3559-dfc6-4b70-9b74-b923c43558c4",
    "спецефекти":                     "89912d8e-512f-4842-a058-6a3175a3f79b",
    "декор і фотозони":               "08f41478-09cc-4b9c-8557-6f84165d0cdc",
    "проектори та екрани":            "e7ef6075-3785-482f-ab29-6f24c524a8f8",
    "меблі для заходів":              "859ee890-57a6-4607-83ce-f1f7b9ddacd3",
    "інтерактив та атракціони":       "41bc5f4e-4833-11f0-bd6d-0242ac130008",
    "прокат одягу":                   "31ac30ae-34ca-48a9-8c98-2cfbe010c7ff",
    "фото-відеообладнання":           "9ab42d8e-09d8-4a51-91a0-edb60ee3096a",
    "прокат інвентарю":               "85e25a8f-b954-4496-8f41-dbc8d8f007fe",
    "кліматичне обладнання":          "6df310b5-6677-4de3-9f93-54b6b0719ee2",
    "обладнання для конференцій":     "1b8b3aa0-50f6-418d-987f-23660ba9e6e1",
    "живлення та кабелі":             "865d659c-1511-4462-85c9-13369dd8d40a",
}

# Розділи для AI промпту
_SECTIONS = [
    ("СПЕЦІАЛІСТИ", [
        "ведучі", "музиканти", "фото та відеозйомка", "аніматори",
        "артисти та шоу", "кейтеринг та бар", "оформлення та декор",
        "організатори заходів", "візажисти та зачіски", "кондитери",
        "танцювальні шоу", "актори", "хостес", "персонал для заходів",
        "поліграфія", "оренда транспорту", "майстер-класи", "блогери", "перекладачі",
    ]),
    ("ЛОКАЦІЇ", [
        "ресторани та банкетні зали", "розважальні заклади", "готелі та комплекси",
        "квест-кімнати", "нічні клуби та караоке", "фото та відеостудії",
        "конференц-зали", "бази відпочинку", "місця для весільних церемоній",
        "івент-простори", "альтанки та бесідки", "активний відпочинок",
        "студії звукозапису", "культурні локації",
    ]),
    ("ОБЛАДНАННЯ", [
        "звукове обладнання", "світлове обладнання", "конструкції та сцени",
        "спецефекти", "декор і фотозони", "проектори та екрани",
        "меблі для заходів", "інтерактив та атракціони", "прокат одягу",
        "фото-відеообладнання", "прокат інвентарю", "кліматичне обладнання",
        "обладнання для конференцій", "живлення та кабелі",
    ]),
]


def get_categories_prompt() -> str:
    """Форматує категорії для AI системного промпту."""
    lines = []
    for section_name, cats in _SECTIONS:
        lines.append(f"\n{section_name}:")
        for cat in cats:
            lines.append(f"  - {cat}")
    return "\n".join(lines)


def names_to_uuids(names: list[str]) -> list[str]:
    """Конвертує список назв категорій → список UUID для API запиту."""
    result: list[str] = []
    for name in names:
        n = name.strip().lower()
        if n in CATEGORIES:
            result.append(CATEGORIES[n])
            continue
        # Fuzzy: шукаємо входження
        for cat_name, uuid in CATEGORIES.items():
            if n in cat_name or cat_name in n:
                if uuid not in result:
                    result.append(uuid)
                break
    return result


# ── HTTP пошук продуктів ──────────────────────────────────────────────────────

async def search_products_api(
    category_names: list[str] | None = None,
    max_price: int | None = None,
    search_text: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list["ProductResult"]:
    """
    Шукає виконавців/локації через Egolist public API.
    Повертає список ProductResult (той самий dataclass що і раніше).
    """
    from db.queries import ProductResult

    page = (offset // limit) + 1
    results: list[ProductResult] = []
    seen_ids: set = set()

    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        uuids = names_to_uuids(category_names) if category_names else []

        if uuids:
            # Шукаємо по кожній категорії окремо
            for uuid in uuids:
                params: dict = {
                    "category_id": uuid,
                    "city_slug": CITY_SLUG,
                    "page": page,
                    "per_page": limit,
                }
                if search_text:
                    params["search"] = search_text
                try:
                    resp = await client.get(f"{BASE}/products/by-subcategory", params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        items = _extract_list(data)
                        for p in _parse_products(items):
                            if p.id not in seen_ids:
                                seen_ids.add(p.id)
                                results.append(p)
                except Exception as e:
                    logger.warning(f"Egolist API by-subcategory uuid={uuid}: {e}")
        else:
            # Загальний пошук
            params = {
                "city_slug": CITY_SLUG,
                "page": page,
                "per_page": limit * 2,
            }
            if search_text:
                params["search"] = search_text
            try:
                resp = await client.get(f"{BASE}/products", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    items = _extract_list(data)
                    results = _parse_products(items)
            except Exception as e:
                logger.warning(f"Egolist API products: {e}")

    # Клієнтська фільтрація по ціні (якщо API не підтримує)
    if max_price and results:
        results = [p for p in results if p.price is None or p.price <= max_price]

    # Клієнтська фільтрація по тексту (якщо API не відфільтрував)
    if search_text and results:
        st = search_text.lower()
        filtered = [
            p for p in results
            if st in p.name.lower() or st in (p.description or "").lower()
        ]
        if filtered:
            results = filtered

    # Топ-виконавці першими
    results.sort(key=lambda p: (not p.is_top, 0))

    return results[:limit]


# ── Парсинг відповіді ─────────────────────────────────────────────────────────

def _extract_list(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "products", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


def _parse_products(items: list[dict]) -> list["ProductResult"]:
    from db.queries import ProductResult

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue

        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            continue

        # ID — UUID → стабільний int
        raw_id = item.get("id") or ""
        try:
            item_id = int(str(raw_id).replace("-", ""), 16) % 2_000_000_000
        except Exception:
            item_id = abs(hash(name)) % 2_000_000_000

        # Ціна
        price: Optional[int] = None
        for price_key in ("price", "price_from", "min_price"):
            raw = item.get(price_key)
            if raw is not None:
                try:
                    price = int(float(str(raw)))
                    break
                except Exception:
                    pass

        # Категорія
        cat = item.get("category") or {}
        cat_name = (cat.get("name") or cat.get("title") or "") if isinstance(cat, dict) else str(cat)

        # Місто
        city_obj = item.get("city") or {}
        city_name = (city_obj.get("name") or "Дніпро") if isinstance(city_obj, dict) else "Дніпро"

        # Контакти — є на рівні продукту і в об'єкті user
        user = item.get("user") or {}
        phone = _first(item.get("phone"), user.get("contractor_phone"))
        instagram = _first(item.get("instagram"), user.get("instagram"))
        telegram = _first(item.get("telegram"), user.get("telegram"))
        website = _first(item.get("website"), user.get("website"))

        # Фото — first_image це пряме посилання
        photo_url: Optional[str] = item.get("first_image") or None
        if not photo_url:
            images = item.get("images") or []
            for img in images:
                if isinstance(img, dict):
                    photo_url = img.get("feed") or img.get("view") or img.get("url")
                    if photo_url:
                        break
                elif isinstance(img, str):
                    photo_url = img
                    break

        # Посилання на профіль
        slug = item.get("slug_seo") or item.get("slug") or ""
        product_url = f"https://egolist.ua/products/{slug}" if slug else None

        is_top = bool(item.get("is_top") or item.get("is_recommended"))
        desc = (item.get("description") or "").strip()

        results.append(ProductResult(
            id=item_id,
            name=name,
            description=desc[:300],
            category=cat_name,
            city=city_name,
            price=price,
            phone=phone,
            instagram=instagram,
            website=website,
            telegram_contact=telegram,
            photo_url=photo_url,
            is_top=is_top,
            product_url=product_url,
        ))
    return results


def _first(*values) -> Optional[str]:
    """Повертає перше непусте значення зі списку."""
    for v in values:
        s = (v or "").strip()
        if s:
            return s
    return None
