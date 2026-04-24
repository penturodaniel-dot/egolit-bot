# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg + `pg_trgm` extension (fuzzy search for events)
- **Admin panel**: FastAPI + React SPA (pre-built dist committed to repo)
- **AI**: OpenAI gpt-4o-mini (intent parse + intro text + match reasons)
- **HTTP scraping**: httpx + BeautifulSoup4
- **Product & events search**: Egolist public API (`api.egolist.ua`) — no DB credentials needed
- **Image hosting**: Cloudinary (folder `egolist-events/`) — for event photos

## Deployment
- **Platform**: Railway
- **Repo**: https://github.com/penturodaniel-dot/egolit-bot
- **Branch**: main
- Railway auto-deploys on every push to `main`
- No manual deploy needed — just `git push origin main`
- **Docker**: Python-only image (`python:3.11-slim`). No Node.js in Docker.
  React is pre-built locally and `admin-react/dist/` is committed to git.
- **DB**: Railway-managed PostgreSQL (`nozomi.proxy.rlwy.net:33189/railway`)

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
│   ├── queries.py            # search_products() + _search_egolist_events() + pg_trgm
│   ├── egolist_api.py        # Egolist public API client (47 categories, city filter)
│   ├── categories_cache.py   # Stub — delegates to egolist_api.get_categories_prompt()
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults + prompt migrations
│   ├── settings.py           # Key-value settings (get_setting, get_manager_online, etc.)
│   ├── human_sessions.py     # Legacy human-mode session tracking (Telegram-based)
│   ├── chat.py               # CRM: chat_sessions, chat_messages, quick_replies
│   └── content.py            # bot_places, bot_events CRUD + search functions
├── ai/
│   ├── parse.py              # ParsedIntent — AI parses user query; category_names (not IDs)
│   └── respond.py            # format_intro() + generate_match_reasons()
├── scrapers/
│   ├── egolist.py            # Egolist products sync → egolist_products table
│   └── egolist_events.py     # Egolist events API → egolist_events table (+Cloudinary upload)
├── utils/
│   └── cloudinary.py         # Cloudinary upload helper (pass URL, Cloudinary fetches)
└── config.py                 # Settings from .env
```

## DB tables
| Table | Purpose |
|-------|---------|
| `egolist_events` | Scraped from api.egolist.ua/api/events (all Dnipro events, 6 categories) |
| `egolist_products` | Scraped from Egolist API (performers/venues) |
| `menu_buttons` | Dynamic bot menu buttons |
| `bot_leads` | Collected leads (name, phone, category, budget, date, people, details) |
| `admin_settings` | Key-value: notification_chat_id, notification_enabled, manager_online, ai_prompt_extra |
| `human_sessions` | Legacy: active Telegram-based manager sessions |
| `chat_sessions` | CRM: one row per user (status: ai/human/closed, tag, unread_count) |
| `chat_messages` | CRM: full message history (direction: in/out), fields: `content`, `sent_at` |
| `quick_replies` | Admin quick-reply scripts for chat |
| `bot_places` | Admin-managed venues/performers (shown in bot search) |
| `bot_events` | Admin-managed events (shown in bot search) |

> **Deprecated tables (removed)**: `karabas_events`, `kino_events` — replaced by unified `egolist_events`

## Key design decisions

### Bot
- **IsDynamicButton(BaseFilter)** — only known button texts → dynamic_menu.router; everything else → search.router
- **main_menu_keyboard()** lives in `bot/menu_cache.py` (NOT keyboards.py)
- **ChatPersistenceMiddleware** — saves every incoming message to chat_sessions + chat_messages automatically
- **Human mode check in search.py** — if `chat_sessions.status == 'human'`, AI skips; manager replies from web admin
- **Human mode dual system**: old `human_sessions` (Telegram reply-based) + new `chat_sessions` (web CRM)
- **/start resets both human mode systems** — `end_human_session()` + `set_session_status(user_id, "ai")`
- **"🚪 Вийти з чату" button** — inline keyboard on every human-mode message
- **Lead flow states**: name → phone → category (inline buttons) → budget → date → people → details
- **Manager online/offline**: stored in `admin_settings.manager_online`; checked before starting chat
- **Search error handling**: `_do_search` catches all exceptions, shows user-friendly error
- **Card buttons**: events get "🔗 Детальніше" linking to source_url; products get "🔗 Детальніше" linking to `egolist.ua/products/{slug}`

### Admin panel — React SPA
- FastAPI serves pre-built React app from `admin-react/dist/`
- All non-API GET routes return `index.html` (SPA catch-all at bottom of main.py)
- Static assets served from `/assets/` via `StaticFiles`
- Session cookie auth shared between old Jinja2 routes and new JSON API
- **Rebuild workflow**: `cd admin-react && npm run build` → commit `dist/` → push
- **Sync endpoints use BackgroundTasks** — return immediately (avoid Railway 30s timeout)
- **Sync progress UI** — Analytics polls `/api/sync-status` every 1.5s for live progress bars

### Egolist public API (product search)
- **Base URL**: `https://api.egolist.ua/api`
- **No auth required** — fully public
- **Categories**: `GET /api/tree-categories` → 3 sections, 47 subcategories, each with UUID
- **Products**: `GET /api/products/by-subcategory?category_id=UUID&city_slug=dnipro&page=1`
- **City filter**: `city_slug` param is **ignored** for products — client-side filter by `city.slug == "dnipro"`
- **Photos**: `first_image` field is a direct URL on egolist.ua servers (works from anywhere)
- **Contacts**: `phone`, `instagram`, `telegram`, `website` on product + `user.contractor_phone`
- **Category mapping**: `db/egolist_api.py` → `CATEGORIES` dict: Ukrainian name → UUID
- **AI returns**: `category_names: ["ведучі", "фото та відеозйомка"]` — mapped to UUIDs

