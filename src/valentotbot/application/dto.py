from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from valentotbot.domain.entities import Link, Message, Thread, ThreadMessage, User
from valentotbot.domain.value_objects import MessageStatus


@dataclass(slots=True)
class TelegramUserData:
    telegram_user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language: Optional[str]


@dataclass(slots=True)
class CreateLinkInput:
    owner_user_id: int
    label: str
    prompt: Optional[str]


@dataclass(slots=True)
class SendAnonymousMessageInput:
    slug: str
    text: str
    is_reveal_allowed: bool
    sender_user_id: Optional[int]


@dataclass(slots=True)
class UserMessagesQuery:
    user_id: int
    status: Optional[MessageStatus] = None
    link_id: Optional[int] = None
    from_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


@dataclass(slots=True)
class ReplyToMessageInput:
    message_id: int
    from_user_id: int
    text: str


@dataclass(slots=True)
class RevealAuthorResult:
    sender: Optional[User]
    message: Message
    link: Link


@dataclass(slots=True)
class ReplyResult:
    thread: Thread
    reply: ThreadMessage
