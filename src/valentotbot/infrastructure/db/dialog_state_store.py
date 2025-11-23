from __future__ import annotations

from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from valentotbot.infrastructure.db.models import DialogState

StateData = dict[str, Any]


class DialogStateStore:
    """Persistence layer for dialog states in Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_state(self, user_id: int) -> Tuple[Optional[str], StateData]:
        stmt = select(DialogState).where(DialogState.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None, {}
        return model.state, model.data or {}

    async def set_state(self, user_id: int, state: str, data: Optional[StateData] = None) -> None:
        stmt = select(DialogState).where(DialogState.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = DialogState(user_id=user_id, state=state, data=data or {})
            self._session.add(model)
        else:
            model.state = state
            model.data = data or {}
        await self._session.commit()

    async def clear_state(self, user_id: int) -> None:
        stmt = select(DialogState).where(DialogState.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return
        await self._session.delete(model)
        await self._session.commit()
