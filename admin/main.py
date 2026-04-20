from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg
from config import settings

app = FastAPI()
templates = Jinja2Templates(directory="admin/templates")


async def get_db():
    return await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = await get_db()

    leads = await db.fetch("""
        SELECT id, created_at, name, phone, username, details, status, manager_note
        FROM bot_leads
        ORDER BY created_at DESC
    """)

    stats = await db.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'new')       AS new_count,
            COUNT(*) FILTER (WHERE status = 'in_work')   AS in_work_count,
            COUNT(*) FILTER (WHERE status = 'done')      AS done_count,
            COUNT(*)                                      AS total_count
        FROM bot_leads
    """)

    await db.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "leads": leads,
        "stats": stats,
    })


@app.post("/lead/{lead_id}/status")
async def update_status(lead_id: int, status: str = Form(...), manager_note: str = Form("")):
    db = await get_db()
    await db.execute("""
        UPDATE bot_leads SET status = $1, manager_note = $2 WHERE id = $3
    """, status, manager_note, lead_id)
    await db.close()
    return RedirectResponse("/", status_code=303)
