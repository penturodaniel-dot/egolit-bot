# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg
- **Admin panel**: FastAPI + Jinja2 (separate service)
- **AI**: OpenAI gpt-4o-mini (intent parse + intro text + match reasons)
- **HTTP scraping**: httpx + BeautifulSoup4

## Deployment
- **Platform**: Railway
- **Repo**: https://github.com/penturodaniel-dot/egolit-bot
- **Branch**: main
- Railway auto-deploys on every push to `main`
- No manual deploy needed — just `git push origin main`

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
│   ├── main.py               # FastAPI admin: all routes + JSON API
│   └── templates/
│       ├── index.html        # Dashboard — leads list
│       ├── buttons.html      # Dynamic menu button management
│       ├── settings.html     # Notification settings
│       ├── prompt.html       # AI prompt extra instructions editor
│       ├── chats.html        # CRM online chat (Binotel-like)
│       ├── analytics.html    # Analytics dashboard
│       └── content.html      # Content management (places + events)
├── db/
│   ├── connection.py         # asyncpg pool
│   ├── queries.py            # search_products(), search_karabas_events() — merge bot content
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults
│   ├── settings.py           # Key-value settings (get_setting, get_manager_online, etc.)
│   ├── human_sessions.py     # Legacy human-mode session tracking (Telegram-based)
│   ├── chat.py               # CRM: chat_sessions, chat_messages, quick_replies
│   └── content.py            # bot_places, bot_events CRUD + search functions
├── ai/
│   ├── parse.py              # ParsedIntent — AI parses user query
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
| `chat_messages` | CRM: full message history (direction: in/out) |
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
- **Lead flow states**: name → phone → category (inline buttons) → budget → date → people → details (all skippable except name/phone)
- **Manager online/offline**: stored in `admin_settings.manager_online`; checked in `callback_start_chat` — if offline → redirect to lead form

### Search
- **search_products()** merges `bot_places` at end (featured bot_places shown first)
- **search_karabas_events()** merges `bot_events` (featured shown first)
- **bot_places/bot_events** have `priority` (0–100) and `is_featured` fields
- **AI match reasons**: `generate_match_reasons()` — one API call for all results → returns list of 1-sentence explanations shown as `✅ <i>reason</i>` in each card

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
| `/` | Dashboard — leads list with status management |
| `/buttons` | Dynamic menu buttons (tree, add/edit/toggle/delete) |
| `/sync-events` | Manual Karabas scrape trigger |
| `/settings` | Notification chat ID, enable/disable |
| `/prompt` | AI extra instructions editor (live, no restart) |
| `/chats` | CRM chat UI — real-time (2s polling), send messages, quick replies |
| `/analytics` | Users/messages/leads/handoffs dashboard + bar charts |
| `/content` | Manage bot_places and bot_events (add/edit/toggle/delete/featured) |

### Admin JSON API (used by /chats)
- `GET /api/sessions` — all chat sessions with unread counts
- `GET /api/sessions/{id}/messages?after_id=N` — messages after ID (for polling)
- `POST /api/sessions/{id}/send` — send message via Bot API + save to DB
- `POST /api/sessions/{id}/status` — ai/human/closed
- `POST /api/sessions/{id}/tag` — hot/cold/vip/null
- `POST /api/sessions/{id}/read` — mark as read
- `GET/POST /api/manager-status` — online/offline toggle
- `GET/POST/DELETE/PUT /api/quick-replies` — quick reply CRUD
- `GET /api/analytics` — all analytics data as JSON

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
- `/chats` page: session list (left), messages (center), client info + quick replies (right)
- Manager online/offline toggle in header (stored in admin_settings)
- When offline → bot shows "офлайн" message + redirects to lead form
- When online → "Живий чат" button starts human mode
- Admin sends message → Bot API → saved to DB
- Real-time updates: JS polls `/api/sessions/{id}/messages?after_id=N` every 2s
- Browser notifications + sound alert on new unread messages
- Tags: hot/cold/vip per session
- Quick replies: saved scripts, one-click insert into input

## Content management (/content)
- **bot_places**: own venues/performers searchable by bot
  - Fields: name, category, description, district, address, price_from/to, for_who, tags, phone, instagram, telegram, website, booking_url, photo_url, city, is_published, is_featured, priority
- **bot_events**: own events searchable by bot
  - Fields: title, description, category, date, time, price, place_name, place_address, tags, photo_url, ticket_url, city, is_published, is_featured, priority
- `is_featured = TRUE` → appears first in bot search results
- `priority` (0–100) → sort order within bot results

## AI flow
1. `parse_intent(user_text, history)` → `ParsedIntent`
   - intent: service | event | lead
   - event_category, category_ids, max_price, search_text, date_filter, needs_clarification
   - Loads `ai_prompt_extra` from DB on every call (live without restart)
2. DB search (karabas_events or products, merged with bot content)
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

## Railway deploy workflow
```bash
git add <files>
git commit -m "feat: description"
git push origin main
# Railway auto-deploys both bot and admin services
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
| Artist/performer name search | ✅ |
| Lead form (7 steps with skip) | ✅ |
| Lead → manager notification | ✅ |
| Manager online/offline in bot | ✅ |
| Full chat history storage | ✅ |
| CRM chat admin (/chats) | ✅ |
| AI prompt editor (/prompt) | ✅ |
| Analytics dashboard (/analytics) | ✅ |
| Content management (/content) | ✅ |
| Karabas scraper + sync | ✅ |
| Dynamic menu buttons | ✅ |
