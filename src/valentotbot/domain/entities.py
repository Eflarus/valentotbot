from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from valentotbot.domain.value_objects import CallbackTokenType, MessageStatus


@dataclass(slots=True)
class User:
    id: int
    telegram_user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language: Optional[str]
    is_blocked: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Link:
    id: int
    owner_user_id: int
    slug: str
    label: str
    prompt: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


@dataclass(slots=True)
class Message:
    id: int
    link_id: int
    recipient_user_id: int
    sender_user_id: Optional[int]
    text: str
    is_reveal_allowed: bool
    is_revealed: bool
    status: MessageStatus
    is_reported: bool
    created_at: datetime
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]


@dataclass(slots=True)
class Thread:
    id: int
    root_message_id: int
    created_at: datetime
    closed_at: Optional[datetime]


@dataclass(slots=True)
class ThreadMessage:
    id: int
    thread_id: int
    from_user_id: int
    to_user_id: int
    text: str
    created_at: datetime
    read_at: Optional[datetime]


@dataclass(slots=True)
class CallbackToken:
    id: int
    token: str
    type: CallbackTokenType
    entity_id: int
    extra_data: Optional[dict[str, object]]
    expires_at: Optional[datetime]
    created_at: datetime


@dataclass(slots=True)
class UserStats:
    total_messages: int
    total_replies: int
    total_revealed: int
    total_reported: int
    total_links: int
    link_stats: Sequence["LinkStats"]


@dataclass(slots=True)
class LinkStats:
    link_id: int
    label: str
    messages_count: int
    unique_senders: int
