"""
Simple key-value settings storage in DB.
Used by admin panel to configure notification targets etc.
"""

from db.connection import get_pool


async def init_settings() -> None:
    """Create table on startup if not exists."""
    pool = await get_pool()
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)


async def get_setting(key: str, default: str = "") -> str:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT value FROM admin_settings WHERE key = $1", key
    )
    return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO admin_settings (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        key, value,
    )


# ── Convenience wrappers ──────────────────────────────────────────────────

async def get_notification_chat_id() -> str:
    """Return configured notification chat ID, or empty string if not set."""
    return await get_setting("notification_chat_id", "")


async def get_notification_enabled() -> bool:
    val = await get_setting("notification_enabled", "1")
    return val == "1"


async def get_manager_online() -> bool:
    """Return True if manager has set themselves as online in admin panel."""
    val = await get_setting("manager_online", "0")
    return val == "1"
