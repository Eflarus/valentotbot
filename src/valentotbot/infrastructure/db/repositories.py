from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from valentotbot.domain.entities import (
    CallbackToken as DomainCallbackToken,
    Link as DomainLink,
    LinkStats,
    Message as DomainMessage,
    Thread as DomainThread,
    ThreadMessage as DomainThreadMessage,
    User as DomainUser,
    UserStats,
)
from valentotbot.domain.interfaces import (
    CallbackTokenRepository,
    LinkRepository,
    MessageRepository,
    ThreadMessageRepository,
    ThreadRepository,
    UserRepository,
)
from valentotbot.domain.value_objects import CallbackTokenType, MessageStatus
from valentotbot.infrastructure.db.models import (
    CallbackToken,
    Link,
    Message,
    Thread,
    ThreadMessage,
    User,
)


def _map_user(model: User) -> DomainUser:
    return DomainUser(
        id=model.id,
        telegram_user_id=model.telegram_user_id,
        username=model.username,
        first_name=model.first_name,
        last_name=model.last_name,
        language=model.language,
        is_blocked=model.is_blocked,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _map_link(model: Link) -> DomainLink:
    return DomainLink(
        id=model.id,
        owner_user_id=model.owner_user_id,
        slug=model.slug,
        label=model.label,
        prompt=model.prompt,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _map_message(model: Message) -> DomainMessage:
    return DomainMessage(
        id=model.id,
        link_id=model.link_id,
        recipient_user_id=model.recipient_user_id,
        sender_user_id=model.sender_user_id,
        text=model.text,
        is_reveal_allowed=model.is_reveal_allowed,
        is_revealed=model.is_revealed,
        status=MessageStatus(model.status),
        is_reported=model.is_reported,
        created_at=model.created_at,
        delivered_at=model.delivered_at,
        read_at=model.read_at,
    )


def _map_thread(model: Thread) -> DomainThread:
    return DomainThread(
        id=model.id,
        root_message_id=model.root_message_id,
        created_at=model.created_at,
        closed_at=model.closed_at,
    )


def _map_thread_message(model: ThreadMessage) -> DomainThreadMessage:
    return DomainThreadMessage(
        id=model.id,
        thread_id=model.thread_id,
        from_user_id=model.from_user_id,
        to_user_id=model.to_user_id,
        text=model.text,
        created_at=model.created_at,
        read_at=model.read_at,
    )


def _map_callback_token(model: CallbackToken) -> DomainCallbackToken:
    return DomainCallbackToken(
        id=model.id,
        token=model.token,
        type=CallbackTokenType(model.type),
        entity_id=model.entity_id,
        extra_data=model.extra_data,
        expires_at=model.expires_at,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[DomainUser]:
        stmt: Select[tuple[User]] = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_user(model) if model else None

    async def get_by_id(self, user_id: int) -> Optional[DomainUser]:
        stmt: Select[tuple[User]] = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_user(model) if model else None

    async def upsert_from_telegram(
        self,
        telegram_user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        language: Optional[str],
    ) -> DomainUser:
        stmt: Select[tuple[User]] = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.username = username
            model.first_name = first_name
            model.last_name = last_name
            model.language = language
        else:
            model = User(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language=language,
            )
            self._session.add(model)

        await self._session.commit()
        await self._session.refresh(model)
        return _map_user(model)


class SqlAlchemyLinkRepository(LinkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, owner_user_id: int, slug: str, label: str, prompt: Optional[str]) -> DomainLink:
        model = Link(
            owner_user_id=owner_user_id,
            slug=slug,
            label=label,
            prompt=prompt,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _map_link(model)

    async def list_by_owner(self, owner_user_id: int) -> Sequence[DomainLink]:
        stmt: Select[tuple[Link]] = select(Link).where(Link.owner_user_id == owner_user_id, Link.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return [_map_link(model) for model in result.scalars().all()]

    async def get_by_slug(self, slug: str) -> Optional[DomainLink]:
        stmt: Select[tuple[Link]] = select(Link).where(Link.slug == slug, Link.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_link(model) if model else None

    async def get_by_id(self, link_id: int) -> Optional[DomainLink]:
        stmt: Select[tuple[Link]] = select(Link).where(Link.id == link_id, Link.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_link(model) if model else None

    async def exists_slug(self, slug: str) -> bool:
        stmt: Select[tuple[int]] = select(func.count()).select_from(Link).where(Link.slug == slug)
        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count > 0


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        link_id: int,
        recipient_user_id: int,
        sender_user_id: Optional[int],
        text: str,
        is_reveal_allowed: bool,
    ) -> DomainMessage:
        model = Message(
            link_id=link_id,
            recipient_user_id=recipient_user_id,
            sender_user_id=sender_user_id,
            text=text,
            is_reveal_allowed=is_reveal_allowed,
            status=MessageStatus.NEW.value,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _map_message(model)

    async def get_by_id(self, message_id: int) -> Optional[DomainMessage]:
        stmt: Select[tuple[Message]] = select(Message).where(Message.id == message_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_message(model) if model else None

    async def list_for_user(
        self,
        user_id: int,
        status: Optional[MessageStatus] = None,
        link_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DomainMessage]:
        stmt: Select[tuple[Message]] = select(Message).where(Message.recipient_user_id == user_id)
        if status is not None:
            stmt = stmt.where(Message.status == status.value)
        if link_id is not None:
            stmt = stmt.where(Message.link_id == link_id)
        if from_date is not None:
            stmt = stmt.where(Message.created_at >= from_date)
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_map_message(model) for model in result.scalars().all()]

    async def mark_revealed(self, message_id: int) -> None:
        stmt = (
            update(Message)
            .where(Message.id == message_id)
            .values(is_revealed=True)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def mark_read(self, message_id: int) -> None:
        stmt = update(Message).where(Message.id == message_id).values(status=MessageStatus.READ.value)
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_stats(self, user_id: int) -> UserStats:
        total_messages_stmt = select(func.count()).select_from(Message).where(Message.recipient_user_id == user_id)
        total_revealed_stmt = select(func.count()).select_from(Message).where(
            Message.recipient_user_id == user_id, Message.is_revealed.is_(True)
        )
        total_reported_stmt = select(func.count()).select_from(Message).where(
            Message.recipient_user_id == user_id, Message.is_reported.is_(True)
        )

        total_messages = (await self._session.execute(total_messages_stmt)).scalar_one()
        total_revealed = (await self._session.execute(total_revealed_stmt)).scalar_one()
        total_reported = (await self._session.execute(total_reported_stmt)).scalar_one()
        total_replies_stmt = select(func.count()).select_from(ThreadMessage).where(ThreadMessage.from_user_id == user_id)
        total_replies = (await self._session.execute(total_replies_stmt)).scalar_one()

        return UserStats(
            total_messages=int(total_messages),
            total_replies=int(total_replies),
            total_revealed=int(total_revealed),
            total_reported=int(total_reported),
            total_links=0,
            link_stats=[],
        )

    async def get_link_stats(self, user_id: int) -> Sequence[LinkStats]:
        stmt = (
            select(Link.id, Link.label, func.count(Message.id), func.count(func.distinct(Message.sender_user_id)))
            .join(Message, Message.link_id == Link.id)
            .where(Link.owner_user_id == user_id)
            .group_by(Link.id, Link.label)
        )
        result = await self._session.execute(stmt)
        stats: list[LinkStats] = []
        for link_id, label, msg_count, uniq_senders in result.all():
            stats.append(
                LinkStats(
                    link_id=int(link_id),
                    label=label,
                    messages_count=int(msg_count or 0),
                    unique_senders=int(uniq_senders or 0),
                )
            )
        return stats


class SqlAlchemyThreadRepository(ThreadRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_root_message(self, message_id: int) -> Optional[DomainThread]:
        stmt: Select[tuple[Thread]] = select(Thread).where(Thread.root_message_id == message_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_thread(model) if model else None

    async def create(self, root_message_id: int) -> DomainThread:
        model = Thread(root_message_id=root_message_id)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _map_thread(model)


class SqlAlchemyThreadMessageRepository(ThreadMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        thread_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
    ) -> DomainThreadMessage:
        model = ThreadMessage(
            thread_id=thread_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            text=text,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _map_thread_message(model)

    async def list_by_thread(self, thread_id: int) -> Sequence[DomainThreadMessage]:
        stmt: Select[tuple[ThreadMessage]] = (
            select(ThreadMessage).where(ThreadMessage.thread_id == thread_id).order_by(ThreadMessage.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_map_thread_message(model) for model in result.scalars().all()]


class SqlAlchemyCallbackTokenRepository(CallbackTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        token: str,
        type: CallbackTokenType,
        entity_id: int,
        extra_data: Optional[dict[str, object]],
        expires_at: Optional[datetime],
    ) -> DomainCallbackToken:
        model = CallbackToken(
            token=token,
            type=type.value,
            entity_id=entity_id,
            extra_data=extra_data,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _map_callback_token(model)

    async def get(self, token: str) -> Optional[DomainCallbackToken]:
        stmt: Select[tuple[CallbackToken]] = select(CallbackToken).where(CallbackToken.token == token)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _map_callback_token(model) if model else None

    async def delete(self, token: str) -> None:
        stmt = CallbackToken.__table__.delete().where(CallbackToken.token == token)
        await self._session.execute(stmt)
        await self._session.commit()
