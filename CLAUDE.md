# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg + `pg_trgm` extension (fuzzy search for events/kino)
- **Admin panel**: FastAPI + React SPA (pre-built dist committed to repo)
- **AI**: OpenAI gpt-4o-mini (intent parse + intro text + match reasons)
- **HTTP scraping**: httpx + BeautifulSoup4
- **Product search**: Egolist public API (`api.egolist.ua`) — no DB credentials needed

## Deployment
- **Platform**: Railway
- **Repo**: https://github.com/penturodaniel-dot/egolit-bot
- **Branch**: main
- Railway auto-deploys on every push to `main`
- No manual deploy needed — just `git push origin main`
- **Docker**: Python-only image (`python:3.11-slim`). No Node.js in Docker.
  React is pre-built locally and `admin-react/dist/` is committed to git.

## Project structure
```
egolist-bot/
├── bot/
│   ├── handlers/
│   │   ├── dynamic_menu.py   # DB-driven button dispatcher (IsDynamicButton filter)
│   │   ├── search.py         # Free-text → AI parse → DB/API search → cards with reasons
│   │   ├── lead.py           # Lead flow: name/phone/category/budget/date/people/details
│   │   └── human.py          # Human mode + "🚪 Вийти з чату" button + chat_sessions sync
│   ├── middleware.py         # ChatPersistenceMiddleware — saves all incoming msgs to DB
│   ├── menu_cache.py         # 30s TTL cache for dynamic buttons
│   ├── keyboards.py          # Inline keyboards
│   └── states.py             # FSM states: SearchFlow, LeadFlow (7 steps)
├── admin/
│   └── main.py               # FastAPI: JSON API + serves React SPA from dist/
├── admin-react/
│   ├── src/
│   │   ├── pages/            # React pages: Chats, Buttons, Leads, Analytics, Content, etc.
│   │   └── api.js            # All fetch() helpers (credentials: include)
│   └── dist/                 # Pre-built production bundle (committed to git)
├── db/
│   ├── connection.py         # asyncpg pool
│   ├── queries.py            # search_products() → egolist_api; search_karabas/kino_events + pg_trgm
│   ├── egolist_api.py        # Egolist public API client (47 categories, city filter, product parse)
│   ├── categories_cache.py   # Stub — delegates to egolist_api.get_categories_prompt()
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults
│   ├── settings.py           # Key-value settings (get_setting, get_manager_online, etc.)
│   ├── human_sessions.py     # Legacy human-mode session tracking (Telegram-based)
│   ├── chat.py               # CRM: chat_sessions, chat_messages, quick_replies
│   └── content.py            # bot_places, bot_events CRUD + search functions
├── ai/
│   ├── parse.py              # ParsedIntent — AI parses user query; category_names (not IDs)
│   └── respond.py            # format_intro() + generate_match_reasons()
├── scrapers/
│   ├── karabas.py            # Scrapes dnipro.karabas.com (9 categories)
│   └── kino_teatr.py         # Scrapes api.kino-teatr.ua (Dnipro cinemas, parallel asyncio.gather)
└── config.py                 # Settings from .env
```

## DB tables
| Table | Purpose |
|-------|---------|
| `karabas_events` | Scraped from karabas.com |
| `kino_events` | Scraped from kino-teatr.ua (films showing in Dnipro cinemas) |
| `menu_buttons` | Dynamic bot menu buttons |
| `bot_leads` | Collected leads (name, phone, category, budget, date, people, details) |
| `admin_settings` | Key-value: notification_chat_id, notification_enabled, manager_online, ai_prompt_extra |
| `human_sessions` | Legacy: active Telegram-based manager sessions |
| `chat_sessions` | CRM: one row per user (status: ai/human/closed, tag, unread_count) |
| `chat_messages` | CRM: full message history (direction: in/out), fields: `content`, `sent_at` |
| `quick_replies` | Admin quick-reply scripts for chat |
| `bot_places` | Admin-managed venues/performers (shown in bot search) |
| `bot_events` | Admin-managed events (shown in bot search) |

