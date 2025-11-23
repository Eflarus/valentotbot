from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence

from valentotbot.domain.entities import (
    CallbackToken,
    Link,
    LinkStats,
    Message,
    Thread,
    ThreadMessage,
    User,
    UserStats,
)
from valentotbot.domain.value_objects import CallbackTokenType, MessageStatus


class UserRepository(Protocol):
    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        ...

    async def get_by_id(self, user_id: int) -> Optional[User]:
        ...

    async def upsert_from_telegram(
        self,
        telegram_user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        language: Optional[str],
    ) -> User:
        ...


class LinkRepository(Protocol):
    async def create(self, owner_user_id: int, slug: str, label: str, prompt: Optional[str]) -> Link:
        ...

    async def list_by_owner(self, owner_user_id: int) -> Sequence[Link]:
        ...

    async def get_by_slug(self, slug: str) -> Optional[Link]:
        ...

    async def get_by_id(self, link_id: int) -> Optional[Link]:
        ...

    async def exists_slug(self, slug: str) -> bool:
        ...


class MessageRepository(Protocol):
    async def create(
        self,
        link_id: int,
        recipient_user_id: int,
        sender_user_id: Optional[int],
        text: str,
        is_reveal_allowed: bool,
    ) -> Message:
        ...

    async def get_by_id(self, message_id: int) -> Optional[Message]:
        ...

    async def list_for_user(
        self,
        user_id: int,
        status: Optional[MessageStatus] = None,
        link_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Message]:
        ...

    async def mark_revealed(self, message_id: int) -> None:
        ...

    async def mark_read(self, message_id: int) -> None:
        ...

    async def get_stats(self, user_id: int) -> UserStats:
        ...

    async def get_link_stats(self, user_id: int) -> Sequence[LinkStats]:
        ...


class ThreadRepository(Protocol):
    async def get_by_root_message(self, message_id: int) -> Optional[Thread]:
        ...

    async def create(self, root_message_id: int) -> Thread:
        ...


class ThreadMessageRepository(Protocol):
    async def create(
        self,
        thread_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
    ) -> ThreadMessage:
        ...

    async def list_by_thread(self, thread_id: int) -> Sequence[ThreadMessage]:
        ...


class CallbackTokenRepository(Protocol):
    async def create(
        self,
        token: str,
        type: CallbackTokenType,
        entity_id: int,
        extra_data: Optional[dict[str, object]],
        expires_at: Optional[datetime],
    ) -> CallbackToken:
        ...

    async def get(self, token: str) -> Optional[CallbackToken]:
        ...

    async def delete(self, token: str) -> None:
        ...
