"""
Dynamic bot menu buttons stored in DB.
Supports one level of nesting: root buttons → child buttons (submenu).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from db.connection import get_pool


@dataclass
class MenuButton:
    id: int
    parent_id: Optional[int]
    label: str
    emoji: str
    action_type: str   # ai_search | submenu | lead_form | manager | custom_query
    ai_prompt: Optional[str]
    position: int
    is_active: bool

    @property
    def display(self) -> str:
        """Full text shown on the Telegram button."""
        return f"{self.emoji} {self.label}".strip() if self.emoji else self.label


# ── Default buttons seeded on first run ──────────────────────────────────

_DEFAULT_BUTTONS = [
    # (parent_id, label, emoji, action_type, ai_prompt, position)
    (None, "Куди піти сьогодні",      "🌆", "ai_search",
     "Які події та заходи відбуваються сьогодні у Дніпрі?", 0),
    (None, "Події на вихідні",        "📅", "ai_search",
     "Всі події та заходи на найближчі вихідні у Дніпрі", 1),
    (None, "Ідея для побачення",      "💑", "ai_search",
     "Яка подія є в афіші Дніпра?", 2),
    (None, "Куди з дітьми",           "👨‍👩‍👧", "ai_search",
     "Яка подія є в афіші Дніпра?", 3),
    (None, "Відпочити з друзями",     "🍻", "ai_search",
     "Яка подія є в афіші Дніпра?", 4),
    (None, "Концерти та фестивалі",   "🎵", "ai_search",
     "Концерти та музичні фестивалі у Дніпрі найближчим часом", 5),
    (None, "Знайти виконавця",        "🎤", "ai_search",
     "Знайди виконавця або артиста для свята у Дніпрі", 6),
    (None, "Свій запит",              "✍️", "custom_query", None, 7),
    (None, "Поговорити з менеджером", "📞", "manager",      None, 8),
]

# Prompts to migrate on existing DBs (label → new_prompt).
# Runs on EVERY startup to keep default buttons in sync with code.
# NOTE: only covers buttons with ORIGINAL default labels — user-renamed buttons are untouched.
_PROMPT_MIGRATIONS: dict[str, str] = {
    "Куди піти сьогодні":
        "Які події та заходи відбуваються сьогодні у Дніпрі?",
    "Події на вихідні":
        "Всі події та заходи на найближчі вихідні у Дніпрі",
    "Ідея для побачення":
        "Яка подія є в афіші Дніпра?",
    "Куди з дітьми":
        "Яка подія є в афіші Дніпра?",
    "Відпочити з друзями":
        "Яка подія є в афіші Дніпра?",
    "Знайти виконавця":
        "Знайди виконавця або артиста для свята у Дніпрі",
    "Куди поїхати недалеко":
        "Концерти та музичні фестивалі у Дніпрі найближчим часом",
}


# ── DB init ───────────────────────────────────────────────────────────────

async def init_menu_buttons() -> None:
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS bot_menu_buttons (
            id          SERIAL PRIMARY KEY,
            parent_id   INT REFERENCES bot_menu_buttons(id) ON DELETE CASCADE,
            label       TEXT NOT NULL,
            emoji       TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL DEFAULT 'ai_search',
            ai_prompt   TEXT,
            position    INT  NOT NULL DEFAULT 0,
            is_active   BOOL NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Seed defaults only if table is empty
    count = await pool.fetchval("SELECT COUNT(*) FROM bot_menu_buttons")
    if count == 0:
        for parent_id, label, emoji, action_type, ai_prompt, position in _DEFAULT_BUTTONS:
            await pool.execute("""
                INSERT INTO bot_menu_buttons
                    (parent_id, label, emoji, action_type, ai_prompt, position)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, parent_id, label, emoji, action_type, ai_prompt, position)
    else:
        # Migrate stale prompts on existing DBs
        for label, new_prompt in _PROMPT_MIGRATIONS.items():
            await pool.execute("""
                UPDATE bot_menu_buttons SET ai_prompt = $1
                WHERE label = $2 AND action_type = 'ai_search'
            """, new_prompt, label)


# ── Queries ───────────────────────────────────────────────────────────────

async def load_all_buttons() -> list[MenuButton]:
    """Return all active buttons ordered by parent_id NULLS FIRST, then position."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, parent_id, label, emoji, action_type, ai_prompt, position, is_active
        FROM bot_menu_buttons
        ORDER BY parent_id NULLS FIRST, position, id
    """)
    return [MenuButton(**dict(r)) for r in rows]


async def get_button(btn_id: int) -> Optional[MenuButton]:
    pool = await get_pool()
    row = await pool.fetchrow("""
        SELECT id, parent_id, label, emoji, action_type, ai_prompt, position, is_active
        FROM bot_menu_buttons WHERE id = $1
    """, btn_id)
    return MenuButton(**dict(row)) if row else None


async def create_button(
    label: str, emoji: str, action_type: str,
    ai_prompt: Optional[str], parent_id: Optional[int], position: int
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow("""
        INSERT INTO bot_menu_buttons (parent_id, label, emoji, action_type, ai_prompt, position)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
    """, parent_id, label, emoji, action_type, ai_prompt or None, position)
    return row["id"]


async def update_button(
    btn_id: int, label: str, emoji: str, action_type: str,
    ai_prompt: Optional[str], parent_id: Optional[int], position: int
) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE bot_menu_buttons
        SET label=$1, emoji=$2, action_type=$3, ai_prompt=$4, parent_id=$5, position=$6
        WHERE id=$7
    """, label, emoji, action_type, ai_prompt or None, parent_id, position, btn_id)


async def toggle_button(btn_id: int) -> None:
    pool = await get_pool()
    await pool.execute("""
        UPDATE bot_menu_buttons SET is_active = NOT is_active WHERE id = $1
    """, btn_id)


async def delete_button(btn_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM bot_menu_buttons WHERE id = $1", btn_id)
