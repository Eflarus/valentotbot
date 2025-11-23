from __future__ import annotations

from typing import Optional

from valentotbot.application.dto import RevealAuthorResult
from valentotbot.domain.entities import Link, Message, User
from valentotbot.domain.interfaces import (
    LinkRepository,
    MessageRepository,
    UserRepository,
)


class RevealAuthorService:
    def __init__(
        self,
        message_repo: MessageRepository,
        user_repo: UserRepository,
        link_repo: LinkRepository,
    ) -> None:
        self._message_repo = message_repo
        self._user_repo = user_repo
        self._link_repo = link_repo

    async def execute(self, message_id: int) -> RevealAuthorResult:
        message: Optional[Message] = await self._message_repo.get_by_id(message_id)
        if message is None:
            raise ValueError("Message not found")

        if not message.is_reveal_allowed:
            raise PermissionError("Reveal not allowed")

        sender: Optional[User] = None
        if message.sender_user_id is not None:
            sender = await self._user_repo.get_by_id(message.sender_user_id)

        link: Optional[Link] = await self._link_repo.get_by_id(message.link_id)
        if link is None:
            raise ValueError("Link not found for message")

        await self._message_repo.mark_revealed(message_id)
        return RevealAuthorResult(sender=sender, message=message, link=link)
