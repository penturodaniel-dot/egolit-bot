import os
from fastapi import FastAPI, Request, Form, Depends, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import asyncpg
import httpx
import asyncio
import json
import logging
from datetime import datetime, timedelta

REACT_DIST = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin-react", "dist"))
REACT_INDEX = os.path.join(REACT_DIST, "index.html")
from config import settings
from db.settings import get_setting as db_get_setting, set_setting as db_set_setting, init_settings as db_init_settings
from db.content import (
    init_content_tables,
    get_all_places, get_place, create_place, update_place, delete_place, toggle_place_published,
    get_all_bot_events, get_bot_event, create_bot_event, update_bot_event, delete_bot_event, toggle_bot_event_published,
)
from db.chat import (
    init_chat_tables,
    get_all_sessions_rich,
    get_session_by_user,
    get_messages,
    get_messages_after,
    save_message,
    set_session_status,
    set_session_tag,
    mark_session_read,
    delete_session,
    get_quick_replies,
    create_quick_reply,
    delete_quick_reply,
    update_quick_reply,
)
from scrapers.egolist import scrape_all as egolist_scrape_all, init_egolist_products
from scrapers.egolist_events import scrape_all as events_scrape_all, init_egolist_events
from scrapers.seed import seed_karabas_events, seed_egolist_performers, SEED_CATEGORIES
from db.performers import (
    init_performers_table,
    get_all_performers, get_performer, create_performer, update_performer,
    delete_performer, toggle_performer_published, ALL_CATEGORIES,
)
from db.events_unified import (
    init_events_table,
    get_all_events, get_event, create_event, update_event,
    delete_event, toggle_event_published,
)
from db.menu_buttons import (
    load_all_buttons, get_button,
    create_button, update_button, toggle_button, delete_button,
    init_menu_buttons,
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="admin/templates")


def _spa():
    """Serve the React SPA index.html (built dist). Falls back to 503 if not built."""
    if os.path.exists(REACT_INDEX):
        return FileResponse(REACT_INDEX)
    return JSONResponse(
        {"error": "Frontend not built. Run: cd admin-react && npm install && npm run build"},
        status_code=503,
    )


# ── Auth ──────────────────────────────────────────────────────────────────

def require_auth(request: Request):
    """Залежність — перевіряє чи залогінений менеджер."""
    if not request.session.get("authenticated"):
        raise Exception("not_authenticated")


async def _table_exists(db, table: str) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_name = $1", table
    )
    return row is not None


async def get_db():
    return await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )


# ── Login ─────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return _spa()


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == settings.ADMIN_LOGIN and password == settings.ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ── Auth JSON API (for React SPA) ─────────────────────────────────────────

@app.post("/api/auth/login")
async def api_auth_login(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if username == settings.ADMIN_LOGIN and password == settings.ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return JSONResponse({"ok": True, "username": username})
    return JSONResponse({"error": "Невірний логін або пароль"}, status_code=401)


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    if request.session.get("authenticated"):
        return JSONResponse({"authenticated": True, "username": settings.ADMIN_LOGIN})
    return JSONResponse({"authenticated": False}, status_code=401)


@app.post("/api/auth/logout")
async def api_auth_logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})


# ── Main page ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _spa()


# ── Leads JSON API ─────────────────────────────────────────────────────────

@app.get("/api/leads")
async def api_get_leads(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    db = await get_db()
    leads = await db.fetch("""
        SELECT id, created_at, name, phone, username, details, status, manager_note,
               COALESCE(category, '') AS category,
               COALESCE(budget, '') AS budget,
               COALESCE(date_needed, '') AS date_needed,
               COALESCE(people_count, '') AS people_count
        FROM bot_leads
        ORDER BY created_at DESC
    """)
    stats = await db.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'new')      AS new_count,
            COUNT(*) FILTER (WHERE status = 'in_work')  AS in_work_count,
            COUNT(*) FILTER (WHERE status = 'done')     AS done_count,
            COUNT(*)                                     AS total_count
        FROM bot_leads
    """)
    await db.close()
    leads_list = []
    for r in leads:
        leads_list.append({
            "id": r["id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "name": r["name"],
            "phone": r["phone"],
            "username": r["username"],
            "details": r["details"],
            "status": r["status"],
            "manager_note": r["manager_note"],
            "category": r["category"],
            "budget": r["budget"],
            "event_date": r["date_needed"],   # frontend uses event_date
            "people_count": r["people_count"],
        })
    # Return plain array — Leads page computes stats itself
    return JSONResponse(leads_list)


@app.post("/human-session/{user_id}/end")
async def end_human_session(request: Request, user_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    db = await get_db()
    await db.execute("DELETE FROM human_sessions WHERE user_id = $1", user_id)
    await db.close()

    # Notify user via Telegram Bot API
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": "✅ Менеджер завершив чат. Дякуємо!\n\nЧим ще можу допомогти?",
                    "parse_mode": "HTML",
                },
            )
    except Exception:
        pass  # Non-critical — session is already deleted from DB

    return RedirectResponse("/", status_code=303)


# ── Settings ──────────────────────────────────────────────────────────────

async def _get_all_settings(db) -> dict:
    """Load all admin_settings rows into a dict."""
    base = {"notification_chat_id": "", "notification_enabled": True}
    if not await _table_exists(db, "admin_settings"):
        return base
    rows = await db.fetch("SELECT key, value FROM admin_settings")
    for r in rows:
        if r["key"] == "notification_enabled":
            base["notification_enabled"] = r["value"] == "1"
        else:
            base[r["key"]] = r["value"]
    return base


async def _upsert_setting(db, key: str, value: str) -> None:
    await db.execute("""
        INSERT INTO admin_settings (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, key, value)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, msg: str = "", msg_type: str = "info"):
    return _spa()


# ── Settings JSON API ──────────────────────────────────────────────────────

