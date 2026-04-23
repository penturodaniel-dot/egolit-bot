from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import asyncpg
import httpx
import asyncio
import json
from datetime import datetime
from config import settings
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
    get_quick_replies,
    create_quick_reply,
    delete_quick_reply,
    update_quick_reply,
)
from scrapers.karabas import scrape_all as karabas_scrape_all
from db.menu_buttons import (
    load_all_buttons, get_button,
    create_button, update_button, toggle_button, delete_button,
    init_menu_buttons,
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SECRET_KEY)
templates = Jinja2Templates(directory="admin/templates")


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
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
    })


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


# ── Main page ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    db = await get_db()

    leads = await db.fetch("""
        SELECT id, created_at, name, phone, username, details, status, manager_note
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

    human_sessions = await db.fetch("""
        SELECT user_id, username, first_name, started_at
        FROM human_sessions
        ORDER BY started_at DESC
    """) if await _table_exists(db, "human_sessions") else []

    await db.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "leads": leads,
        "stats": stats,
        "human_sessions": human_sessions,
    })


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
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    db = await get_db()
    s = await _get_all_settings(db)
    await db.close()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": s,
        "msg": msg,
        "msg_type": msg_type,
    })


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

@app.on_event("startup")
async def on_startup():
    await init_menu_buttons()
    await init_chat_tables()


@app.get("/buttons", response_class=HTMLResponse)
async def buttons_page(request: Request, msg: str = "", msg_type: str = "info"):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)

    all_buttons = await load_all_buttons()
    root_buttons = [b for b in all_buttons if b.parent_id is None]
    children: dict[int, list] = {}
    for b in all_buttons:
        if b.parent_id is not None:
            children.setdefault(b.parent_id, []).append(b)

    return templates.TemplateResponse("buttons.html", {
        "request": request,
        "root_buttons": root_buttons,
        "children": children,
        "msg": msg,
        "msg_type": msg_type,
    })


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


# ── Karabas sync ──────────────────────────────────────────────────────────

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
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
        )
    """)
    row = await db.fetchrow("SELECT value FROM admin_settings WHERE key = 'ai_prompt_extra'")
    await db.close()
    current = row["value"] if row else ""
    return templates.TemplateResponse("prompt.html", {
        "request": request,
        "current_prompt": current,
        "msg": msg,
        "msg_type": msg_type,
    })


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
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("chats.html", {"request": request})


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

    await set_session_status(row["user_id"], new_status)
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


# ── Manager online status ──────────────────────────────────────────────────

@app.get("/api/manager-status")
async def api_manager_status_get(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
        )
    """)
    row = await db.fetchrow("SELECT value FROM admin_settings WHERE key = 'manager_online'")
    await db.close()
    online = (row["value"] == "1") if row else False
    return JSONResponse({"online": online})


@app.post("/api/manager-status")
async def api_manager_status_set(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    online = body.get("online", False)
    db = await get_db()
    await db.execute("""
        INSERT INTO admin_settings (key, value) VALUES ('manager_online', $1)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, "1" if online else "0")
    await db.close()
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
