from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import asyncpg
from config import settings

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SECRET_KEY)
templates = Jinja2Templates(directory="admin/templates")


# ── Auth ──────────────────────────────────────────────────────────────────

def require_auth(request: Request):
    """Залежність — перевіряє чи залогінений менеджер."""
    if not request.session.get("authenticated"):
        raise Exception("not_authenticated")


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

    await db.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "leads": leads,
        "stats": stats,
    })


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
