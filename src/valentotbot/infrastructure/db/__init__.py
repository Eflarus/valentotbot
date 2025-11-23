"""Database package with engine and models."""

from valentotbot.infrastructure.db.dialog_state_store import DialogStateStore
from valentotbot.infrastructure.db.engine import (
    AsyncSessionFactory,
    build_connection_string,
    get_async_engine,
    get_session_factory,
    get_session_maker,
)
from valentotbot.infrastructure.db.models import (
    Base,
    CallbackToken,
    CallbackTokenType,
    DialogState,
    Link,
    Message,
    MessageStatus,
    Thread,
    ThreadMessage,
    User,
)
from valentotbot.infrastructure.db.repositories import (
    SqlAlchemyCallbackTokenRepository,
    SqlAlchemyLinkRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyThreadMessageRepository,
    SqlAlchemyThreadRepository,
    SqlAlchemyUserRepository,
)

__all__ = [
    "AsyncSessionFactory",
    "Base",
    "CallbackToken",
    "CallbackTokenType",
    "DialogState",
    "DialogStateStore",
    "Link",
    "Message",
    "MessageStatus",
    "Thread",
    "ThreadMessage",
    "User",
    "SqlAlchemyUserRepository",
    "SqlAlchemyLinkRepository",
    "SqlAlchemyMessageRepository",
    "SqlAlchemyThreadRepository",
    "SqlAlchemyThreadMessageRepository",
    "SqlAlchemyCallbackTokenRepository",
    "build_connection_string",
    "get_async_engine",
    "get_session_factory",
    "get_session_maker",
]