> **Note**: `products` and `events` tables (Egolist platform DB) are NO LONGER queried directly.
> Product search now uses the public REST API at `api.egolist.ua`.

## Key design decisions

### Bot
- **IsDynamicButton(BaseFilter)** — only known button texts → dynamic_menu.router; everything else → search.router
- **main_menu_keyboard()** lives in `bot/menu_cache.py` (NOT keyboards.py)
- **ChatPersistenceMiddleware** — saves every incoming message to chat_sessions + chat_messages automatically, no handler changes needed
- **Human mode check in search.py** — if `chat_sessions.status == 'human'`, AI skips; manager replies from web admin
- **Human mode dual system**: old `human_sessions` (Telegram reply-based) + new `chat_sessions` (web CRM). Both coexist
- **/start resets both human mode systems** — calls `end_human_session()` + `set_session_status(user_id, "ai")`
- **"🚪 Вийти з чату" button** — inline keyboard shown on activation message and every `✉️ Передано менеджеру` reply; `callback_data="end_chat"` → ends session, notifies manager
- **Lead flow states**: name → phone → category (inline buttons) → budget → date → people → details (all skippable except name/phone)
- **Manager online/offline**: stored in `admin_settings.manager_online`; checked in `callback_start_chat` — if offline → redirect to lead form
- **Search error handling**: `_do_search` catches all exceptions, shows user-friendly error message instead of hanging

### Admin panel — React SPA
- FastAPI serves the pre-built React app from `admin-react/dist/`
- All non-API GET routes return `index.html` (SPA catch-all at bottom of main.py)
- Static assets served from `/assets/` via `StaticFiles`
- Session cookie auth shared between old Jinja2 routes and new JSON API
- CORS enabled for `localhost:3000` (Vite dev proxy) — production is same-origin
- **Rebuild workflow**: `cd admin-react && npm run build` → commit `dist/` → push
- **Sync endpoints use BackgroundTasks** — return immediately (avoid Railway 30s timeout); scraping runs in background

### Egolist public API (product search)
- **Base URL**: `https://api.egolist.ua/api`
- **No auth required** — fully public
- **Categories**: `GET /api/tree-categories` → 3 sections, 47 subcategories, each with UUID
- **Products by category**: `GET /api/products/by-subcategory?category_id=UUID&city_slug=dnipro&page=1&per_page=20`
- **City filter**: `city_slug` param is **ignored by the API** — client-side filter by `city.slug == "dnipro"` applied in `_parse_products()`
- **Photos**: `first_image` field is a direct URL — no Spatie URL building needed
- **Contacts**: `phone`, `instagram`, `telegram`, `website` on product + `user.contractor_phone`
- **Category mapping**: `db/egolist_api.py` → `CATEGORIES` dict: Ukrainian name → UUID
- **AI returns**: `category_names: ["ведучі", "фото та відеозйомка"]` — mapped to UUIDs in `names_to_uuids()`

### Search — multilingual + fuzzy (3 layers)
1. **AI normalization** — GPT normalizes `search_text` to Ukrainian:
   "Оля Цыбульская" → "Оля Цибульська" (instruction in `BASE_PROMPT_TEXT`)
2. **Python transliteration fallback** — `_normalize_search()` in `ai/parse.py`
   maps: `ы→и`, `э→е`, `ё→е`, `ъ→""`
3. **pg_trgm fuzzy search** — used for `karabas_events` and `kino_events` (not products — those use API)
   `_ensure_trgm()` enables extension once per process; queries add `OR similarity(title, $N) > 0.25`
4. **Multi-word ILIKE** — search_text split into words (≥3 chars), OR per word

