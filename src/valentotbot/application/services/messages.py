from __future__ import annotations

from typing import Optional, Sequence

from valentotbot.application.dto import (
    ReplyResult,
    SendAnonymousMessageInput,
    UserMessagesQuery,
)
from valentotbot.domain.entities import Link, Message, UserStats
from valentotbot.domain.interfaces import (
    LinkRepository,
    MessageRepository,
    ThreadMessageRepository,
    ThreadRepository,
)


class SendAnonymousMessageService:
    def __init__(self, link_repo: LinkRepository, message_repo: MessageRepository) -> None:
        self._link_repo = link_repo
        self._message_repo = message_repo

    async def execute(self, input_data: SendAnonymousMessageInput) -> Message:
        link: Optional[Link] = await self._link_repo.get_by_slug(input_data.slug)
        if link is None or not link.is_active:
            raise ValueError("Link not found or inactive")

        return await self._message_repo.create(
            link_id=link.id,
            recipient_user_id=link.owner_user_id,
            sender_user_id=input_data.sender_user_id,
            text=input_data.text,
            is_reveal_allowed=input_data.is_reveal_allowed,
        )


class GetUserMessagesService:
    def __init__(self, message_repo: MessageRepository) -> None:
        self._message_repo = message_repo

    async def execute(self, query: UserMessagesQuery) -> Sequence[Message]:
        return await self._message_repo.list_for_user(
            user_id=query.user_id,
            status=query.status,
            link_id=query.link_id,
            from_date=query.from_date,
            limit=query.limit,
            offset=query.offset,
        )


class ReplyToMessageService:
    def __init__(
        self,
        message_repo: MessageRepository,
        thread_repo: ThreadRepository,
        thread_message_repo: ThreadMessageRepository,
    ) -> None:
        self._message_repo = message_repo
        self._thread_repo = thread_repo
        self._thread_message_repo = thread_message_repo

    async def execute(self, message_id: int, from_user_id: int, text: str) -> ReplyResult:
        message = await self._message_repo.get_by_id(message_id)
        if message is None:
            raise ValueError("Message not found")

        thread = await self._thread_repo.get_by_root_message(message_id)
        if thread is None:
            thread = await self._thread_repo.create(root_message_id=message_id)

        reply = await self._thread_message_repo.create(
            thread_id=thread.id,
            from_user_id=from_user_id,
            to_user_id=message.sender_user_id or message.recipient_user_id,
            text=text,
        )
        await self._message_repo.mark_read(message_id)
        return ReplyResult(thread=thread, reply=reply)


class GetUserStatsService:
    def __init__(self, message_repo: MessageRepository, link_repo: LinkRepository) -> None:
        self._message_repo = message_repo
        self._link_repo = link_repo

    async def execute(self, user_id: int) -> UserStats:
        stats = await self._message_repo.get_stats(user_id)
        total_links = len(await self._link_repo.list_by_owner(user_id))
        return UserStats(
            total_messages=stats.total_messages,
            total_replies=stats.total_replies,
            total_revealed=stats.total_revealed,
            total_reported=stats.total_reported,
            total_links=total_links,
            link_stats=await self._message_repo.get_link_stats(user_id),
        )
