from __future__ import annotations

from enum import Enum


class MessageStatus(str, Enum):
    NEW = "NEW"
    DELIVERED = "DELIVERED"
    READ = "READ"
    BLOCKED = "BLOCKED"


class CallbackTokenType(str, Enum):
    OPEN_MESSAGE = "OPEN_MESSAGE"
    REPLY = "REPLY"
    REVEAL_AUTHOR = "REVEAL_AUTHOR"
    PAGINATE = "PAGINATE"
    LINK_TOGGLE = "LINK_TOGGLE"
    LINK_CREATE = "LINK_CREATE"