### AI category system (IMPORTANT — changed from integer IDs)
- **Old**: AI returned `category_ids: [155, 101]` (integer IDs from Egolist PostgreSQL)
- **New**: AI returns `category_names: ["фото та відеозйомка", "музиканти"]` (strings from our list)
- `ParsedIntent.category_names: list[str]` — replaces old `category_ids: list[int]`
- FSM state key: `last_category_names` (was `last_category_ids`)
- `db/categories_cache.py` is now a stub — `load_categories()` is a no-op; prompt comes from `egolist_api.get_categories_prompt()`
- 47 categories in 3 sections: СПЕЦІАЛІСТИ / ЛОКАЦІЇ / ОБЛАДНАННЯ

### Cinema scraper (kino-teatr.ua)
- `scrapers/kino_teatr.py` — scrapes `api.kino-teatr.ua` REST API, city_id=5 (Dnipro)
- Tries multiple endpoint patterns (`/films/now-showing`, `/films`, `/schedule` by date)
- Parallel processing with `asyncio.gather` + `Semaphore(10)` — fast, no timeout
- Stores one row per film in `kino_events` (date_from/date_to range, cinema_name list)
- `event_category = "кіно"` → `search_kino_events()` in `db/queries.py`
- Nightly scheduler at 00:10 (Karabas at 00:00)
- Manual sync: `POST /api/sync-kino` → "Оновити кіно" button (purple) in Analytics

### Karabas scraper
- `_parse_iso()` returns `datetime.date` and `datetime.time` objects (asyncpg requirement, NOT strings)
- Ukrainian locale is default — URLs are `/{slug}/` (no `/ua/` prefix)
- Trailing commas in JSON-LD fixed with `re.sub(r",\s*([}\]])", r"\1", text)`
- Manual sync: `POST /api/sync-karabas` → "Оновити афіші Karabas" button (green) in Analytics

### Sync endpoints (BackgroundTasks pattern)
Both `/api/sync-karabas` and `/api/sync-kino` return **immediately** with `{"ok": true, "status": "started"}`.
The actual scraping runs in `BackgroundTasks` to avoid Railway's 30-second HTTP timeout.
The Analytics UI shows "Синхронізацію розпочато — оновиться за ~1 хв".

## Admin panel routes
| Route | Description |
|-------|-------------|
| `/` | React SPA (all routes handled client-side) |
| `/sync-events` | Manual Karabas scrape trigger (POST, legacy server-side) |

