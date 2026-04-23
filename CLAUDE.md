# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg + `pg_trgm` extension (fuzzy search)
- **Admin panel**: FastAPI + React SPA (pre-built dist committed to repo)
- **AI**: OpenAI gpt-4o-mini (intent parse + intro text + match reasons)
- **HTTP scraping**: httpx + BeautifulSoup4

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
│   │   ├── search.py         # Free-text → AI parse → DB search → cards with reasons
│   │   ├── lead.py           # Lead flow: name/phone/category/budget/date/people/details
│   │   └── human.py          # Human mode + chat_sessions sync
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
│   ├── queries.py            # search_products(), search_karabas_events() + pg_trgm
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults
│   ├── settings.py           # Key-value settings (get_setting, get_manager_online, etc.)
│   ├── human_sessions.py     # Legacy human-mode session tracking (Telegram-based)
│   ├── chat.py               # CRM: chat_sessions, chat_messages, quick_replies
│   └── content.py            # bot_places, bot_events CRUD + search functions
├── ai/
│   ├── parse.py              # ParsedIntent — AI parses user query; BASE_PROMPT_TEXT constant
│   └── respond.py            # format_intro() + generate_match_reasons()
├── scrapers/
│   └── karabas.py            # Scrapes dnipro.karabas.com (9 categories)
└── config.py                 # Settings from .env
```

## DB tables
| Table | Purpose |
|-------|---------|
| `products` | Egolist platform performers/venues (read-only, external) |
| `events` | Egolist platform events (read-only, external) |
| `karabas_events` | Scraped from karabas.com |
| `menu_buttons` | Dynamic bot menu buttons |
| `bot_leads` | Collected leads (name, phone, category, budget, date, people, details) |
| `admin_settings` | Key-value: notification_chat_id, notification_enabled, manager_online, ai_prompt_extra |
| `human_sessions` | Legacy: active Telegram-based manager sessions |
| `chat_sessions` | CRM: one row per user (status: ai/human/closed, tag, unread_count) |
| `chat_messages` | CRM: full message history (direction: in/out), fields: `content`, `sent_at` |
| `quick_replies` | Admin quick-reply scripts for chat |
| `bot_places` | Admin-managed venues/performers (shown in bot search) |
| `bot_events` | Admin-managed events (shown in bot search) |

## Key design decisions

### Bot
- **IsDynamicButton(BaseFilter)** — only known button texts → dynamic_menu.router; everything else → search.router
- **main_menu_keyboard()** lives in `bot/menu_cache.py` (NOT keyboards.py)
- **ChatPersistenceMiddleware** — saves every incoming message to chat_sessions + chat_messages automatically, no handler changes needed
- **Human mode check in search.py** — if `chat_sessions.status == 'human'`, AI skips; manager replies from web admin
- **Human mode dual system**: old `human_sessions` (Telegram reply-based) + new `chat_sessions` (web CRM). Both coexist
- **/start resets both human mode systems** — calls `end_human_session()` + `set_session_status(user_id, "ai")`
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

### Search — multilingual + fuzzy (3 layers)
1. **AI normalization** — GPT normalizes `search_text` to Ukrainian:
   "Оля Цыбульская" → "Оля Цибульська" (instruction in `BASE_PROMPT_TEXT`)
2. **Python transliteration fallback** — `_normalize_search()` in `ai/parse.py`
   maps: `ы→и`, `э→е`, `ё→е`, `ъ→""`
3. **pg_trgm fuzzy search** — `_ensure_trgm()` enables extension once per process;
   queries add `OR similarity(title, $N) > 0.25`; results sorted by similarity DESC.
   Graceful fallback to ILIKE-only if extension unavailable.
4. **Multi-word ILIKE** — search_text split into words (≥3 chars), OR per word,
   so "Оля Цибульська" finds events with just "Цибульська" in title.

### Karabas scraper
- `_parse_iso()` returns `datetime.date` and `datetime.time` objects (asyncpg requirement, NOT strings)
- Ukrainian locale is default — URLs are `/{slug}/` (no `/ua/` prefix)
- Trailing commas in JSON-LD fixed with `re.sub(r",\s*([}\]])", r"\1", text)`

### Spatie MediaLibrary (Egolist product photos)
- URL format: `/storage/other/{uuid[0:2]}/{uuid[2:4]}/conversions/{name}-feed.webp`
- `model_type = 'product'` (exact match, not LIKE)
- egolist.com.ua returns 401 for all pages (site behind auth) — can't link to profiles
- Contact buttons: Telegram > Instagram > Website (NO tel: links — Telegram doesn't support them)

## Admin panel routes
| Route | Description |
|-------|-------------|
| `/` | React SPA (all routes handled client-side) |
| `/sync-events` | Manual Karabas scrape trigger (POST, server-side) |

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

## chat_messages field names (important!)
- Text content field: **`content`** (NOT `text`)
- Timestamp field: **`sent_at`** (NOT `created_at`)
- Direction: `in` (from user) / `out` (from admin/bot)

## AI prompt architecture
- `BASE_PROMPT_TEXT` — module-level constant in `ai/parse.py` (extractable for admin display)
- `_build_system_prompt(extra)` — formats categories into prompt + appends admin extra instructions
- `ai_prompt_extra` — loaded from DB on every `parse_intent()` call (live without restart)
- `GET /api/prompt` returns both `base_prompt` (read-only display) and `ai_prompt_extra` (editable)

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
   - event_category, category_ids, max_price, search_text (normalized to Ukrainian), date_filter, needs_clarification
   - `needs_clarification = true` ONLY for completely meaningless input ("привіт", "?")
   - City is always Дніпро — never ask the user about it
2. DB search (karabas_events or products, merged with bot content, pg_trgm ranked)
3. `format_intro()` → 1-sentence intro text
4. `generate_match_reasons()` → list of per-result explanations (one API call)
5. Cards sent one by one with photo (fallback to text), reason shown as ✅ italic line

## Known bugs fixed
- **asyncpg date type** — `_parse_iso()` returns `datetime.date`/`datetime.time` (not strings)
- **aiogram routing** — `IsDynamicButton(BaseFilter)` prevents free-text handler eating button presses
- **Button edit modal** — `data-*` attributes + DOMContentLoaded instead of `tojson` in onclick
- **Karabas URL** — `/concerts/` not `/ua/concerts/`
- **Product photos 404** — Spatie URL pattern + `model_type = 'product'` exact match
- **egolist.com.ua 401** — replaced profile links with direct contact buttons
- **TelegramBadRequest tel: links** — phone shown as text only, no tel: in inline buttons
- **Import error** — `main_menu_keyboard` is in `bot/menu_cache.py`
- **Node.js in Dockerfile crashed Railway** — reverted to Python-only image; React dist pre-built and committed
- **Human mode stuck** — `/start` now resets both `human_sessions` and `chat_sessions.status`
- **Bot silent on errors** — `_do_search` wraps all logic in try/except, shows error message to user
- **AI asking "which city?"** — `BASE_PROMPT_TEXT` explicitly forbids city questions; stricter `needs_clarification` rules
- **Chat messages empty in CRM** — fixed `msg.text→msg.content` and `msg.created_at→msg.sent_at` in `Chats.jsx`
- **Russian search queries not finding Ukrainian results** — 3-layer normalization: AI transliteration + Python fallback + pg_trgm fuzzy

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
| Karabas scraper + sync | ✅ |
| Dynamic menu buttons (full CRUD) | ✅ |
| React admin panel (full JSON API) | ✅ |
| pg_trgm fuzzy search | ✅ |
