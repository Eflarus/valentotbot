from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from valentotbot.domain.entities import CallbackToken
from valentotbot.domain.interfaces import CallbackTokenRepository
from valentotbot.domain.value_objects import CallbackTokenType


class CallbackTokenService:
    def __init__(self, repo: CallbackTokenRepository) -> None:
        self._repo = repo

    def _generate_token(self, prefix: str = "cb_", length: int = 16) -> str:
        alphabet = string.ascii_letters + string.digits
        return prefix + "".join(secrets.choice(alphabet) for _ in range(length))

    async def create_token(
        self,
        type: CallbackTokenType,
        entity_id: int,
        extra_data: Optional[dict[str, object]] = None,
        ttl_seconds: int = 3600,
    ) -> CallbackToken:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        token = self._generate_token()
        # In rare case of collision, regenerate
        while await self._repo.get(token) is not None:
            token = self._generate_token()
        return await self._repo.create(token, type, entity_id, extra_data, expires_at)

    async def consume_token(self, token: str, one_time: bool = True) -> Optional[CallbackToken]:
        record = await self._repo.get(token)
        if record is None:
            return None
        if record.expires_at is not None and record.expires_at < datetime.now(timezone.utc):
            await self._repo.delete(token)
            return None
        if one_time:
            await self._repo.delete(token)
        return record
