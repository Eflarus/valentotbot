from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_core_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    message_status_enum = sa.Enum(
        "NEW",
        "DELIVERED",
        "READ",
        "BLOCKED",
        name="message_status",
    )
    callback_token_type_enum = sa.Enum(
        "OPEN_MESSAGE",
        "REPLY",
        "REVEAL_AUTHOR",
        "PAGINATE",
        name="callback_token_type",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])

    op.create_table(
        "links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_links_owner_user_id", "links", ["owner_user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("link_id", sa.BigInteger(), sa.ForeignKey("links.id"), nullable=False),
        sa.Column("recipient_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_reveal_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_revealed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", message_status_enum, nullable=False, server_default="NEW"),
        sa.Column("is_reported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_messages_recipient_user_id", "messages", ["recipient_user_id"])
    op.create_index("ix_messages_link_id", "messages", ["link_id"])
    op.create_index("ix_messages_sender_user_id", "messages", ["sender_user_id"])

    op.create_table(
        "threads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("root_message_id", sa.BigInteger(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("root_message_id"),
    )

    op.create_table(
        "thread_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("from_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])
    op.create_index("ix_thread_messages_from_user_id", "thread_messages", ["from_user_id"])

    op.create_table(
        "callback_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        sa.Column("type", callback_token_type_enum, nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_callback_tokens_token", "callback_tokens", ["token"], unique=True)

    op.create_table(
        "dialog_states",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("dialog_states")
    op.drop_index("ix_callback_tokens_token", table_name="callback_tokens")
    op.drop_table("callback_tokens")
    op.drop_index("ix_thread_messages_from_user_id", table_name="thread_messages")
    op.drop_index("ix_thread_messages_thread_id", table_name="thread_messages")
    op.drop_table("thread_messages")
    op.drop_table("threads")
    op.drop_index("ix_messages_sender_user_id", table_name="messages")
    op.drop_index("ix_messages_link_id", table_name="messages")
    op.drop_index("ix_messages_recipient_user_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_links_owner_user_id", table_name="links")
    op.drop_table("links")
    op.drop_index("ix_users_telegram_user_id", table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS message_status")
    op.execute("DROP TYPE IF EXISTS callback_token_type")
