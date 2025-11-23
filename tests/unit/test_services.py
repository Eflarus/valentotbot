from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pytest

from valentotbot.application.dto import CreateLinkInput, SendAnonymousMessageInput
from valentotbot.application.services.links import CreateLinkService
from valentotbot.application.services.messages import (
    ReplyToMessageService,
    SendAnonymousMessageService,
)
from valentotbot.application.services.reveal import RevealAuthorService
from valentotbot.domain.entities import (
    Link,
    LinkStats,
    Message,
    Thread,
    ThreadMessage,
    User,
    UserStats,
)
from valentotbot.domain.interfaces import (
    LinkRepository,
    MessageRepository,
    ThreadMessageRepository,
    ThreadRepository,
    UserRepository,
)
from valentotbot.domain.value_objects import MessageStatus


class InMemoryUserRepo(UserRepository):
    def __init__(self) -> None:
        self._users: Dict[int, User] = {}
        self._by_tg: Dict[int, int] = {}
        self._id_seq = 1

    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        user_id = self._by_tg.get(telegram_user_id)
        return self._users.get(user_id) if user_id is not None else None

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return self._users.get(user_id)

    async def upsert_from_telegram(
        self,
        telegram_user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        language: Optional[str],
    ) -> User:
        existing = await self.get_by_telegram_id(telegram_user_id)
        if existing:
            updated = User(
                id=existing.id,
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language=language,
                is_blocked=existing.is_blocked,
                created_at=existing.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._users[existing.id] = updated
            self._by_tg[telegram_user_id] = existing.id
            return updated
        user = User(
            id=self._id_seq,
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=language,
            is_blocked=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._users[self._id_seq] = user
        self._by_tg[telegram_user_id] = self._id_seq
        self._id_seq += 1
        return user


class InMemoryLinkRepo(LinkRepository):
    def __init__(self) -> None:
        self._links: Dict[int, Link] = {}
        self._by_slug: Dict[str, int] = {}
        self._id_seq = 1

    async def create(self, owner_user_id: int, slug: str, label: str, prompt: Optional[str]) -> Link:
        link = Link(
            id=self._id_seq,
            owner_user_id=owner_user_id,
            slug=slug,
            label=label,
            prompt=prompt,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )
        self._links[self._id_seq] = link
        self._by_slug[slug] = self._id_seq
        self._id_seq += 1
        return link

    async def list_by_owner(self, owner_user_id: int) -> Sequence[Link]:
        return [link for link in self._links.values() if link.owner_user_id == owner_user_id and link.deleted_at is None]

    async def get_by_slug(self, slug: str) -> Optional[Link]:
        link_id = self._by_slug.get(slug)
        return self._links.get(link_id) if link_id is not None else None

    async def get_by_id(self, link_id: int) -> Optional[Link]:
        return self._links.get(link_id)

    async def exists_slug(self, slug: str) -> bool:
        return slug in self._by_slug

    def set_link(self, link: Link) -> None:
        self._links[link.id] = link
        self._by_slug[link.slug] = link.id


class InMemoryMessageRepo(MessageRepository):
    def __init__(self) -> None:
        self._messages: Dict[int, Message] = {}
        self._id_seq = 1
        self.read_marked: List[int] = []
        self.revealed: List[int] = []

    async def create(
        self,
        link_id: int,
        recipient_user_id: int,
        sender_user_id: Optional[int],
        text: str,
        is_reveal_allowed: bool,
    ) -> Message:
        msg = Message(
            id=self._id_seq,
            link_id=link_id,
            recipient_user_id=recipient_user_id,
            sender_user_id=sender_user_id,
            text=text,
            is_reveal_allowed=is_reveal_allowed,
            is_revealed=False,
            status=MessageStatus.NEW,
            is_reported=False,
            created_at=datetime.now(timezone.utc),
            delivered_at=None,
            read_at=None,
        )
        self._messages[self._id_seq] = msg
        self._id_seq += 1
        return msg

    async def get_by_id(self, message_id: int) -> Optional[Message]:
        return self._messages.get(message_id)

    async def list_for_user(
        self,
        user_id: int,
        status: Optional[MessageStatus] = None,
        link_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Message]:
        messages = [
            m
            for m in self._messages.values()
            if m.recipient_user_id == user_id
            and (status is None or m.status == status)
            and (link_id is None or m.link_id == link_id)
            and (from_date is None or m.created_at >= from_date)
        ]
        return messages[offset : offset + limit]

    async def mark_revealed(self, message_id: int) -> None:
        msg = self._messages.get(message_id)
        if msg:
            msg.is_revealed = True
            self.revealed.append(message_id)

    async def mark_read(self, message_id: int) -> None:
        msg = self._messages.get(message_id)
        if msg:
            msg.status = MessageStatus.READ
            self.read_marked.append(message_id)

    async def get_stats(self, user_id: int) -> UserStats:
        total_messages = sum(1 for m in self._messages.values() if m.recipient_user_id == user_id)
        total_revealed = sum(1 for m in self._messages.values() if m.recipient_user_id == user_id and m.is_revealed)
        total_reported = sum(1 for m in self._messages.values() if m.recipient_user_id == user_id and m.is_reported)
        return UserStats(
            total_messages=total_messages,
            total_replies=0,
            total_revealed=total_revealed,
            total_reported=total_reported,
            total_links=0,
            link_stats=[],
        )

    async def get_link_stats(self, user_id: int) -> Sequence[LinkStats]:
        return []


class InMemoryThreadRepo(ThreadRepository):
    def __init__(self) -> None:
        self._threads: Dict[int, Thread] = {}
        self._id_seq = 1

    async def get_by_root_message(self, message_id: int) -> Optional[Thread]:
        for thread in self._threads.values():
            if thread.root_message_id == message_id:
                return thread
        return None

    async def create(self, root_message_id: int) -> Thread:
        thread = Thread(
            id=self._id_seq,
            root_message_id=root_message_id,
            created_at=datetime.now(timezone.utc),
            closed_at=None,
        )
        self._threads[self._id_seq] = thread
        self._id_seq += 1
        return thread


class InMemoryThreadMessageRepo(ThreadMessageRepository):
    def __init__(self) -> None:
        self._msgs: List[ThreadMessage] = []
        self._id_seq = 1

    async def create(
        self,
        thread_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
    ) -> ThreadMessage:
        tm = ThreadMessage(
            id=self._id_seq,
            thread_id=thread_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            text=text,
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )
        self._msgs.append(tm)
        self._id_seq += 1
        return tm

    async def list_by_thread(self, thread_id: int) -> Sequence[ThreadMessage]:
        return [m for m in self._msgs if m.thread_id == thread_id]


@pytest.mark.asyncio
async def test_create_link_generates_slug_unique() -> None:
    link_repo = InMemoryLinkRepo()
    service = CreateLinkService(link_repo)
    result = await service.execute(CreateLinkInput(owner_user_id=1, label="Test", prompt=None))
    assert result.slug
    assert result.owner_user_id == 1


@pytest.mark.asyncio
async def test_send_anonymous_message_success() -> None:
    link_repo = InMemoryLinkRepo()
    link = await link_repo.create(owner_user_id=1, slug="abc", label="L1", prompt=None)
    message_repo = InMemoryMessageRepo()
    service = SendAnonymousMessageService(link_repo, message_repo)
    msg = await service.execute(
        SendAnonymousMessageInput(slug=link.slug, text="hello", is_reveal_allowed=True, sender_user_id=2)
    )
    assert msg.recipient_user_id == 1
    assert msg.text == "hello"


@pytest.mark.asyncio
async def test_send_anonymous_message_inactive_link_raises() -> None:
    link_repo = InMemoryLinkRepo()
    link = await link_repo.create(owner_user_id=1, slug="abc", label="L1", prompt=None)
    link_repo.set_link(
        Link(
            id=link.id,
            owner_user_id=link.owner_user_id,
            slug=link.slug,
            label=link.label,
            prompt=link.prompt,
            is_active=False,
            created_at=link.created_at,
            updated_at=link.updated_at,
            deleted_at=link.deleted_at,
        )
    )
    message_repo = InMemoryMessageRepo()
    service = SendAnonymousMessageService(link_repo, message_repo)
    with pytest.raises(ValueError):
        await service.execute(
            SendAnonymousMessageInput(slug="abc", text="hello", is_reveal_allowed=False, sender_user_id=None)
        )


@pytest.mark.asyncio
async def test_reply_to_message_creates_thread_and_reply() -> None:
    message_repo = InMemoryMessageRepo()
    orig = await message_repo.create(link_id=1, recipient_user_id=1, sender_user_id=2, text="hi", is_reveal_allowed=False)
    thread_repo = InMemoryThreadRepo()
    thread_msg_repo = InMemoryThreadMessageRepo()
    service = ReplyToMessageService(message_repo, thread_repo, thread_msg_repo)
    result = await service.execute(message_id=orig.id, from_user_id=1, text="reply")
    assert result.thread.root_message_id == orig.id
    assert result.reply.text == "reply"
    assert result.reply.to_user_id == 2


@pytest.mark.asyncio
async def test_reveal_author_allows() -> None:
    user_repo = InMemoryUserRepo()
    sender = await user_repo.upsert_from_telegram(telegram_user_id=123, username="u", first_name=None, last_name=None, language=None)
    link_repo = InMemoryLinkRepo()
    link = await link_repo.create(owner_user_id=1, slug="abc", label="L1", prompt=None)
    message_repo = InMemoryMessageRepo()
    msg = await message_repo.create(
        link_id=link.id,
        recipient_user_id=link.owner_user_id,
        sender_user_id=sender.id,
        text="hi",
        is_reveal_allowed=True,
    )
    service = RevealAuthorService(message_repo, user_repo, link_repo)
    result = await service.execute(msg.id)
    assert result.sender is not None
    assert result.sender.id == sender.id


@pytest.mark.asyncio
async def test_reveal_author_forbidden() -> None:
    user_repo = InMemoryUserRepo()
    link_repo = InMemoryLinkRepo()
    link = await link_repo.create(owner_user_id=1, slug="abc", label="L1", prompt=None)
    message_repo = InMemoryMessageRepo()
    msg = await message_repo.create(
        link_id=link.id,
        recipient_user_id=link.owner_user_id,
        sender_user_id=None,
        text="hi",
        is_reveal_allowed=False,
    )
    service = RevealAuthorService(message_repo, user_repo, link_repo)
    with pytest.raises(PermissionError):
        await service.execute(msg.id)