### Full JSON API (admin/main.py)
| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/login` | Login → sets session cookie |
| `GET /api/auth/me` | Current user info |
| `POST /api/auth/logout` | Clear session |
| `GET /api/sessions` | All chat sessions with unread counts |
| `GET /api/sessions/{id}/messages?after_id=N` | Messages after ID (polling) |
| `POST /api/sessions/{id}/send` | Send message via Bot API + save to DB |
| `POST /api/sessions/{id}/status` | ai / human / closed |
| `POST /api/sessions/{id}/tag` | hot / cold / vip / null |
| `POST /api/sessions/{id}/read` | Mark as read |
| `DELETE /api/sessions/{id}` | Delete chat session + all messages |
| `GET/POST /api/manager-status` | Online/offline toggle |
| `GET/POST/DELETE /api/quick-replies` | Quick reply CRUD |
| `GET /api/analytics` | Analytics data as JSON |
| `GET /api/leads` | Leads list |
| `POST /api/leads/{id}/status` | Update lead status + note |
| `GET/POST /api/settings` | Admin settings (notification_chat_id, etc.) |
| `POST /api/settings/test-notification` | Send test Telegram notification |
| `GET /api/prompt` | Returns `ai_prompt_extra` + `base_prompt` (BASE_PROMPT_TEXT) |
| `POST /api/prompt` | Save extra AI instructions (live, no restart) |
| `GET/POST /api/buttons` | Menu buttons list / create |
| `PUT/DELETE /api/buttons/{id}` | Update / delete button |
| `POST /api/buttons/{id}/toggle` | Toggle active/inactive |
| `GET/POST /api/content/places` | bot_places list / create |
| `PUT/DELETE /api/content/places/{id}` | Update / delete place |
| `POST /api/content/places/{id}/toggle` | Toggle published |
| `GET/POST /api/content/events` | bot_events list / create |
| `PUT/DELETE /api/content/events/{id}` | Update / delete event |
| `POST /api/content/events/{id}/toggle` | Toggle published |
| `POST /api/sync-karabas` | Start Karabas scrape in background |
| `POST /api/sync-kino` | Start kino-teatr.ua scrape in background |

## chat_messages field names (important!)
- Text content field: **`content`** (NOT `text`)
- Timestamp field: **`sent_at`** (NOT `created_at`)
- Direction: `in` (from user) / `out` (from admin/bot)
- Read status: **`is_read`** (BOOLEAN, default FALSE)
  - For `direction='in'`: set TRUE by `mark_session_read()` when admin opens chat
  - For `direction='out'`: set TRUE automatically in `save_message()` when client sends any new message (proxy read receipt)

## AI prompt architecture
- `BASE_PROMPT_TEXT` — module-level constant in `ai/parse.py`
- `_build_system_prompt(extra)` — formats categories into prompt + appends admin extra instructions
- `ai_prompt_extra` — loaded from DB on every `parse_intent()` call (live without restart)
- `GET /api/prompt` returns both `base_prompt` (read-only display) and `ai_prompt_extra` (editable)
- Categories prompt: generated from `db/egolist_api.get_categories_prompt()` — static dict, no DB call

## Notification system
- New lead → Telegram notification to `notification_chat_id`
- Notification includes: name, phone, username, category, budget, date, people, details
- `notification_enabled` toggle in admin Settings

## Bot lead flow (7 steps)
1. Name
2. Phone / Telegram username
3. Category — inline buttons: День народження / Корпоратив / Побачення / Захід / Виконавець / Питання / Інше
4. Budget (skippable)
5. Date (skippable)
6. People count (skippable)
7. Details / description (skippable)

## CRM Chat system
- Session list (left) / messages (center) / client info + quick replies (right)
- Manager online/offline toggle (stored in admin_settings)
- When offline → bot shows "офлайн" message + redirects to lead form
- When online → "Живий чат" button starts human mode
- Admin sends message → Bot API → saved to DB
- Real-time updates: polls `/api/sessions/{id}/messages?after_id=N` every 2s
- Browser notifications + sound alert on new unread messages
- Tags: hot/cold/vip per session
- Quick replies: saved scripts, one-click insert into input
- **Read receipts**: `✓` (grey) = sent to Telegram; `✓✓` (blue) = client read (is_read=TRUE)
- **No optimistic updates**: send fetches real message immediately after API responds (prevents duplicates)
- **Bubble layout**: `.bubble-wrap { flex:1; min-width:0; max-width:68% }` wraps bubble+meta

## Content management
- **bot_places**: own venues/performers searchable by bot
  - Fields: name, category, description, district, address, price_from/to, for_who, tags, phone, instagram, telegram, website, booking_url, photo_url, city, is_published, is_featured, priority
- **bot_events**: own events searchable by bot
  - Fields: title, description, category, date, time, price, place_name, place_address, tags, photo_url, ticket_url, city, is_published, is_featured, priority
- `is_featured = TRUE` → appears first in bot search results
- `priority` (0–100) → sort order within bot results

## AI flow
1. `parse_intent(user_text, history)` → `ParsedIntent`
   - intent: service | event | lead | other
   - `category_names` (list of strings), `event_category`, `max_price`, `search_text`, `date_filter`, `needs_clarification`
   - `needs_clarification = true` ONLY for completely meaningless input ("привіт", "?")
   - City is always Дніпро — never ask the user about it
2. Search routing:
   - `intent=service` → `search_products()` → Egolist API + bot_places
   - `intent=event, event_category="кіно"` → `search_kino_events()` → kino_events table
   - `intent=event, other` → `search_karabas_events()` → karabas_events table + bot_events
3. `format_intro()` → 1-sentence intro text
4. `generate_match_reasons()` → list of per-result explanations (one API call)
5. Cards sent one by one with photo (fallback to text), reason shown as ✅ italic line

## Known bugs fixed
- **asyncpg date type** — `_parse_iso()` returns `datetime.date`/`datetime.time` (not strings)
- **aiogram routing** — `IsDynamicButton(BaseFilter)` prevents free-text handler eating button presses
- **Karabas URL** — `/concerts/` not `/ua/concerts/`
- **TelegramBadRequest tel: links** — phone shown as text only, no tel: in inline buttons
- **Import error** — `main_menu_keyboard` is in `bot/menu_cache.py`
- **Node.js in Dockerfile crashed Railway** — reverted to Python-only image; React dist pre-built and committed
- **Human mode stuck** — `/start` now resets both `human_sessions` and `chat_sessions.status`
- **Bot silent on errors** — `_do_search` wraps all logic in try/except, shows error message to user
- **AI asking "which city?"** — `BASE_PROMPT_TEXT` explicitly forbids city questions
- **Chat messages empty in CRM** — fixed `msg.text→msg.content` and `msg.created_at→msg.sent_at` in `Chats.jsx`
- **Russian search queries** — 3-layer normalization: AI transliteration + Python fallback + pg_trgm fuzzy
- **Chat bubble text on separate lines** — `.bubble-wrap` flex wrapper with `max-width:68%`
- **Sent messages duplicated in chat** — removed optimistic update; fetch real message immediately after send
- **✓✓ shown immediately** — now conditional on `msg.is_read` from DB
- **Double /api in sync URLs** — `syncKarabas`/`syncKino` in api.js used `/api/sync-*` but BASE already `/api`; fixed to `/sync-*`
- **502 timeout on sync** — scrape runs in FastAPI `BackgroundTasks`; endpoint returns instantly
- **Products from other cities (Vinnytsia)** — `city_slug` param ignored by API; client-side filter `city.slug == "dnipro"` added in `_parse_products()`
- **Human mode no exit button** — `END_CHAT_KB` inline button on every human-mode message; `callback_data="end_chat"` handler ends session

## Railway deploy workflow
```bash
# Bot/backend changes:
git add <files>
git commit -m "feat: description"
git push origin main

