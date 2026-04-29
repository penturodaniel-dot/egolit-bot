# Egolist Bot — Project Context

## Stack
- **Language**: Python 3.11
- **Bot framework**: aiogram 3
- **DB**: PostgreSQL via asyncpg
- **Admin panel**: FastAPI + React SPA (pre-built dist committed to repo)
- **AI**: Pluggable provider (OpenAI / Groq / OpenRouter) — switch via ENV.
  Default: `gpt-5-mini`. All use OpenAI-compatible `/chat/completions` API.
- **Image hosting**: Local VPS storage (`/uploads/` volume, served via FastAPI StaticFiles)
  > Cloudinary повністю видалено. `utils/cloudinary.py` — видалено. `config.py` — cloudinary-поля прибрано.

## Deployment
- **Platform**: VPS [hostpro.ua](https://hostpro.ua) — повністю мігровано з Railway
- **Repo**: https://github.com/penturodaniel-dot/egolit-bot
- **Branch**: main
- **Docker**: Python-only image (`python:3.11-slim`). No Node.js in Docker.
  React is pre-built locally and `admin-react/dist/` is committed to git.
- **DB**: PostgreSQL локально на VPS (не Railway)
- **Автозапуск**: увімкнено (`restart: unless-stopped` у docker-compose)

## Server access
| | |
|-|-|
| **IP** | `91.239.234.193` |
| **SSH** | `ssh root@91.239.234.193` |
| **Password** | `LimoN471854921596L@` |
| **Project path** | `/opt/egolist-bot` |
| **Admin panel** | http://91.239.234.193:8000 |

> ⚠️ Репо публічне — не зберігай тут продакшн-секрети (токени, паролі БД).
> Цей файл лише для локального контексту Claude.

### Корисні команди на сервері
```bash
# Переглянути логи бота
docker logs egolist_bot -f

# Переглянути логи адмін-панелі
docker logs egolist_admin -f

# Перезапустити бот
docker compose -f /opt/egolist-bot/docker-compose.yml restart bot

# Оновити після git push (rebuild + restart)
cd /opt/egolist-bot && git pull && docker compose up -d --build bot

# Оновити фронтенд (якщо змінився dist/)
cd /opt/egolist-bot && git pull && docker compose up -d --build admin

# Статус контейнерів
docker compose -f /opt/egolist-bot/docker-compose.yml ps
```

### Deploy workflow (замість Railway auto-deploy)
```bash
# 1. Локально — внести зміни, збілдити фронт якщо треба
cd admin-react && npm run build && cd ..

# 2. Закомітити і запушити
git add <files>
git commit -m "feat: ..."
git push origin main

# 3. На сервері — підтягнути і перезапустити
ssh root@91.239.234.193
cd /opt/egolist-bot && git pull && docker compose up -d --build bot
```

## Project structure
```
egolist-bot/
├── bot/
│   ├── handlers/
│   │   ├── dynamic_menu.py   # DB-driven button dispatcher (IsDynamicButton filter)
│   │   ├── search.py         # Free-text → AI parse → DB search → cards with reasons
│   │   ├── lead.py           # Lead flow: name/phone/category/budget/date/people/details
│   │   └── human.py          # Human mode + "🚪 Вийти з чату" button + chat_sessions sync
│   ├── middleware.py         # ChatPersistenceMiddleware — saves all incoming msgs to DB
│   ├── menu_cache.py         # 30s TTL cache for dynamic buttons
│   ├── keyboards.py          # Inline keyboards (results_keyboard, manager_choice_keyboard, etc.)
│   └── states.py             # FSM states: SearchFlow, LeadFlow (7 steps)
├── admin/
│   └── main.py               # FastAPI: JSON API + serves React SPA from dist/
│                             # POST /api/upload-image — зберігає файл у /app/uploads/
│                             # StaticFiles mount: /uploads → /app/uploads (публічний доступ)
├── admin-react/
│   ├── src/
│   │   ├── pages/            # Chats, Buttons, Leads, Analytics, Performers, Events, AI Промт
│   │   └── api.js            # All fetch() helpers + uploadImage(file) для фото-аплоаду
│   └── dist/                 # Pre-built production bundle (committed to git)
├── db/
│   ├── connection.py         # asyncpg pool
│   ├── queries.py            # search_products() + search_karabas_events() + search_kino_events()
│   │                         # ALL query only our CRM tables (performers + events)
│   ├── performers.py         # performers table CRUD + search_performers()
│   ├── events_unified.py     # events table CRUD + search_crm_events()
│   ├── egolist_api.py        # Legacy — kept for categories list only (not used for search)
│   ├── menu_buttons.py       # MenuButton CRUD + seed defaults + prompt migrations
│   ├── settings.py           # Key-value settings (get_setting, get_manager_online, etc.)
│   ├── human_sessions.py     # Legacy human-mode session tracking (Telegram-based)
│   ├── chat.py               # CRM: chat_sessions, chat_messages, quick_replies
│   └── content.py            # Legacy bot_places, bot_events (no longer used for search)
├── ai/
│   ├── client.py             # Provider-agnostic OpenAI-compatible client
│   ├── parse.py              # ParsedIntent — minimal base prompt + admin extra instructions
│   └── respond.py            # format_intro() + generate_match_reasons() (no hallucination)
├── scrapers/
│   └── seed.py               # seed_karabas_events() + seed_egolist_performers() — one-time data load
├── utils/
│   └── (cloudinary.py видалено — використовується локальне сховище)
└── config.py                 # Settings from .env (cloudinary-поля прибрано)
```

## DB tables
| Table | Purpose |
|-------|---------|
| `performers` | **CRM performers** — виконавці, артисти, локації, обладнання (main search table) |
| `events` | **CRM events** — unified afisha (all sources: manual, karabas, egolist, etc.) |
| `bot_menu_buttons` | Dynamic bot menu buttons |
| `bot_leads` | Collected leads (name, phone, category, budget, date, people, details) |
| `admin_settings` | Key-value: notification_chat_id, notification_enabled, manager_online, ai_prompt_extra |
| `human_sessions` | Legacy: active Telegram-based manager sessions |
| `chat_sessions` | CRM: one row per user (status: ai/human/closed, tag, unread_count) |
| `chat_messages` | CRM: full message history (direction: in/out), fields: `content`, `sent_at` |
| `quick_replies` | Admin quick-reply scripts for chat |

> **Deprecated/unused for bot search**: `egolist_events`, `egolist_products`, `bot_places`, `bot_events`
> Bot queries ONLY `performers` and `events` tables. All external API searches removed.

## performers table — key fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | text | Назва/ім'я виконавця |
| `category` | text | Категорія (ведучі, фотографи, аніматори тощо) |
| `description` | text | Опис |
| `city` | text | Місто (завжди Дніпро) |
| `price_from` | int | Ціна від (грн) |
| `price_to` | int | Ціна до (грн) |
| `phone` | text | Телефон |
| `instagram` | text | Instagram handle |
| `telegram` | text | Telegram handle |
| `website` | text | Сайт |
| `tags` | text | Теги для пошуку |
| `image_url` | text | Головне фото (URL до /uploads/...) |
| `gallery` | text | JSON-масив URL додаткових фото (до 5 шт.), напр. `["url1","url2"]` |
| `is_featured` | bool | Топ-виконавець (пріоритет у видачі) |
| `source` | text | manual / egolist (звідки додано) |

## events table — key fields
| Field | Type | Description |
|-------|------|-------------|
| `title` | text | Назва події |
| `description` | text | Опис |
| `category` | text | Категорія (концерти, кіно, театр тощо) |
| `date` | date | Дата |
| `time` | time | Час |
| `price` | text | Ціна (рядок, напр. "200–500 UAH") |
| `venue_name` | text | Назва майданчика |
| `venue_address` | text | Адреса |
| `city` | text | Місто |
| `ticket_url` | text | Посилання на квитки |
| `source_url` | text | Посилання на джерело |
| `image_url` | text | Головне фото (URL до /uploads/...) |
| `gallery` | text | JSON-масив URL додаткових фото (до 5 шт.), напр. `["url1","url2"]` |
| `is_featured` | bool | Топ-подія |
| `source` | text | manual / karabas / egolist |

## Key design decisions

### CRM-only architecture (важливо!)
- Бот працює **виключно** з нашими таблицями `performers` і `events`
- Жодних зовнішніх API при пошуку (Egolist API, gorod.dp.ua, Karabas — повністю видалено)
- `db/queries.py` → `search_products()` → `db/performers.py` → `performers` table
- `db/queries.py` → `search_karabas_events()` / `search_kino_events()` → `db/events_unified.py` → `events` table
- Дані наповнюються через адмін-панель або seed-скрипти

### Bot search flow
1. Користувач пише запит
2. `parse_intent()` → AI повертає JSON з `intent`, `category_names`, `event_category`, `search_text`, тощо
3. Routing:
   - `intent=service` → `search_products()` → шукає в `performers` по category + search_text
   - `intent=event, event_category=кіно` → `search_kino_events()` → шукає в `events` category ILIKE '%кіно%'
   - `intent=event, інше` → `search_karabas_events()` → шукає в `events` по category + search_text
   - `intent=lead` → запускає LeadFlow
   - `intent=other` → `needs_clarification=true` → відповідь з пропозицією звернутись до менеджера
4. Результати: `PAGE_SIZE=2` карток + кнопка "🔄 Ще варіанти" якщо є більше
5. При 0 результатах → `manager_choice_keyboard()` з кнопками 📝 Залишити заявку + 💬 Живий чат

### Pagination
- **`PAGE_SIZE = 2`** — константа у верхній частині `bot/handlers/search.py`
- Перший запит: fetch `PAGE_SIZE+1`, показати `PAGE_SIZE`, `has_more = fetched > PAGE_SIZE`
- "Ще варіанти": offset зсувається на `PAGE_SIZE`, та сама логіка
- Кнопка "Ще варіанти" зникає коли більше немає результатів

### AI prompt architecture
- **`BASE_PROMPT_TEXT`** (`ai/parse.py`) — мінімальний технічний контракт: тільки JSON-схема полів
- **`ai_prompt_extra`** — вся поведінкова логіка пишеться адміном через панель (AI Промт → Додаткові інструкції)
- Зберігається в `admin_settings`, підвантажується при кожному запиті (без рестарту)
- `_build_system_prompt(extra)` = BASE_PROMPT_TEXT + "\n\n" + extra

### ParsedIntent JSON fields
| Field | Values |
|-------|--------|
| `intent` | `"service"` / `"event"` / `"lead"` / `"other"` |
| `category_names` | масив рядків — назви категорій з `performers.category` |
| `event_category` | рядок з `events.category` або null |
| `date_filter` | `"today"` / `"weekend"` / `"week"` / `"month"` / null |
| `search_text` | ключове слово або ім'я (ILIKE пошук по name/title/description/tags) |
| `max_price` | число або null (фільтр по `price_from`) |
| `needs_clarification` | true / false |
| `clarification_question` | текст або null |

### match reasons — без галюцинацій
- `generate_match_reasons()` (`ai/respond.py`) — генерує пояснення чому результат підходить
- Суворе правило: спирається ТІЛЬКИ на факти з опису, заборонено "можливо/якщо/може бути"
- Якщо ім'я артиста в запиті НЕ збігається з назвою варіанту → повертає `""`
- Порожня причина → картка показується без ✅ рядка

### "Not found" flow
Коли `items = []` → одне повідомлення:
```
😔 На жаль, нічого не знайдено за твоїм запитом.
Наш менеджер зможе допомогти підібрати варіант особисто 👇
[📝 Залишити заявку]  [💬 Живий чат]
         [🏠 Головне меню]
```

### Фото-аплоад (локальне сховище)
- **Endpoint**: `POST /api/upload-image` (multipart/form-data, поле `file`)
- **Повертає**: `{ "url": "http://<host>/uploads/<uuid>.<ext>" }`
- **Зберігає** у `/app/uploads/` всередині контейнера
- **Docker volume**: `uploads_data:/app/uploads` — файли переживають рестарти
- **Публічний доступ**: FastAPI `StaticFiles` mount на `/uploads`
- **React**: `uploadImage(file)` в `api.js` — FormData + fetch, повертає `{ url }`

### Галерея (performers + events)
- Колонка `gallery TEXT` в обох таблицях (додана через `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`)
- Зберігається як JSON-рядок: `'["http://host/uploads/a.jpg","http://host/uploads/b.jpg"]'`
- React-компонент `GalleryUpload`: до 5 фото, превʼю 64×64, кнопка "+ Додати фото (N/5)", ✕ для видалення
- При збереженні форми: `gallery: JSON.stringify(data.gallery || [])`
- При завантаженні форми: `parseGallery(initial.gallery)` — розпаковує рядок або масив

### Dynamic menu buttons — важливо!
- Таблиця `bot_menu_buttons` — CRUD через адмін-панель (сторінка Кнопки)
- `_PROMPT_MIGRATIONS` у `db/menu_buttons.py` запускається на КОЖНОМУ старті (коли таблиця непуста)
  → **перезаписує ai_prompt** кнопок з оригінальними дефолтними лейблами
  → якщо змінив промпт кнопки через адмін, але лейбл залишився стандартним — зміни скинуться після рестарту
  → **Рішення**: міняти промпт треба в `_DEFAULT_BUTTONS` + `_PROMPT_MIGRATIONS` у коді, потім деплоїти
- Кнопки з часовими запитами ("вихідні", "сьогодні") **не повинні мати** назв конкретних категорій в промпті
  (інакше AI встановлює `event_category` → фільтрує тільки одну категорію → мало результатів)

### Seed data (наповнення бази)
- `scrapers/seed.py` → `seed_karabas_events(limit=50)` + `seed_egolist_performers(limit=50)`
- Запускаються через адмін-панель: Афіша → кнопка "Завантажити з Karabas", Виконавці → "Завантажити з Egolist"
- Дедуплікація по `source_url` / `name`, безпечно перезапускати
- Вставляють у `events` (source='karabas') та `performers` (source='egolist')

### Admin panel — React SPA
- Сторінки: Заявки, Чати, Виконавці, Афіша, Аналітика, Кнопки, AI Промт, Налаштування
- Вкладка "Контент" видалена
- Seed-кнопки перенесені на відповідні сторінки (Виконавці / Афіша)
- Секція "Синхронізація даних" з Аналітики видалена
- **Rebuild workflow**: `cd admin-react && npm run build` → commit `dist/` → push

### Bot
- **IsDynamicButton(BaseFilter)** — тільки відомі тексти кнопок → dynamic_menu.router; решта → search.router
- **main_menu_keyboard()** живе в `bot/menu_cache.py` (НЕ keyboards.py)
- **ChatPersistenceMiddleware** — зберігає кожне вхідне повідомлення автоматично
- **Human mode check** — якщо `chat_sessions.status == 'human'`, AI пропускає; менеджер відповідає з CRM
- **Lead flow**: name → phone → category → budget → date → people → details
- **Manager online/offline**: в `admin_settings.manager_online`

## Admin panel — JSON API (admin/main.py)
| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/login` | Login → session cookie |
| `GET /api/auth/me` | Current user |
| `POST /api/auth/logout` | Logout |
| `GET /api/sessions` | All chat sessions |
| `GET /api/sessions/{id}/messages` | Messages (polling) |
| `POST /api/sessions/{id}/send` | Send message |
| `POST /api/sessions/{id}/status` | ai / human / closed |
| `POST /api/sessions/{id}/tag` | hot / cold / vip / null |
| `POST /api/sessions/{id}/read` | Mark as read |
| `DELETE /api/sessions/{id}` | Delete session |
| `GET/POST /api/manager-status` | Online/offline toggle |
| `GET/POST/DELETE /api/quick-replies` | Quick replies CRUD |
| `GET /api/analytics` | Analytics JSON |
| `GET /api/leads` | Leads list |
| `POST /api/leads/{id}/status` | Update lead status |
| `GET/POST /api/settings` | Admin settings |
| `GET /api/prompt` | Returns `ai_prompt_extra` + `base_prompt` |
| `POST /api/prompt` | Save extra AI instructions (live) |
| `GET/POST /api/buttons` | Menu buttons |
| `PUT/DELETE /api/buttons/{id}` | Update/delete button |
| `POST /api/buttons/{id}/toggle` | Toggle active |
| `GET/POST /api/performers` | Performers CRUD |
| `PUT/DELETE /api/performers/{id}` | Update/delete performer |
| `POST /api/performers/{id}/toggle` | Toggle published |
| `GET/POST /api/events` | Events CRUD |
| `PUT/DELETE /api/events/{id}` | Update/delete event |
| `POST /api/events/{id}/toggle` | Toggle published |
| `POST /api/upload-image` | Upload photo → save to /uploads/, return URL |
| `POST /api/seed-karabas` | Seed events from Karabas (background) |
| `POST /api/seed-egolist-performers` | Seed performers from Egolist (background) |

## chat_messages field names (important!)
- Text content: **`content`** (NOT `text`)
- Timestamp: **`sent_at`** (NOT `created_at`)
- Direction: `in` (from user) / `out` (from admin/bot)
- Read status: **`is_read`** (BOOLEAN)

## AI provider system (pluggable)
- **File**: `ai/client.py`
- `AI_PROVIDER` = `openai` | `groq` | `openrouter`
- `AI_MODEL` = назва моделі
- **Auto-detects reasoning models** (gpt-5, o1/o3/o4): `reasoning_effort="minimal"` + `max_completion_tokens`
- **Regular models**: `max_tokens` + `temperature`
- **Current defaults**: `AI_PROVIDER=openai`, `AI_MODEL=gpt-5-mini`

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
AI_PROVIDER=openai
AI_MODEL=gpt-5-mini
```

## Deploy workflow (VPS hostpro.ua)

> Railway більше не використовується. Авто-деплою немає — після push треба вручну підтягнути на сервері.

```bash
# 1. Backend/bot changes — локально:
git add <files>
git commit -m "feat: description"
git push origin main

# 2. На сервері підтягнути і перезапустити:
ssh root@91.239.234.193
cd /opt/egolist-bot && git pull && docker compose up -d --build bot

# ───────────────────────────────────────────
# Frontend (React) changes — спочатку білд локально:
cd admin-react && npm run build && cd ..
git add admin-react/dist/
git commit -m "feat: description"
git push origin main

# Потім на сервері:
ssh root@91.239.234.193
cd /opt/egolist-bot && git pull && docker compose up -d --build admin
```

## Known bugs fixed
- **Бот показував gorod.dp.ua контент** — повністю видалено всі зовнішні джерела; `db/queries.py` переписано
- **"Нужны аниматоры" → афіша** — переписано AI промт з правилом: ім'я артиста = service
- **"Купити білети Ольга Цибульська" → рандомні концерти** — тепер: ім'я в запиті → завжди `intent=service` + `search_text=ім'я`
- **Галюцинації в match reasons** — доданий суворий промт: без припущень, порожній рядок якщо немає реального зв'язку
- **0 результатів показує 2 повідомлення** — тепер одне повідомлення з `manager_choice_keyboard()`
- **has_more завжди true** — виправлено: fetch PAGE_SIZE+1, `has_more = fetched > PAGE_SIZE`
- **Базовий промт не можна редагувати** — очищено до мінімального JSON-контракту; вся логіка — в полі адміна
- **"Події на вихідні" повертає 1 результат** — кнопки з часовим запитом мали категорійні слова в промпті ("концерти, вистави") → AI фільтрував по `event_category`. Виправлено: замінено на нейтральне "всі події та заходи"
- **Cloudinary залежність** — повністю видалено `utils/cloudinary.py`, config-поля, імпорти в scrapers

## ТЗ completion status
| Feature | Status |
|---------|--------|
| Free-form text + quick start buttons | ✅ |
| AI intent classification | ✅ |
| 2 recommendations per page + "show more" | ✅ |
| "Why this fits" explanation (no hallucination) | ✅ |
| Pagination (load more) | ✅ |
| Date filters (today/weekend/week/month) | ✅ |
| Artist/performer name search | ✅ |
| Lead form (7 steps) | ✅ |
| Lead → manager notification | ✅ |
| Manager online/offline | ✅ |
| Full chat history storage | ✅ |
| CRM chat admin (React SPA) | ✅ |
| AI prompt editor (admin panel) | ✅ |
| Analytics dashboard | ✅ |
| Performers management (CRUD + seed) | ✅ |
| Events/Afisha management (CRUD + seed) | ✅ |
| Dynamic menu buttons (CRUD) | ✅ |
| React admin panel (full JSON API) | ✅ |
| Not-found → manager contact buttons | ✅ |
| CRM-only architecture (no external APIs) | ✅ |
| Configurable page size (PAGE_SIZE constant) | ✅ |
| Fully editable AI prompt via admin panel | ✅ |
| Photo upload from computer (no Cloudinary) | ✅ |
| Gallery support (up to 5 photos) for performers + events | ✅ |