@app.get("/api/settings")
async def api_get_settings(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    db = await get_db()
    s = await _get_all_settings(db)
    await db.close()
    return JSONResponse(s)


@app.post("/api/settings")
async def api_save_settings(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
        )
    """)
    chat_id = (body.get("notification_chat_id") or "").strip()
    enabled = body.get("notification_enabled", True)
    await _upsert_setting(db, "notification_chat_id", chat_id)
    await _upsert_setting(db, "notification_enabled", "1" if enabled else "0")
    await db.close()
    return JSONResponse({"ok": True})


@app.post("/api/settings/test-notification")
async def api_test_notification(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    db = await get_db()
    s = await _get_all_settings(db)
    await db.close()
    chat_id = s.get("notification_chat_id", "")
    if not chat_id:
        return JSONResponse({"error": "Спочатку вкажи Chat ID"}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "✅ <b>Тест сповіщень</b>\n\nЦей канал налаштований для отримання заявок від Egolist бота.",
                    "parse_mode": "HTML",
                },
            )
        if resp.status_code == 200:
            return JSONResponse({"ok": True})
        detail = resp.json().get("description", "невідома помилка")
        return JSONResponse({"error": f"Помилка Telegram: {detail}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/settings")
async def settings_save(
    request: Request,
    action: str = Form(...),
    notification_chat_id: str = Form(""),
    notification_enabled: str = Form(""),   # checkbox sends "on" or nothing
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    db = await get_db()

    if action == "save_notifications":
        # Ensure table exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
            )
        """)
        await _upsert_setting(db, "notification_chat_id", notification_chat_id.strip())
        await _upsert_setting(db, "notification_enabled", "1" if notification_enabled else "0")
        await db.close()
        return RedirectResponse("/settings?msg=Збережено&msg_type=success", status_code=303)

    if action == "test_notification":
        s = await _get_all_settings(db)
        await db.close()
        chat_id = s.get("notification_chat_id", "")
        if not chat_id:
            return RedirectResponse(
                "/settings?msg=Спочатку+вкажи+Chat+ID&msg_type=error", status_code=303
            )
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "✅ <b>Тест сповіщень</b>\n\nЦей канал налаштований для отримання заявок від Egolist бота.",
                        "parse_mode": "HTML",
                    },
                )
            if resp.status_code == 200:
                return RedirectResponse(
                    "/settings?msg=Тестове+повідомлення+надіслано&msg_type=success", status_code=303
                )
            detail = resp.json().get("description", "невідома помилка")
            return RedirectResponse(
                f"/settings?msg=Помилка+Telegram:+{detail}&msg_type=error", status_code=303
            )
        except Exception as e:
            return RedirectResponse(
                f"/settings?msg=Помилка:+{e}&msg_type=error", status_code=303
            )

    await db.close()
    return RedirectResponse("/settings", status_code=303)


# ── Menu Buttons ──────────────────────────────────────────────────────────

_sched_logger = logging.getLogger("scheduler")


async def _nightly_events_loop():
    """Run Egolist events scrape every night at 00:00."""
    while True:
        try:
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=10, microsecond=0
            )
            sleep_secs = (tomorrow - now).total_seconds()
            _sched_logger.info("Next events scrape in %.1fh", sleep_secs / 3600)
            await asyncio.sleep(sleep_secs)
            _sched_logger.info("Starting nightly events scrape…")
            stats = await events_scrape_all()
            _sched_logger.info("Nightly events scrape done: %s", stats)
        except asyncio.CancelledError:
            break
        except Exception:
            _sched_logger.exception("Nightly events scrape failed")
            await asyncio.sleep(3600)


async def _nightly_egolist_loop():
    """Run Egolist performers/venues scrape every night at 01:00."""
    while True:
        try:
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(
                hour=1, minute=0, second=0, microsecond=0
            )
            sleep_secs = (tomorrow - now).total_seconds()
            _sched_logger.info("Next egolist products scrape in %.1fh", sleep_secs / 3600)
            await asyncio.sleep(sleep_secs)
            _sched_logger.info("Starting nightly egolist products scrape…")
            stats = await egolist_scrape_all()
            _sched_logger.info("Nightly egolist products scrape done: %s", stats)
        except asyncio.CancelledError:
            break
        except Exception:
            _sched_logger.exception("Nightly egolist products scrape failed")
            await asyncio.sleep(3600)


