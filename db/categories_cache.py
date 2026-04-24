"""
Stub — categories are now served from db/egolist_api.py (static dict from api.egolist.ua).
This module kept for backward compat with bot/main.py startup call.
"""
from db.egolist_api import get_categories_prompt as _get_prompt


async def load_categories():
    """No-op — categories are now a static dict, no DB load needed."""
    pass


def get_categories_prompt() -> str:
    return _get_prompt()


def get_all_category_ids() -> list[int]:
    return []


def expand_category_ids(ids: list[int]) -> list[int]:
    return ids