### Egolist Events API (consolidated afisha)
- **Base URL**: `https://api.egolist.ua/api/events?city_slug=dnipro&per_page=50&page=N`
- **City filter**: `city_slug` **works** for events (unlike products) — server-side filter
- **6 event types** via slug:
  - `koncerti` → концерти
  - `vistavi` → виставки
  - `kino` → кіно
  - `dlia-ditei` → для дітей
  - `aktivnii-vidpocinok` → активний відпочинок
  - `maister-klasi` → майстер-класи
- **~248 active Dnipro events**
- **Images**: `image_links[0]` array — URLs from `gorod.dp.ua` (see "Known issues" below)
- **Date format**: DD.MM.YYYY in API → parsed to PostgreSQL DATE
- **Source URL**: `source_url` field → links to gorod.dp.ua event page
- Replaces both old Karabas scraper AND kino-teatr scraper — one unified source

### Cloudinary integration (event images)
- **Credentials**: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` in `.env`
- **Folder**: `egolist-events/` — one image per event with `public_id = event_{api_id}`
- **Strategy**: pass source URL to Cloudinary upload API as `file` parameter → Cloudinary fetches itself
  (avoids downloading on Railway, which saves bandwidth)
- **DB column**: `egolist_events.cloudinary_url` — populated on first scrape
- **Bot logic**: `_send_event_card` uses `URLInputFile` for Cloudinary URLs (no httpx download needed)
- **Fallback**: if `cloudinary_url` is NULL → falls back to `image_url` (raw gorod.dp.ua)
- **Code**: `utils/cloudinary.py` — signature via SHA-1, no SDK needed

### Search — multilingual + fuzzy (3 layers)
1. **AI normalization** — GPT normalizes `search_text` to Ukrainian
   ("Оля Цыбульская" → "Оля Цибульська")
2. **Python transliteration fallback** — `_normalize_search()` in `ai/parse.py`
   maps: `ы→и`, `э→е`, `ё→е`, `ъ→""`
3. **pg_trgm fuzzy search** — used for `egolist_events`
   `_ensure_trgm()` enables extension; queries add `OR similarity(title, $N) > 0.25`
4. **Multi-word ILIKE** — search_text split into words (≥3 chars), OR per word

### AI category system
- AI returns `category_names: ["фото та відеозйомка", "музиканти"]` (strings)
- `ParsedIntent.category_names: list[str]`
- FSM state key: `last_category_names`
- `event_category`: `"концерти"|"виставки"|"кіно"|"для дітей"|"активний відпочинок"|"майстер-класи"|null`
- `_CATEGORY_TO_SLUG` dict in `queries.py` maps event_category → egolist event_slug

### Sync endpoints (BackgroundTasks pattern)
- `POST /api/sync-events` — scrape afisha (egolist_events)
- `POST /api/sync-egolist` — scrape products (egolist_products)
- Both return **immediately** with `{"ok": true, "status": "started"}`
- Actual scraping runs in `BackgroundTasks` to avoid Railway's 30s HTTP timeout
- Progress tracked in global `_sync_state` dict; polled via `/api/sync-status`
- Nightly schedulers: events at 00:00, products at 01:00

## Admin panel routes
| Route | Description |
|-------|-------------|
| `/` | React SPA (all routes handled client-side) |

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
| `GET/POST /api/settings` | Admin settings |
| `POST /api/settings/test-notification` | Send test Telegram notification |
| `GET /api/prompt` | Returns `ai_prompt_extra` + `base_prompt` |
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
| `POST /api/sync-events` | Start Egolist events (afisha) scrape in background |
| `POST /api/sync-egolist` | Start Egolist products scrape in background |
| `GET /api/sync-status` | Live progress of both sync jobs |

## chat_messages field names (important!)
- Text content field: **`content`** (NOT `text`)
- Timestamp field: **`sent_at`** (NOT `created_at`)
- Direction: `in` (from user) / `out` (from admin/bot)
- Read status: **`is_read`** (BOOLEAN, default FALSE)

## AI prompt architecture
- `BASE_PROMPT_TEXT` — module-level constant in `ai/parse.py`
- `_build_system_prompt(extra)` — formats categories + appends admin extra instructions
- `ai_prompt_extra` — loaded from DB on every `parse_intent()` call (live without restart)
- Categories prompt from `db/egolist_api.get_categories_prompt()` — static dict
- Button prompts in `db/menu_buttons.py` → `_DEFAULT_BUTTONS` + `_PROMPT_MIGRATIONS`
  (migrations auto-fix stale prompts in existing DBs)

## AI flow
1. `parse_intent(user_text, history)` → `ParsedIntent`
   - intent: service | event | lead | other
   - `category_names` (list), `event_category`, `max_price`, `search_text`, `date_filter`
   - City is always Дніпро — never ask the user
2. Search routing:
   - `intent=service` → `search_products()` → egolist_products table + bot_places
   - `intent=event` → `_search_egolist_events()` → egolist_events table + bot_events
3. `format_intro()` → 1-sentence intro text
4. `generate_match_reasons()` → per-result explanations (one API call)
5. Cards sent one by one with photo, reason shown as ✅ italic line

## Known issues

### gorod.dp.ua geo-blocking
`gorod.dp.ua` (the source of event images via `image_links`) **blocks all non-Ukrainian IPs**
with HTTP 403. Confirmed blocked:
- ❌ Railway (US/EU servers)
- ❌ Cloudinary fetch API (global CDN)
- ❌ weserv.nl, statically.io, photon (image proxies)
- ❌ corsproxy.io, allorigins (CORS proxies)
- ✅ Only Ukrainian-resident IPs work

**Consequence**: `cloudinary_url` stays NULL because Cloudinary can't fetch the images.
Bot falls back to `image_url` but Telegram's fetch also fails → event cards sent as text only.

**Workarounds** (pick one):
1. **Ukrainian HTTP proxy** — configure `httpx.AsyncClient(proxy=...)` in `utils/cloudinary.py`
   with a Ukrainian proxy service (proxy6.net, smartproxy, ~$3-5/mo)
2. **Local sync** — run `scrapers/egolist_events.py` from a Ukrainian-resident machine;
   it uploads to Cloudinary and writes `cloudinary_url` to the shared Railway DB
3. **Skip event photos** — remove photo logic for events, show text-only cards

## Known bugs fixed
- **asyncpg date type** — parse to `datetime.date`/`datetime.time` (not strings)
- **aiogram routing** — `IsDynamicButton(BaseFilter)` prevents free-text eating button presses
- **TelegramBadRequest tel: links** — phone shown as text only, no tel: in inline buttons
- **Import error** — `main_menu_keyboard` is in `bot/menu_cache.py`
- **Node.js in Dockerfile** — reverted to Python-only; React dist pre-built and committed
- **Human mode stuck** — `/start` resets both `human_sessions` and `chat_sessions.status`
- **Bot silent on errors** — `_do_search` wraps all logic in try/except
- **AI asking "which city?"** — `BASE_PROMPT_TEXT` explicitly forbids city questions
- **Chat messages empty in CRM** — fixed `msg.text→msg.content`, `msg.created_at→msg.sent_at`
- **Russian search queries** — 3-layer normalization (AI + Python + pg_trgm)
- **Sent messages duplicated** — removed optimistic update; fetch real message after send
- **Double /api in sync URLs** — api.js BASE already has `/api`; paths use `/sync-*`
- **502 timeout on sync** — scrape runs in FastAPI `BackgroundTasks`
- **Products from other cities** — client-side filter `city.slug == "dnipro"` in `_parse_products`
- **Human mode no exit** — `END_CHAT_KB` inline button, `callback_data="end_chat"`
- **Wrong AI routing for menu buttons** — button prompts now explicitly mention event/concert/show
- **bot_leads table missing** — was never created, only `ALTER TABLE` calls; added `CREATE TABLE IF NOT EXISTS` in both `lead.py` and `admin/main.py` startup
- **Undefined `_egolist_logger`** — renamed to unified `_sched_logger` during karabas/kino consolidation
- **Event photos blocked** — added httpx download with Referer header; then Cloudinary integration
  (but gorod.dp.ua still blocks non-UA IPs — see "Known issues")
- **Karabas + kino scrapers removed** — consolidated into single `egolist_events` scraper using
  Egolist's own event API (6 categories, city_slug works server-side)

## Environment variables (.env)
```
BOT_TOKEN=...
OPENAI_API_KEY=...
DB_HOST=nozomi.proxy.rlwy.net
DB_PORT=33189
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=...
ADMIN_LOGIN=admin
ADMIN_PASSWORD=...
MANAGER_TELEGRAM_ID=0
CLOUDINARY_CLOUD_NAME=dqwsfvuon
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

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
| 3–5 recommendations with photos | ✅ (events photos need UA proxy) |
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
| Analytics dashboard (with live sync progress) | ✅ |
| Content management | ✅ |
| Egolist events scraper (unified afisha) | ✅ |
| Egolist products scraper | ✅ |
| Cloudinary integration for event photos | ✅ (blocked by gorod.dp.ua geo-restriction) |
| Dynamic menu buttons (full CRUD) | ✅ |
| React admin panel (full JSON API) | ✅ |
| pg_trgm fuzzy search (events) | ✅ |
| Exit chat button in human mode | ✅ |
| City filter for product search (Dnipro only) | ✅ |
| "🔗 Детальніше" button on all cards | ✅ |
