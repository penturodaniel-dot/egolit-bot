from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import asyncpg
import httpx
from config import settings

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
