"""
FSM helpers — shared utilities for all handlers.
"""
from aiogram.fsm.context import FSMContext

# Keys that survive state.clear() — persistent user preferences
_PERSISTENT_KEYS = {"user_city"}


async def preserve_clear(state: FSMContext) -> None:
    """Clear FSM state but keep persistent user preferences (user_city, etc.)."""
    data = await state.get_data()
    preserved = {k: v for k, v in data.items() if k in _PERSISTENT_KEYS and v is not None}
    await state.clear()
    if preserved:
        await state.update_data(**preserved)
