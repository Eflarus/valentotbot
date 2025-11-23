from __future__ import annotations

from valentotbot.application.dto import TelegramUserData
from valentotbot.domain.entities import User
from valentotbot.domain.interfaces import UserRepository


class CreateOrUpdateUserFromTelegramService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, data: TelegramUserData) -> User:
        return await self._user_repo.upsert_from_telegram(
            telegram_user_id=data.telegram_user_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
            language=data.language,
        )
