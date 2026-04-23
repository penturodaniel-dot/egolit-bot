# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg
- **Admin panel**: FastAPI + Jinja2
- **AI**: OpenAI (parse intent + generate answers)
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
│   │   ├── search.py         # Free-text queries → AI parse → DB search
│   │   ├── lead.py           # Lead collection flow (3 steps: name/phone/details)
│   │   └── human.py          # Human mode (bot ↔ manager live chat)
│   ├── menu_cache.py         # 30s TTL cache for dynamic buttons
│   └── keyboards.py          # Inline keyboards (manager_choice, lead_cancel, etc.)
├── admin/
│   ├── main.py               # FastAPI admin panel
│   └── templates/
│       ├── buttons.html      # Dynamic menu button management
│       └── ...
├── db/
│   ├── connection.py         # asyncpg pool
│   ├── queries.py            # search_events(), search_karabas_events()
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults
│   ├── settings.py           # Bot settings (notification chat ID, etc.)
│   └── human_sessions.py     # Human mode session tracking
├── scrapers/
│   └── karabas.py            # Scrapes dnipro.karabas.com (9 categories)
├── ai/
│   └── parse.py              # ParsedIntent — AI parses user query
└── config.py                 # Settings from .env

## Key design decisions
- **Dynamic menu buttons** stored in DB (`menu_buttons` table), not hardcoded
- **IsDynamicButton(BaseFilter)** — only known button texts go to dynamic_menu.router; everything else falls through to search.router as free-text
- **Karabas scraper** — asyncpg requires `datetime.date`/`datetime.time` objects (NOT strings) for DATE/TIME columns
- **main_menu_keyboard()** lives in `bot/menu_cache.py` (NOT in bot/keyboards.py)
- **Ukrainian locale** on karabas.com is default — URLs are `/{slug}/` without `/ua/` prefix

## DB tables
- `egolist_events` — main events/services from Egolist site
- `karabas_events` — scraped events from karabas.com
- `menu_buttons` — dynamic bot menu buttons
- `bot_leads` — collected leads (name, phone, details)
- `bot_settings` — key/value settings (notification_chat_id, etc.)
- `human_sessions` — active human-mode sessions

## Bot button action types
- `ai_search` — runs AI search with `btn.ai_prompt`
- `submenu` — shows child buttons
- `lead_form` — starts lead collection flow
- `manager` — shows manager contact options
- `custom_query` — asks user to type free query

## Notification system
- Manager gets Telegram notification on new lead
- `notification_chat_id` configured in admin → Settings
- `notification_enabled` toggle in settings

## Railway deploy workflow
```bash
git add <files>
git commit -m "описание"
git push origin main
# Railway автоматично деплоїть
```