@app.on_event("startup")
async def on_startup():
    await db_init_settings()
    await init_menu_buttons()
    await init_chat_tables()
    await init_content_tables()
    await init_egolist_events()
    await init_egolist_products()
    await init_performers_table()
    await init_events_table()
    asyncio.create_task(_nightly_events_loop())
    asyncio.create_task(_nightly_egolist_loop())
    # Ensure bot_leads table exists + all columns (safe migration)
    try:
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_leads (
                id           SERIAL PRIMARY KEY,
                name         TEXT,
                phone        TEXT,
                telegram_id  TEXT,
                username     TEXT,
                details      TEXT,
                category     TEXT,
                budget       TEXT,
                date_needed  TEXT,
                people_count TEXT,
                status       TEXT NOT NULL DEFAULT 'new',
                manager_note TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        for col, coltype in [
            ("category", "TEXT"), ("budget", "TEXT"),
            ("date_needed", "TEXT"), ("people_count", "TEXT"),
            ("manager_note", "TEXT"),
        ]:
            await db.execute(f"ALTER TABLE bot_leads ADD COLUMN IF NOT EXISTS {col} {coltype}")
        await db.close()
    except Exception:
        pass


@app.get("/buttons", response_class=HTMLResponse)
async def buttons_page(request: Request, msg: str = "", msg_type: str = "info"):
    return _spa()


# ── Buttons JSON API ───────────────────────────────────────────────────────

@app.get("/api/buttons")
async def api_get_buttons(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    all_buttons = await load_all_buttons()
    def btn_to_dict(b):
        return {
            "id": b.id, "label": b.label, "emoji": b.emoji or "",
            "action_type": b.action_type, "ai_prompt": b.ai_prompt or "",
            "parent_id": b.parent_id, "position": b.position, "is_active": b.is_active,
        }
    return JSONResponse([btn_to_dict(b) for b in all_buttons])


@app.post("/api/buttons")
async def api_create_button(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "label required"}, status_code=400)
    await create_button(
        label, body.get("emoji", "").strip(), body.get("action_type", "ai_search"),
        body.get("ai_prompt", "").strip() or None,
        body.get("parent_id"), int(body.get("position", 0)),
    )
    return JSONResponse({"ok": True})


@app.put("/api/buttons/{btn_id}")
async def api_update_button(request: Request, btn_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    await update_button(
        btn_id, body.get("label", "").strip(), body.get("emoji", "").strip(),
        body.get("action_type", "ai_search"), body.get("ai_prompt", "").strip() or None,
        body.get("parent_id"), int(body.get("position", 0)),
    )
    return JSONResponse({"ok": True})


@app.post("/api/buttons/{btn_id}/toggle")
async def api_toggle_button(request: Request, btn_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await toggle_button(btn_id)
    return JSONResponse({"ok": True})


@app.delete("/api/buttons/{btn_id}")
async def api_delete_button(request: Request, btn_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await delete_button(btn_id)
    return JSONResponse({"ok": True})


@app.post("/buttons/add")
async def buttons_add(
    request: Request,
    label: str = Form(...),
    emoji: str = Form(""),
    action_type: str = Form("ai_search"),
    ai_prompt: str = Form(""),
    parent_id: str = Form(""),
    position: str = Form("0"),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    pid = int(parent_id) if parent_id.strip() else None
    pos = int(position) if position.strip().isdigit() else 0
    await create_button(label.strip(), emoji.strip(), action_type,
                        ai_prompt.strip() or None, pid, pos)
    return RedirectResponse("/buttons?msg=Кнопку+додано&msg_type=success", status_code=303)


@app.post("/buttons/{btn_id}/edit")
async def buttons_edit(
    request: Request,
    btn_id: int,
    label: str = Form(...),
    emoji: str = Form(""),
    action_type: str = Form("ai_search"),
    ai_prompt: str = Form(""),
    parent_id: str = Form(""),
    position: str = Form("0"),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    pid = int(parent_id) if parent_id.strip() else None
    pos = int(position) if position.strip().isdigit() else 0
    await update_button(btn_id, label.strip(), emoji.strip(), action_type,
                        ai_prompt.strip() or None, pid, pos)
    return RedirectResponse("/buttons?msg=Кнопку+збережено&msg_type=success", status_code=303)


@app.post("/buttons/{btn_id}/toggle")
async def buttons_toggle(request: Request, btn_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await toggle_button(btn_id)
    return RedirectResponse("/buttons", status_code=303)


@app.post("/buttons/{btn_id}/delete")
async def buttons_delete(request: Request, btn_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await delete_button(btn_id)
    return RedirectResponse("/buttons?msg=Кнопку+видалено&msg_type=success", status_code=303)


# ── Sync state (shared across all background sync jobs) ───────────────────

import time as _time

_sync_state: dict = {
    "events":  {"status": "idle", "progress": 0, "message": "", "started_at": None, "eta": None, "stats": None},
    "egolist": {"status": "idle", "progress": 0, "message": "", "started_at": None, "eta": None, "stats": None},
}


def _make_progress_cb(name: str):
    """Returns an async callback that updates _sync_state[name] with progress info."""
    async def _cb(done: int, total: int, message: str = ""):
        pct = int(done / total * 100) if total else 0
        started = _sync_state[name]["started_at"] or _time.time()
        elapsed = _time.time() - started
        eta: int | None = None
        if done > 0 and done < total:
            eta = int(elapsed / done * (total - done))
        _sync_state[name].update({"progress": pct, "message": message, "eta": eta})
    return _cb


# ── Events sync ───────────────────────────────────────────────────────────

async def _run_events_bg():
    _sync_state["events"].update({"status": "running", "progress": 0,
                                  "message": "Завантажуємо афішу…", "started_at": _time.time(),
                                  "eta": None, "stats": None})
    try:
        stats = await events_scrape_all(progress_cb=_make_progress_cb("events"))
        _sync_state["events"].update({"status": "done", "progress": 100, "eta": None,
                                      "message": f"Готово: +{stats['new']} нових, {stats['updated']} оновлено, {stats.get('total_active', 0)} активних",
                                      "stats": stats})
        _sched_logger.info("Manual events sync done: %s", stats)
    except Exception as e:
        _sync_state["events"].update({"status": "error", "message": f"Помилка: {e}", "eta": None})
        _sched_logger.exception("Manual events sync failed")


async def _run_egolist_bg():
    _sync_state["egolist"].update({"status": "running", "progress": 0,
                                   "message": "Починаємо обхід категорій…", "started_at": _time.time(),
                                   "eta": None, "stats": None})
    try:
        stats = await egolist_scrape_all(progress_cb=_make_progress_cb("egolist"))
        _sync_state["egolist"].update({"status": "done", "progress": 100, "eta": None,
                                       "message": f"Готово: +{stats['new']} нових, {stats['updated']} оновлено, {stats.get('total_active', 0)} в БД",
                                       "stats": stats})
        _sched_logger.info("Manual Egolist sync done: %s", stats)
    except Exception as e:
        _sync_state["egolist"].update({"status": "error", "message": f"Помилка: {e}", "eta": None})
        _sched_logger.exception("Manual Egolist sync failed")


@app.get("/api/sync-status")
async def api_sync_status(request: Request):
    """Returns current status of all background sync jobs."""
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return JSONResponse(_sync_state)


@app.post("/api/sync-events")
async def api_sync_events(request: Request, background_tasks: BackgroundTasks):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    background_tasks.add_task(_run_events_bg)
    return JSONResponse({"ok": True, "status": "started"})


@app.post("/api/sync-egolist")
async def api_sync_egolist(request: Request, background_tasks: BackgroundTasks):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    background_tasks.add_task(_run_egolist_bg)
    return JSONResponse({"ok": True, "status": "started"})


@app.post("/api/seed-karabas")
async def api_seed_karabas(request: Request, background_tasks: BackgroundTasks):
    """Seed up to 50 events from Karabas Dnipro → unified events table."""
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    background_tasks.add_task(_run_seed_karabas_bg)
    return JSONResponse({"ok": True, "status": "started"})


async def _run_seed_karabas_bg():
    try:
        result = await seed_karabas_events(limit=50)
        _sched_logger.info("Karabas seed done: %s", result)
    except Exception:
        _sched_logger.exception("Karabas seed failed")


# ── Egolist seed progress state ──────────────────────────────────────────────
_egolist_seed_status: dict = {
    "running": False, "current": 0, "total": 0, "current_cat": "",
    "inserted": 0, "updated": 0, "total_parsed": 0, "done": False, "error": None,
}


@app.post("/api/seed-egolist-performers")
async def api_seed_egolist_performers(request: Request, background_tasks: BackgroundTasks):
    """Seed up to 10 performers per category from Egolist API → performers table."""
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    if _egolist_seed_status.get("running"):
        return JSONResponse({"ok": False, "status": "already_running"})
    background_tasks.add_task(_run_seed_egolist_bg)
    return JSONResponse({"ok": True, "status": "started"})


@app.get("/api/seed-egolist-status")
async def api_seed_egolist_status(request: Request):
    """Return current seed progress."""
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return JSONResponse(_egolist_seed_status)


async def _run_seed_egolist_bg():
    global _egolist_seed_status
    _egolist_seed_status = {
        "running": True, "current": 0, "total": len(SEED_CATEGORIES),
        "current_cat": "", "inserted": 0, "updated": 0,
        "total_parsed": 0, "done": False, "error": None,
    }
    try:
        async def _on_progress(idx: int, total: int, cat_name: str):
            _egolist_seed_status.update({"current": idx + 1, "current_cat": cat_name})

        result = await seed_egolist_performers(per_category=10, progress_callback=_on_progress)
        _egolist_seed_status.update({
            "running": False, "done": True,
            "current": len(SEED_CATEGORIES),
            "inserted": result["inserted"],
            "updated": result["updated"],
            "total_parsed": result["total_parsed"],
        })
        _sched_logger.info("Egolist performers seed done: %s", result)
    except Exception as e:
        _egolist_seed_status.update({"running": False, "error": str(e)})
        _sched_logger.exception("Egolist performers seed failed")


@app.post("/sync-events")
async def sync_events(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    try:
        stats = await karabas_scrape_all()
        msg = (
            f"Синхронізація завершена: "
            f"+{stats['new']} нових, "
            f"{stats['updated']} оновлено, "
            f"{stats.get('total_active', '?')} активних подій"
        )
        return RedirectResponse(
            f"/buttons?msg={msg}&msg_type=success", status_code=303
        )
    except Exception as e:
        return RedirectResponse(
            f"/buttons?msg=Помилка+синхронізації:+{e}&msg_type=error",
            status_code=303,
        )


# ── AI Prompt editor ─────────────────────────────────────────────────────

@app.get("/prompt", response_class=HTMLResponse)
async def prompt_page(request: Request, msg: str = "", msg_type: str = "info"):
    return _spa()


# ── Prompt JSON API ────────────────────────────────────────────────────────

@app.get("/api/prompt")
async def api_get_prompt(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
        )
    """)
    row = await db.fetchrow("SELECT value FROM admin_settings WHERE key = 'ai_prompt_extra'")
    kw_row = await db.fetchrow("SELECT value FROM admin_settings WHERE key = 'keyword_map'")
    await db.close()
    # Also return the base prompt so admin can see it (read-only reference)
    try:
        from ai.parse import BASE_PROMPT_TEXT
        from db.categories_cache import get_categories_prompt
        base = BASE_PROMPT_TEXT.replace("{categories}", get_categories_prompt())
    except Exception:
        base = ""
    from ai.parse import DEFAULT_KEYWORD_MAP
    return JSONResponse({
        "ai_prompt_extra": row["value"] if row else "",
        "base_prompt": base,
        "keyword_map": kw_row["value"] if kw_row else DEFAULT_KEYWORD_MAP,
    })


@app.post("/api/prompt")
async def api_save_prompt(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    text = (body.get("ai_prompt_extra") or "").strip()
    kw_map = (body.get("keyword_map") or "").strip()
    db = await get_db()
    await db.execute("""
        INSERT INTO admin_settings (key, value) VALUES ('ai_prompt_extra', $1)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, text)
    if kw_map:
        await db.execute("""
            INSERT INTO admin_settings (key, value) VALUES ('keyword_map', $1)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, kw_map)
    await db.close()
    return JSONResponse({"ok": True})


# ── Image upload (local storage) ───────────────────────────────────────────

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")


def _delete_upload_files(*urls) -> None:
    """Delete local /uploads/ files by URL. Handles single URLs and JSON gallery arrays."""
    import json as _json
    for url in urls:
        if not url:
            continue
        # Handle JSON gallery array: '["http://.../a.jpg","http://.../b.jpg"]'
        if isinstance(url, str) and url.startswith('['):
            try:
                items = _json.loads(url)
                if isinstance(items, list):
                    _delete_upload_files(*items)
                    continue
            except Exception:
                pass
        # Extract filename from URL: http://host/uploads/uuid.jpg → uuid.jpg
        if isinstance(url, str) and '/uploads/' in url:
            filename = url.split('/uploads/')[-1].lstrip('/')
            filepath = os.path.join(UPLOADS_DIR, filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

@app.post("/api/upload-image")
async def api_upload_image(request: Request, file: UploadFile = File(...)):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        return JSONResponse({"error": "Файл занадто великий (макс 10MB)"}, status_code=400)
    try:
        import uuid, pathlib
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = pathlib.Path(UPLOADS_DIR) / filename
        path.write_bytes(data)
        # Build public URL from request host
        base = str(request.base_url).rstrip("/")
        url = f"{base}/uploads/{filename}"
        return JSONResponse({"url": url})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/prompt")
async def prompt_save(
    request: Request,
    ai_prompt_extra: str = Form(""),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    db = await get_db()
    await db.execute("""
        INSERT INTO admin_settings (key, value) VALUES ('ai_prompt_extra', $1)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, ai_prompt_extra.strip())
    await db.close()
    return RedirectResponse("/prompt?msg=Збережено&msg_type=success", status_code=303)


@app.post("/api/leads/{lead_id}/status")
async def api_update_lead_status(request: Request, lead_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    status = body.get("status", "new")
    note = (body.get("note") or "").strip()
    if status not in ("new", "in_work", "done"):
        return JSONResponse({"error": "invalid status"}, status_code=400)
    db = await get_db()
    await db.execute(
        "UPDATE bot_leads SET status=$1, manager_note=$2 WHERE id=$3",
        status, note, lead_id,
    )
    await db.close()
    return JSONResponse({"ok": True})


@app.post("/lead/{lead_id}/status")
async def update_status(
    request: Request,
    lead_id: int,
    status: str = Form(...),
    manager_note: str = Form(""),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    db = await get_db()
    await db.execute("""
        UPDATE bot_leads SET status = $1, manager_note = $2 WHERE id = $3
    """, status, manager_note, lead_id)
    await db.close()
    return RedirectResponse("/", status_code=303)


# ── Chats CRM ─────────────────────────────────────────────────────────────

def _session_to_dict(s: dict) -> dict:
    """Serialize session dict with datetime → ISO strings."""
    out = {}
    for k, v in s.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _msg_to_dict(m: dict) -> dict:
    """Serialize message dict with datetime → ISO strings."""
    out = {}
    for k, v in m.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@app.get("/chats", response_class=HTMLResponse)
async def chats_page(request: Request):
    return _spa()


# ── Chat JSON API ──────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def api_get_sessions(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    sessions = await get_all_sessions_rich()
    return JSONResponse([_session_to_dict(s) for s in sessions])


@app.get("/api/sessions/{session_id}/messages")
async def api_get_messages(request: Request, session_id: int, after_id: int = 0):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    if after_id > 0:
        msgs = await get_messages_after(session_id, after_id)
    else:
        msgs = await get_messages(session_id, limit=80)
    return JSONResponse([_msg_to_dict(m) for m in msgs])


@app.post("/api/sessions/{session_id}/send")
async def api_send_message(request: Request, session_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)

    # Look up user_id from session
    db = await get_db()
    row = await db.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
    await db.close()
    if not row:
        return JSONResponse({"error": "session not found"}, status_code=404)

    user_id = row["user_id"]

    # Send via Telegram Bot API
    sent_ok = False
    tg_msg_id = None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
            )
        if resp.status_code == 200:
            sent_ok = True
            tg_msg_id = resp.json().get("result", {}).get("message_id")
    except Exception as e:
        pass

    # Save to DB regardless (so admin sees what was sent)
    await save_message(
        user_id=user_id,
        direction="out",
        content=text,
        msg_type="text",
        tg_msg_id=tg_msg_id,
    )

    return JSONResponse({"ok": sent_ok, "tg_msg_id": tg_msg_id})


@app.post("/api/sessions/{session_id}/status")
async def api_set_status(request: Request, session_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    new_status = body.get("status", "ai")
    if new_status not in ("ai", "human", "closed"):
        return JSONResponse({"error": "invalid status"}, status_code=400)

    db = await get_db()
    row = await db.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
    await db.close()
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)

    user_id = row["user_id"]
    await set_session_status(user_id, new_status)

    # When returning to AI — clear human_sessions + send main menu keyboard back to user
    if new_status == "ai":
        # ── CRITICAL: remove from human_sessions so IsHumanMode filter stops intercepting ──
        try:
            db2 = await get_db()
            await db2.execute("DELETE FROM human_sessions WHERE user_id = $1", user_id)
            await db2.close()
        except Exception:
            pass

        try:
            from db.menu_buttons import load_all_buttons as _load_btns
            btns = await _load_btns()
            root = [b for b in btns if b.parent_id is None and b.is_active]
            rows = []
            for i in range(0, len(root), 2):
                row_kb = [{"text": root[i].display}]
                if i + 1 < len(root):
                    row_kb.append({"text": root[i + 1].display})
                rows.append(row_kb)
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": user_id,
                        "text": "🏠 Головне меню",
                        "reply_markup": {"keyboard": rows, "resize_keyboard": True},
                    }
                )
        except Exception:
            pass

    return JSONResponse({"ok": True})


@app.post("/api/sessions/{session_id}/tag")
async def api_set_tag(request: Request, session_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    tag = body.get("tag")  # hot | cold | vip | null
    await set_session_tag(session_id, tag)
    return JSONResponse({"ok": True})


@app.post("/api/sessions/{session_id}/read")
async def api_mark_read(request: Request, session_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await mark_session_read(session_id)
    return JSONResponse({"ok": True})


@app.delete("/api/sessions/{session_id}")
async def api_delete_session(request: Request, session_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    # Delete uploaded files attached to messages in this chat
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT media_url FROM chat_messages WHERE session_id=$1 AND media_url IS NOT NULL",
        session_id
    )
    _delete_upload_files(*[r["media_url"] for r in rows])
    await delete_session(session_id)
    return JSONResponse({"ok": True})


# ── Manager online status ──────────────────────────────────────────────────

@app.get("/api/manager-status")
async def api_manager_status_get(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    val = await db_get_setting("manager_online", "0")
    online = val == "1"
    return JSONResponse({"online": online})


@app.post("/api/manager-status")
async def api_manager_status_set(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    online = body.get("online", False)
    await db_set_setting("manager_online", "1" if online else "0")
    return JSONResponse({"ok": True, "online": online})


# ── Quick replies API ──────────────────────────────────────────────────────

@app.get("/api/quick-replies")
async def api_quick_replies(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    replies = await get_quick_replies()
    return JSONResponse(replies)


@app.post("/api/quick-replies")
async def api_create_quick_reply(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    position = int(body.get("position", 0))
    if not title or not content:
        return JSONResponse({"error": "title and content required"}, status_code=400)
    await create_quick_reply(title, content, position)
    return JSONResponse({"ok": True})


@app.delete("/api/quick-replies/{reply_id}")
async def api_delete_quick_reply(request: Request, reply_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await delete_quick_reply(reply_id)
    return JSONResponse({"ok": True})


@app.put("/api/quick-replies/{reply_id}")
async def api_update_quick_reply(request: Request, reply_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    if not title or not content:
        return JSONResponse({"error": "title and content required"}, status_code=400)
    await update_quick_reply(reply_id, title, content)
    return JSONResponse({"ok": True})


# ── Analytics ─────────────────────────────────────────────────────────────

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    return _spa()


@app.get("/api/analytics")
async def api_analytics(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    db = await get_db()

    # Total users
    total_users = await db.fetchval("SELECT COUNT(*) FROM chat_sessions") or 0

    # Active users last 7 days
    active_7d = await db.fetchval("""
        SELECT COUNT(DISTINCT user_id) FROM chat_messages
        WHERE sent_at >= NOW() - INTERVAL '7 days'
    """) or 0

    # Active users last 30 days
    active_30d = await db.fetchval("""
        SELECT COUNT(DISTINCT user_id) FROM chat_messages
        WHERE sent_at >= NOW() - INTERVAL '30 days'
    """) or 0

    # Total dialogs (sessions with at least 1 message)
    total_dialogs = await db.fetchval("""
        SELECT COUNT(DISTINCT session_id) FROM chat_messages
    """) or 0

    # Total messages in / out
    msg_in = await db.fetchval("SELECT COUNT(*) FROM chat_messages WHERE direction='in'") or 0
    msg_out = await db.fetchval("SELECT COUNT(*) FROM chat_messages WHERE direction='out'") or 0

    # Leads
    leads_total = 0
    leads_new = 0
    leads_in_work = 0
    leads_done = 0
    try:
        leads_total = await db.fetchval("SELECT COUNT(*) FROM bot_leads") or 0
        leads_new = await db.fetchval("SELECT COUNT(*) FROM bot_leads WHERE status='new'") or 0
        leads_in_work = await db.fetchval("SELECT COUNT(*) FROM bot_leads WHERE status='in_work'") or 0
        leads_done = await db.fetchval("SELECT COUNT(*) FROM bot_leads WHERE status='done'") or 0
    except Exception:
        pass

    # Handoffs (sessions that were ever in human mode)
    handoffs = await db.fetchval("""
        SELECT COUNT(*) FROM chat_sessions WHERE status = 'human'
    """) or 0

    # New users per day (last 14 days)
    daily_users = await db.fetch("""
        SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM chat_sessions
        WHERE created_at >= NOW() - INTERVAL '14 days'
        GROUP BY day ORDER BY day
    """)

    # Messages per day (last 14 days)
    daily_msgs = await db.fetch("""
        SELECT DATE(sent_at) as day, COUNT(*) as cnt
        FROM chat_messages
        WHERE sent_at >= NOW() - INTERVAL '14 days' AND direction='in'
        GROUP BY day ORDER BY day
    """)

    # New users today
    users_today = await db.fetchval("""
        SELECT COUNT(*) FROM chat_sessions WHERE DATE(created_at) = CURRENT_DATE
    """) or 0

    # Leads today
    leads_today = 0
    try:
        leads_today = await db.fetchval("""
            SELECT COUNT(*) FROM bot_leads WHERE DATE(created_at) = CURRENT_DATE
        """) or 0
    except Exception:
        pass

    # Egolist events count (afisha)
    events_count = 0
    try:
        events_count = await db.fetchval("SELECT COUNT(*) FROM egolist_events WHERE is_active=TRUE") or 0
    except Exception:
        pass

    # Egolist products count (performers/venues)
    egolist_count = 0
    try:
        egolist_count = await db.fetchval("SELECT COUNT(*) FROM egolist_products WHERE is_active=TRUE") or 0
    except Exception:
        pass

    # Leads by category
    leads_by_cat = []
    try:
        cat_rows = await db.fetch("""
            SELECT COALESCE(category, 'Інше') as category, COUNT(*) as cnt
            FROM bot_leads
            GROUP BY category ORDER BY cnt DESC LIMIT 10
        """)
        leads_by_cat = [{"category": r["category"], "count": int(r["cnt"])} for r in cat_rows]
    except Exception:
        pass

    await db.close()

    def rows_to_chart(rows):
        return {
            "labels": [str(r["day"]) for r in rows],
            "values": [int(r["cnt"]) for r in rows],
        }

    conversion = round((leads_total / total_dialogs * 100), 1) if total_dialogs > 0 else 0

    return JSONResponse({
        "users": {
            "total": int(total_users),
            "today": int(users_today),
            "active_7d": int(active_7d),
            "active_30d": int(active_30d),
        },
        "messages": {
            "in": int(msg_in),
            "out": int(msg_out),
            "total": int(msg_in + msg_out),
        },
        "dialogs": int(total_dialogs),
        "leads": {
            "total": int(leads_total),
            "today": int(leads_today),
            "new": int(leads_new),
            "in_work": int(leads_in_work),
            "done": int(leads_done),
        },
        "handoffs": int(handoffs),
        "events_active": int(events_count),
        "egolist_active": int(egolist_count),
        "conversion": conversion,
        "leads_by_category": leads_by_cat,
        "charts": {
            "daily_users": rows_to_chart(daily_users),
            "daily_msgs": rows_to_chart(daily_msgs),
        },
    })


# ── Content management ────────────────────────────────────────────────────

@app.get("/content", response_class=HTMLResponse)
async def content_page(request: Request, tab: str = "places", msg: str = "", msg_type: str = "success"):
    return _spa()


# ── Content JSON API ───────────────────────────────────────────────────────

def _serialize_record(r) -> dict:
    """Convert asyncpg Record to JSON-serializable dict."""
    out = {}
    for k in r.keys():
        v = r[k]
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat()
        elif isinstance(v, bool):
            out[k] = v
        else:
            out[k] = v
    return out


@app.get("/api/content/places")
async def api_get_places(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    places = await get_all_places()
    return JSONResponse([_serialize_record(p) for p in places])


@app.post("/api/content/places")
async def api_create_place(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "name required"}, status_code=400)
    data = {
        "name": body.get("name", "").strip(),
        "category": body.get("category", "").strip(),
        "description": body.get("description", "").strip(),
        "district": body.get("district", "").strip(),
        "address": body.get("address", "").strip(),
        "price_from": body.get("price_from") or None,
        "price_to": body.get("price_to") or None,
        "for_who": body.get("for_who", "").strip(),
        "tags": body.get("tags", "").strip(),
        "phone": body.get("phone", "").strip(),
        "instagram": body.get("instagram", "").strip(),
        "website": body.get("website", "").strip(),
        "telegram": body.get("telegram", "").strip(),
        "booking_url": body.get("booking_url", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": str(body.get("priority", "0")),
    }
    await create_place(data)
    return JSONResponse({"ok": True})


@app.put("/api/content/places/{place_id}")
async def api_update_place(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    data = {
        "name": body.get("name", "").strip(),
        "category": body.get("category", "").strip(),
        "description": body.get("description", "").strip(),
        "district": body.get("district", "").strip(),
        "address": body.get("address", "").strip(),
        "price_from": body.get("price_from") or None,
        "price_to": body.get("price_to") or None,
        "for_who": body.get("for_who", "").strip(),
        "tags": body.get("tags", "").strip(),
        "phone": body.get("phone", "").strip(),
        "instagram": body.get("instagram", "").strip(),
        "website": body.get("website", "").strip(),
        "telegram": body.get("telegram", "").strip(),
        "booking_url": body.get("booking_url", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": str(body.get("priority", "0")),
    }
    await update_place(place_id, data)
    return JSONResponse({"ok": True})


@app.delete("/api/content/places/{place_id}")
async def api_delete_place(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await delete_place(place_id)
    return JSONResponse({"ok": True})


@app.post("/api/content/places/{place_id}/toggle")
async def api_toggle_place(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await toggle_place_published(place_id)
    return JSONResponse({"ok": True})


@app.get("/api/content/events")
async def api_get_events(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    events = await get_all_bot_events()
    return JSONResponse([_serialize_record(e) for e in events])


@app.post("/api/content/events")
async def api_create_event(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    if not (body.get("title") or "").strip():
        return JSONResponse({"error": "title required"}, status_code=400)
    data = {
        "title": body.get("title", "").strip(),
        "description": body.get("description", "").strip(),
        "category": body.get("category", "").strip(),
        "date": body.get("date") or None,
        "time": body.get("time") or None,
        "price": body.get("price", "").strip(),
        "place_name": body.get("place_name", "").strip(),
        "place_address": body.get("place_address", "").strip(),
        "tags": body.get("tags", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "ticket_url": body.get("ticket_url", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": str(body.get("priority", "0")),
    }
    await create_bot_event(data)
    return JSONResponse({"ok": True})


@app.put("/api/content/events/{event_id}")
async def api_update_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    data = {
        "title": body.get("title", "").strip(),
        "description": body.get("description", "").strip(),
        "category": body.get("category", "").strip(),
        "date": body.get("date") or None,
        "time": body.get("time") or None,
        "price": body.get("price", "").strip(),
        "place_name": body.get("place_name", "").strip(),
        "place_address": body.get("place_address", "").strip(),
        "tags": body.get("tags", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "ticket_url": body.get("ticket_url", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": str(body.get("priority", "0")),
    }
    await update_bot_event(event_id, data)
    return JSONResponse({"ok": True})


@app.delete("/api/content/events/{event_id}")
async def api_delete_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await delete_bot_event(event_id)
    return JSONResponse({"ok": True})


@app.post("/api/content/events/{event_id}/toggle")
async def api_toggle_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    await toggle_bot_event_published(event_id)
    return JSONResponse({"ok": True})


# ── Performers API ────────────────────────────────────────────────────────

@app.get("/api/performers")
async def api_get_performers(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    rows = await get_all_performers()
    return JSONResponse([_serialize_record(r) for r in rows])


@app.get("/api/performers/categories")
async def api_performer_categories(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return JSONResponse(ALL_CATEGORIES)


@app.post("/api/performers")
async def api_create_performer(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "name required"}, status_code=400)
    row = await create_performer({
        "name": body.get("name", "").strip(),
        "category": body.get("category", "").strip(),
        "description": body.get("description", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "price_from": body.get("price_from") or None,
        "price_to": body.get("price_to") or None,
        "phone": body.get("phone", "").strip(),
        "instagram": body.get("instagram", "").strip(),
        "telegram": body.get("telegram", "").strip(),
        "website": body.get("website", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "tags": body.get("tags", "").strip(),
        "experience": body.get("experience", "").strip(),
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": body.get("priority", 0),
        "gallery": body.get("gallery") or None,
    })
    return JSONResponse(_serialize_record(row))


@app.put("/api/performers/{performer_id}")
async def api_update_performer(request: Request, performer_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    row = await update_performer(performer_id, {
        "name": body.get("name", "").strip(),
        "category": body.get("category", "").strip(),
        "description": body.get("description", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "price_from": body.get("price_from") or None,
        "price_to": body.get("price_to") or None,
        "phone": body.get("phone", "").strip(),
        "instagram": body.get("instagram", "").strip(),
        "telegram": body.get("telegram", "").strip(),
        "website": body.get("website", "").strip(),
        "photo_url": body.get("photo_url", "").strip(),
        "tags": body.get("tags", "").strip(),
        "experience": body.get("experience", "").strip(),
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": body.get("priority", 0),
        "gallery": body.get("gallery") or None,
    })
    return JSONResponse(_serialize_record(row))


@app.delete("/api/performers/{performer_id}")
async def api_delete_performer(request: Request, performer_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    performer = await get_performer(performer_id)
    if performer:
        _delete_upload_files(performer.get("image_url"), performer.get("gallery"))
    await delete_performer(performer_id)
    return JSONResponse({"ok": True})


@app.post("/api/performers/{performer_id}/toggle")
async def api_toggle_performer(request: Request, performer_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    new_val = await toggle_performer_published(performer_id)
    return JSONResponse({"ok": True, "is_published": new_val})


# ── Unified Events API ────────────────────────────────────────────────────

@app.get("/api/events")
async def api_get_all_events(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    rows = await get_all_events()
    return JSONResponse([_serialize_record(r) for r in rows])


@app.post("/api/events")
async def api_create_unified_event(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    if not (body.get("title") or "").strip():
        return JSONResponse({"error": "title required"}, status_code=400)
    row = await create_event({
        "source": "manual",
        "title": body.get("title", "").strip(),
        "description": body.get("description", "").strip(),
        "category": body.get("category", "").strip(),
        "date": body.get("date") or None,
        "time": body.get("time") or None,
        "price": body.get("price", "").strip(),
        "venue_name": body.get("venue_name", "").strip(),
        "venue_address": body.get("venue_address", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "image_url": body.get("image_url", "").strip(),
        "source_url": body.get("source_url", "").strip(),
        "ticket_url": body.get("ticket_url", "").strip(),
        "tags": body.get("tags", "").strip(),
        "internal_notes": body.get("internal_notes", "").strip(),
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": body.get("priority", 0),
        "gallery": body.get("gallery") or None,
    })
    return JSONResponse(_serialize_record(row))


@app.put("/api/events/{event_id}")
async def api_update_unified_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    row = await update_event(event_id, {
        "title": body.get("title", "").strip(),
        "description": body.get("description", "").strip(),
        "category": body.get("category", "").strip(),
        "date": body.get("date") or None,
        "time": body.get("time") or None,
        "price": body.get("price", "").strip(),
        "venue_name": body.get("venue_name", "").strip(),
        "venue_address": body.get("venue_address", "").strip(),
        "city": body.get("city", "Дніпро").strip() or "Дніпро",
        "image_url": body.get("image_url", "").strip(),
        "source_url": body.get("source_url", "").strip(),
        "ticket_url": body.get("ticket_url", "").strip(),
        "tags": body.get("tags", "").strip(),
        "internal_notes": body.get("internal_notes", "").strip(),
        "is_published": bool(body.get("is_published", True)),
        "is_featured": bool(body.get("is_featured", False)),
        "priority": body.get("priority", 0),
        "gallery": body.get("gallery") or None,
    })
    return JSONResponse(_serialize_record(row))


@app.delete("/api/events/{event_id}")
async def api_delete_unified_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    event = await get_event(event_id)
    if event:
        _delete_upload_files(event.get("image_url"), event.get("gallery"))
    await delete_event(event_id)
    return JSONResponse({"ok": True})


@app.post("/api/events/{event_id}/toggle")
async def api_toggle_unified_event(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    new_val = await toggle_event_published(event_id)
    return JSONResponse({"ok": True, "is_published": new_val})


# ── Places ────────────────────────────────────────────────────────────────

def _place_from_form(form: dict) -> dict:
    return {
        "name": form.get("name", "").strip(),
        "category": form.get("category", "").strip(),
        "description": form.get("description", "").strip(),
        "district": form.get("district", "").strip(),
        "address": form.get("address", "").strip(),
        "price_from": form.get("price_from", "").strip() or None,
        "price_to": form.get("price_to", "").strip() or None,
        "for_who": form.get("for_who", "").strip(),
        "tags": form.get("tags", "").strip(),
        "phone": form.get("phone", "").strip(),
        "instagram": form.get("instagram", "").strip(),
        "website": form.get("website", "").strip(),
        "telegram": form.get("telegram", "").strip(),
        "booking_url": form.get("booking_url", "").strip(),
        "photo_url": form.get("photo_url", "").strip(),
        "city": form.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": "is_published" in form,
        "is_featured": "is_featured" in form,
        "priority": form.get("priority", "0").strip() or "0",
    }


@app.post("/content/places/add")
async def place_add(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    data = _place_from_form(dict(form))
    if not data["name"]:
        return RedirectResponse("/content?tab=places&msg=Назва+обов%27язкова&msg_type=error", status_code=303)
    await create_place(data)
    return RedirectResponse("/content?tab=places&msg=Місце+додано", status_code=303)


@app.post("/content/places/{place_id}/edit")
async def place_edit(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    data = _place_from_form(dict(form))
    await update_place(place_id, data)
    return RedirectResponse("/content?tab=places&msg=Збережено", status_code=303)


@app.post("/content/places/{place_id}/toggle")
async def place_toggle(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await toggle_place_published(place_id)
    return RedirectResponse("/content?tab=places", status_code=303)


@app.post("/content/places/{place_id}/delete")
async def place_delete(request: Request, place_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await delete_place(place_id)
    return RedirectResponse("/content?tab=places&msg=Видалено", status_code=303)


# ── Bot events ────────────────────────────────────────────────────────────

def _event_from_form(form: dict) -> dict:
    return {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip() or None,
        "time": form.get("time", "").strip() or None,
        "price": form.get("price", "").strip(),
        "place_name": form.get("place_name", "").strip(),
        "place_address": form.get("place_address", "").strip(),
        "tags": form.get("tags", "").strip(),
        "photo_url": form.get("photo_url", "").strip(),
        "ticket_url": form.get("ticket_url", "").strip(),
        "city": form.get("city", "Дніпро").strip() or "Дніпро",
        "is_published": "is_published" in form,
        "is_featured": "is_featured" in form,
        "priority": form.get("priority", "0").strip() or "0",
    }


@app.post("/content/events/add")
async def event_add(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    data = _event_from_form(dict(form))
    if not data["title"]:
        return RedirectResponse("/content?tab=events&msg=Назва+обов%27язкова&msg_type=error", status_code=303)
    await create_bot_event(data)
    return RedirectResponse("/content?tab=events&msg=Подію+додано", status_code=303)


@app.post("/content/events/{event_id}/edit")
async def event_edit(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    data = _event_from_form(dict(form))
    await update_bot_event(event_id, data)
    return RedirectResponse("/content?tab=events&msg=Збережено", status_code=303)


@app.post("/content/events/{event_id}/toggle")
async def event_toggle(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await toggle_bot_event_published(event_id)
    return RedirectResponse("/content?tab=events", status_code=303)


@app.post("/content/events/{event_id}/delete")
async def event_delete(request: Request, event_id: int):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    await delete_bot_event(event_id)
    return RedirectResponse("/content?tab=events&msg=Видалено", status_code=303)


# ── React SPA static files + catch-all ───────────────────────────────────
# Mount built React assets (only if dist exists)
_assets_dir = os.path.join(REACT_DIST, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="react-assets")

# Mount uploads directory for locally stored images
_uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str, request: Request):
    """Serve React SPA index.html for any unmatched route (client-side routing)."""
    return _spa()