# Frontend (React) changes — must rebuild first:
cd admin-react && npm run build && cd ..
git add admin-react/dist/
git commit -m "feat: description"
git push origin main
```

## ТЗ completion status
| Feature | Status |
|---------|--------|
| Free-form text + quick start buttons | ✅ |
| AI intent classification + clarification | ✅ |
| 3–5 recommendations with photos | ✅ |
| "Why this fits" explanation per card | ✅ |
| More results (pagination) | ✅ |
| Date filters (today/weekend/week/month) | ✅ |
| Artist/performer name search (multilingual + fuzzy) | ✅ |
| Lead form (7 steps with skip) | ✅ |
| Lead → manager notification | ✅ |
| Manager online/offline in bot | ✅ |
| Full chat history storage | ✅ |
| CRM chat admin (React SPA) | ✅ |
| AI prompt editor | ✅ |
| Analytics dashboard | ✅ |
| Content management | ✅ |
| Karabas scraper + nightly sync | ✅ |
| Cinema scraper (kino-teatr.ua) + nightly sync | ✅ |
| Egolist public API for product search | ✅ |
| Dynamic menu buttons (full CRUD) | ✅ |
| React admin panel (full JSON API) | ✅ |
| pg_trgm fuzzy search (events/kino) | ✅ |
| Exit chat button in human mode | ✅ |
| City filter for product search (Dnipro only) | ✅ |
