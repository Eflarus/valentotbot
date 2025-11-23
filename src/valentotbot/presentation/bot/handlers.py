from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from valentotbot.application.dto import (
    CreateLinkInput,
    ReplyResult,
    SendAnonymousMessageInput,
    TelegramUserData,
    UserMessagesQuery,
)
from valentotbot.application.services.callback_tokens import CallbackTokenService
from valentotbot.application.services.links import CreateLinkService
from valentotbot.application.services.messages import (
    GetUserMessagesService,
    GetUserStatsService,
    ReplyToMessageService,
    SendAnonymousMessageService,
)
from valentotbot.application.services.reveal import RevealAuthorService
from valentotbot.application.services.users import CreateOrUpdateUserFromTelegramService
from valentotbot.config import get_settings
from valentotbot.domain.entities import Link
from valentotbot.domain.interfaces import LinkRepository, UserRepository
from valentotbot.domain.value_objects import CallbackTokenType, MessageStatus
from valentotbot.i18n import resolve_lang, translate
from valentotbot.infrastructure.db import (
    AsyncSessionFactory,
    DialogStateStore,
    SqlAlchemyCallbackTokenRepository,
    SqlAlchemyLinkRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyThreadMessageRepository,
    SqlAlchemyThreadRepository,
    SqlAlchemyUserRepository,
)

logger = logging.getLogger(__name__)

REVEAL_ALLOW = "Разрешить раскрытие"
REVEAL_DENY = "Запретить раскрытие"
CREATE_LINK_BTN = "Создать ссылку"


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("messages", messages_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("links", links_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, non_text_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))


def _get_session_maker(context: ContextTypes.DEFAULT_TYPE) -> AsyncSessionFactory:
    session_maker = context.bot_data.get("session_maker")
    if session_maker is None:
        raise RuntimeError("Session maker is not configured")
    return session_maker


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    args = context.args or []
    if args and args[0].startswith("link_"):
        await handle_start_with_link(update, context, args[0][5:])
    else:
        await handle_start_menu(update, context)


def _parse_period(value: str) -> Optional[datetime]:
    now = datetime.now(timezone.utc)
    if value.endswith("d") and value[:-1].isdigit():
        days = int(value[:-1])
        return now - timedelta(days=days)
    if value.endswith("h") and value[:-1].isdigit():
        hours = int(value[:-1])
        return now - timedelta(hours=hours)
    return None


def _parse_message_filters(args: Sequence[str]) -> Tuple[Optional[MessageStatus], Optional[str], Optional[datetime]]:
    status: Optional[MessageStatus] = None
    link_slug: Optional[str] = None
    from_date: Optional[datetime] = None
    for arg in args:
        if "=" not in arg:
            continue
        key, val = arg.split("=", 1)
        key = key.lower()
        if key == "status":
            try:
                status = MessageStatus(val.upper())
            except ValueError:
                status = None
        elif key == "link":
            link_slug = val
        elif key == "period":
            from_date = _parse_period(val)
    return status, link_slug, from_date


def _build_deeplink(bot_username: str, slug: str) -> str:
    return f"https://t.me/{bot_username}?start=link_{slug}"


async def handle_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        user_repo: UserRepository = SqlAlchemyUserRepository(session)
        user_service = CreateOrUpdateUserFromTelegramService(user_repo)
        user = await user_service.execute(
            TelegramUserData(
                telegram_user_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                language=update.effective_user.language_code,
            )
        )
        state_store = DialogStateStore(session)
        await state_store.clear_state(user.id)

    lang = resolve_lang(update.effective_user.language_code)
    menu_text = translate("greeting_menu", lang)
    await update.message.reply_text(menu_text)  # type: ignore[union-attr]


async def handle_start_with_link(update: Update, context: ContextTypes.DEFAULT_TYPE, slug: str) -> None:
    if update.effective_user is None:
        return
    invalid_link = False
    link: Optional[Link] = None
    user_id: Optional[int] = None
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        user_repo: UserRepository = SqlAlchemyUserRepository(session)
        link_repo: LinkRepository = SqlAlchemyLinkRepository(session)
        user_service = CreateOrUpdateUserFromTelegramService(user_repo)
        user = await user_service.execute(
            TelegramUserData(
                telegram_user_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                language=update.effective_user.language_code,
            )
        )
        user_id = user.id
        link = await link_repo.get_by_slug(slug)
        if link is None or not link.is_active:
            invalid_link = True
        else:
            state_store = DialogStateStore(session)
            await state_store.set_state(
                user_id=user.id,
                state="await_reveal_choice",
                data={"pending_link_slug": slug},
            )

    lang = resolve_lang(update.effective_user.language_code)
    if invalid_link or link is None or user_id is None:
        await update.message.reply_text(translate("invalid_link", lang))  # type: ignore[union-attr]
        return

    prompt_parts = [translate("send_prompt", lang)]
    if link.prompt:
        prompt_parts.append(f"Промпт: {link.prompt}")
    prompt_parts.append(translate("reveal_choice", lang))

    reply_keyboard = ReplyKeyboardMarkup([[REVEAL_ALLOW, REVEAL_DENY]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("\n".join(prompt_parts), reply_markup=reply_keyboard)  # type: ignore[union-attr]


async def links_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    await render_links_list(update, context, via_callback=False)


async def messages_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    status, link_slug, from_date = _parse_message_filters(context.args or [])
    await render_messages_page(
        update=update,
        context=context,
        offset=0,
        limit=5,
        status=status,
        link_slug=link_slug,
        from_date=from_date,
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    session_maker = _get_session_maker(context)
    text: str = "Статистика недоступна."
    lang = resolve_lang(update.effective_user.language_code)
    async with session_maker() as session:
        user_repo = SqlAlchemyUserRepository(session)
        message_repo = SqlAlchemyMessageRepository(session)
        link_repo = SqlAlchemyLinkRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if user is None:
            await update.message.reply_text(translate("user_not_found", lang))  # type: ignore[union-attr]
            return
        stats_service = GetUserStatsService(message_repo, link_repo)
        stats = await stats_service.execute(user.id)

        lines = [
            translate("stats_header", lang),
            f"Всего сообщений: {stats.total_messages}",
            f"Ответов: {stats.total_replies}",
            f"Раскрытий автора: {stats.total_revealed}",
            f"Жалоб: {stats.total_reported}",
            f"Ссылок: {stats.total_links}",
            "",
            "По ссылкам:",
        ]
        if stats.link_stats:
            for item in stats.link_stats:
                lines.append(f"- {item.label}: сообщений {item.messages_count}, уникальных отправителей {item.unique_senders}")
        else:
            lines.append(translate("stats_links_none", lang))
        text = "\n".join(lines)

    await update.message.reply_text(text)  # type: ignore[union-attr]


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        return
    text = update.message.text
    if text is None:
        return

    lang = resolve_lang(update.effective_user.language_code)
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        user_repo = SqlAlchemyUserRepository(session)
        user_service = CreateOrUpdateUserFromTelegramService(user_repo)
        user = await user_service.execute(
            TelegramUserData(
                telegram_user_id=update.effective_user.id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                language=update.effective_user.language_code,
            )
        )
        state_store = DialogStateStore(session)
        state, data = await state_store.get_state(user.id)

    if state == "await_reply_text":
        await handle_reply_text(update, context, text, user_id=user.id)
        return
    if state == "await_reveal_choice":
        await handle_reveal_choice(update, context, text, user_id=user.id, state_data=data)
        return
    if state == "await_message_text":
        await handle_message_text(update, context, text, user_id=user.id, state_data=data)
        return
    if state == "await_link_label":
        await handle_link_label(update, context, text, user_id=user.id, lang=lang)
        return
    if state == "await_link_prompt":
        await handle_link_prompt(update, context, text, user_id=user.id, state_data=data, lang=lang)
        return

    await update.message.reply_text(translate("send_prompt", lang))


async def handle_reveal_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: int,
    state_data: Optional[dict[str, Any]] = None,
) -> None:
    if text not in (REVEAL_ALLOW, REVEAL_DENY):
        await update.message.reply_text(
            "Выберите один из вариантов.",
            reply_markup=ReplyKeyboardMarkup([[REVEAL_ALLOW, REVEAL_DENY]], one_time_keyboard=True, resize_keyboard=True),
        )  # type: ignore[union-attr]
        return
    pending_link_slug = (state_data or {}).get("pending_link_slug")
    if not pending_link_slug:
        await update.message.reply_text("Сессия устарела, начните заново по ссылке.")  # type: ignore[union-attr]
        return

    reveal_allowed = text == REVEAL_ALLOW
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        state_store = DialogStateStore(session)
        await state_store.set_state(
            user_id=user_id,
            state="await_message_text",
            data={"pending_link_slug": pending_link_slug, "pending_reveal_allowed": reveal_allowed},
        )
    await update.message.reply_text(
        "Введите текст сообщения (1–2000 символов).",
        reply_markup=ReplyKeyboardRemove(),
    )  # type: ignore[union-attr]


async def handle_message_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: int,
    state_data: Optional[dict[str, Any]] = None,
) -> None:
    if update.effective_user is None:
        return
    if len(text) < 1 or len(text) > 2000:
        lang = resolve_lang(update.effective_user.language_code)
        await update.message.reply_text(translate("message_too_short", lang))  # type: ignore[union-attr]
        return
    slug = (state_data or {}).get("pending_link_slug")
    reveal_allowed = (state_data or {}).get("pending_reveal_allowed")
    sender_user_id = user_id
    if not slug or reveal_allowed is None:
        lang = resolve_lang(update.effective_user.language_code)
        await update.message.reply_text(translate("session_expired", lang))  # type: ignore[union-attr]
        session_maker = _get_session_maker(context)
        async with session_maker() as session:
            state_store = DialogStateStore(session)
            await state_store.clear_state(user_id)
        return

    open_token_value: Optional[str] = None
    link_label: str = ""
    recipient_chat_id: Optional[int] = None
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        link_repo = SqlAlchemyLinkRepository(session)
        message_repo = SqlAlchemyMessageRepository(session)
        user_repo = SqlAlchemyUserRepository(session)
        callback_repo = SqlAlchemyCallbackTokenRepository(session)
        state_store = DialogStateStore(session)
        token_service = CallbackTokenService(callback_repo)

        send_service = SendAnonymousMessageService(link_repo, message_repo)
        msg = await send_service.execute(
            SendAnonymousMessageInput(
                slug=slug,
                text=text,
                is_reveal_allowed=bool(reveal_allowed),
                sender_user_id=sender_user_id,
            )
        )

        link = await link_repo.get_by_slug(slug)
        recipient = await user_repo.get_by_id(msg.recipient_user_id)
        open_token = await token_service.create_token(
            CallbackTokenType.OPEN_MESSAGE,
            entity_id=msg.id,
            ttl_seconds=86400,
        )
        await state_store.clear_state(user_id)
        open_token_value = open_token.token
        link_label = link.label if link else ""
        recipient_chat_id = recipient.telegram_user_id if recipient else None

    lang = resolve_lang(update.effective_user.language_code)
    await update.message.reply_text(translate("message_sent", lang))  # type: ignore[union-attr]

    if recipient_chat_id is not None and open_token_value is not None:
        notify_text = f'Новая валентинка по вашей ссылке "{link_label}":\n{text[:200]}'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Открыть валентинку", callback_data=open_token_value)]])
        try:
            await context.bot.send_message(chat_id=recipient_chat_id, text=notify_text, reply_markup=keyboard)
        except Exception as exc:  # pragma: no cover - notification failures are non-critical
            logger.warning("Failed to notify recipient %s: %s", recipient_chat_id, exc)


async def non_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    lang = resolve_lang(update.effective_user.language_code if update.effective_user else "ru")
    await update.message.reply_text(translate("text_only", lang))


async def handle_link_label(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: int,
    lang: str,
) -> None:
    if not text.strip():
        await update.message.reply_text(translate("enter_link_label", lang))  # type: ignore[union-attr]
        return
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        state_store = DialogStateStore(session)
        await state_store.set_state(user_id, "await_link_prompt", data={"label": text.strip()})
    await update.message.reply_text(translate("enter_link_prompt", lang))  # type: ignore[union-attr]


async def handle_link_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: int,
    state_data: Optional[dict[str, Any]],
    lang: str,
) -> None:
    label = (state_data or {}).get("label")
    if not label:
        await update.message.reply_text(translate("session_expired", lang))  # type: ignore[union-attr]
        return
    prompt_value = None if text.strip() == "-" else text.strip()

    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        link_repo = SqlAlchemyLinkRepository(session)
        create_service = CreateLinkService(link_repo)
        link = await create_service.execute(CreateLinkInput(owner_user_id=user_id, label=label, prompt=prompt_value))
        state_store = DialogStateStore(session)
        await state_store.clear_state(user_id)

    settings = get_settings()
    deeplink = _build_deeplink(settings.bot_username, link.slug)
    text_resp = f"{translate('link_created', lang)}\n{link.label}\n{deeplink}"
    await update.message.reply_text(text_resp)  # type: ignore[union-attr]


async def render_links_list(update: Update, context: ContextTypes.DEFAULT_TYPE, via_callback: bool) -> None:
    if update.effective_user is None:
        return
    lang = resolve_lang(update.effective_user.language_code)
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        user_repo = SqlAlchemyUserRepository(session)
        link_repo = SqlAlchemyLinkRepository(session)
        message_repo = SqlAlchemyMessageRepository(session)
        callback_repo = SqlAlchemyCallbackTokenRepository(session)
        token_service = CallbackTokenService(callback_repo)

        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if user is None:
            target = update.callback_query if via_callback else update.message
            if target:
                await target.reply_text(translate("user_not_found", lang))  # type: ignore[union-attr]
            return

        links = await link_repo.list_by_owner(user.id)
        link_stats = await message_repo.get_link_stats(user.id)
        stats_map = {ls.link_id: ls.messages_count for ls in link_stats}

        buttons: list[list[InlineKeyboardButton]] = []
        lines: list[str] = [translate("links_header", lang)]
        if not links:
            lines.append(translate("no_links", lang))
        for link in links:
            status = "✅" if link.is_active else "⏸"
            count = stats_map.get(link.id, 0)
            lines.append(f"{status} {link.label} ({count})")
            toggle_token = await token_service.create_token(
                CallbackTokenType.LINK_TOGGLE,
                entity_id=link.id,
                extra_data={"link_id": link.id},
                ttl_seconds=3600,
            )
            buttons.append([InlineKeyboardButton("Вкл/Выкл", callback_data=toggle_token.token)])

        create_token = await token_service.create_token(
            CallbackTokenType.LINK_CREATE,
            entity_id=0,
            extra_data={},
            ttl_seconds=1800,
        )
        buttons.append([InlineKeyboardButton(CREATE_LINK_BTN, callback_data=create_token.token)])

        text = "\n".join(lines)
        markup = InlineKeyboardMarkup(buttons)
        if via_callback and update.callback_query is not None:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        elif update.message:
            await update.message.reply_text(text, reply_markup=markup)  # type: ignore[union-attr]


async def render_messages_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    offset: int,
    limit: int,
    status: Optional[MessageStatus],
    link_slug: Optional[str],
    from_date: Optional[datetime],
    via_callback: bool = False,
) -> None:
    if update.effective_user is None:
        return
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        user_repo = SqlAlchemyUserRepository(session)
        message_repo = SqlAlchemyMessageRepository(session)
        link_repo = SqlAlchemyLinkRepository(session)
        callback_repo = SqlAlchemyCallbackTokenRepository(session)
        token_service = CallbackTokenService(callback_repo)

        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if user is None:
            target = update.callback_query if via_callback else update.message
            if target:
                await target.reply_text(translate("user_not_found", resolve_lang(update.effective_user.language_code)))  # type: ignore[union-attr]
            return

        link_id: Optional[int] = None
        link_label = ""
        if link_slug:
            link = await link_repo.get_by_slug(link_slug)
            if link is None or link.owner_user_id != user.id:
                text = translate("link_not_found", resolve_lang(update.effective_user.language_code))
                if via_callback and update.callback_query is not None:
                    await update.callback_query.edit_message_text(text)
                elif update.message:
                    await update.message.reply_text(text)  # type: ignore[union-attr]
                return
            link_id = link.id
            link_label = link.label

        messages_service = GetUserMessagesService(message_repo)
        query = UserMessagesQuery(
            user_id=user.id,
            status=status,
            link_id=link_id,
            from_date=from_date,
            limit=limit,
            offset=offset,
        )
        messages = await messages_service.execute(query)

        if not messages:
            text = translate("no_messages", resolve_lang(update.effective_user.language_code))
            if via_callback and update.callback_query is not None:
                await update.callback_query.edit_message_text(text)
            elif update.message:
                await update.message.reply_text(text)  # type: ignore[union-attr]
            return

        rows: list[str] = ["Мои сообщения:"]
        if status:
            rows.append(f"Статус: {status.value}")
        if link_label:
            rows.append(f"Ссылка: {link_label}")
        if from_date:
            rows.append(f"Период: с {from_date.isoformat()}")
        rows.append("")

        buttons: list[list[InlineKeyboardButton]] = []
        for msg in messages:
            open_token = await token_service.create_token(
                CallbackTokenType.OPEN_MESSAGE,
                entity_id=msg.id,
                ttl_seconds=3600,
            )
            rows.append(f"- [{msg.status.value}] #{msg.id}: {msg.text[:80]}")
            buttons.append([InlineKeyboardButton(f"Открыть #{msg.id}", callback_data=open_token.token)])

        prev_buttons: list[InlineKeyboardButton] = []
        next_buttons: list[InlineKeyboardButton] = []
        extra_data = {
            "status": status.name if status else None,
            "link_slug": link_slug,
            "from_ts": from_date.isoformat() if from_date else None,
            "limit": limit,
        }
        if offset > 0:
            prev_token = await token_service.create_token(
                CallbackTokenType.PAGINATE,
                entity_id=0,
                extra_data={**extra_data, "offset": max(0, offset - limit)},
                ttl_seconds=1800,
            )
            prev_buttons.append(InlineKeyboardButton("◀️ Предыдущие", callback_data=prev_token.token))
        if len(messages) == limit:
            next_token = await token_service.create_token(
                CallbackTokenType.PAGINATE,
                entity_id=0,
                extra_data={**extra_data, "offset": offset + limit},
                ttl_seconds=1800,
            )
            next_buttons.append(InlineKeyboardButton("Следующие ▶️", callback_data=next_token.token))
        nav_row: list[InlineKeyboardButton] = []
        nav_row.extend(prev_buttons)
        nav_row.extend(next_buttons)
        if nav_row:
            buttons.append(nav_row)

        text = "\n".join(rows)
        markup = InlineKeyboardMarkup(buttons) if buttons else None
        if via_callback and update.callback_query is not None:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        elif update.message:
            await update.message.reply_text(text, reply_markup=markup)  # type: ignore[union-attr]


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is None or update.effective_user is None:
        return
    token_str = update.callback_query.data
    if token_str is None:
        return

    await update.callback_query.answer()
    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        callback_repo = SqlAlchemyCallbackTokenRepository(session)
        token_service = CallbackTokenService(callback_repo)
        token = await token_service.consume_token(token_str, one_time=True)
        if token is None:
            await update.callback_query.answer("Кнопка больше не действительна.", show_alert=True)
            return

        message_repo = SqlAlchemyMessageRepository(session)
        link_repo = SqlAlchemyLinkRepository(session)
        user_repo = SqlAlchemyUserRepository(session)
        thread_repo = SqlAlchemyThreadRepository(session)
        thread_msg_repo = SqlAlchemyThreadMessageRepository(session)
        state_store = DialogStateStore(session)

        effective_user = update.effective_user
        user = await user_repo.get_by_telegram_id(effective_user.id)
        if user is None:
            await update.callback_query.answer("Пользователь не найден.", show_alert=True)
            return

        if token.type == CallbackTokenType.PAGINATE:
            extra = token.extra_data or {}
            status_val = extra.get("status")
            status = None
            if isinstance(status_val, str):
                try:
                    status = MessageStatus[status_val]
                except KeyError:
                    status = None
            link_slug = extra.get("link_slug") if isinstance(extra.get("link_slug"), str) else None
            from_ts = extra.get("from_ts") if isinstance(extra.get("from_ts"), str) else None
            from_date = datetime.fromisoformat(from_ts) if from_ts else None
            offset = int(extra.get("offset") or 0)
            limit = int(extra.get("limit") or 5)
            await render_messages_page(
                update=update,
                context=context,
                offset=offset,
                limit=limit,
                status=status,
                link_slug=link_slug,
                from_date=from_date,
                via_callback=True,
            )
            return

        if token.type == CallbackTokenType.LINK_CREATE:
            await state_store.set_state(user.id, "await_link_label", data={})
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
            await update.callback_query.message.reply_text(translate("enter_link_label", resolve_lang(update.effective_user.language_code)))  # type: ignore[union-attr]
            return

        if token.type == CallbackTokenType.LINK_TOGGLE:
            link_id = token.extra_data.get("link_id") if token.extra_data else None
            if not isinstance(link_id, int):
                await update.callback_query.answer(
                    translate("link_not_found", resolve_lang(update.effective_user.language_code)), show_alert=True
                )
                return
            link = await link_repo.get_by_id(link_id)
            if link is None or link.owner_user_id != user.id:
                await update.callback_query.answer(
                    translate("link_not_found", resolve_lang(update.effective_user.language_code)), show_alert=True
                )
                return
            await link_repo.set_active(link_id, not link.is_active)
            await update.callback_query.answer(
                translate("link_toggled_on" if not link.is_active else "link_toggled_off", resolve_lang(update.effective_user.language_code)),
                show_alert=False,
            )
            await render_links_list(update, context, via_callback=True)
            return

        if token.type == CallbackTokenType.OPEN_MESSAGE:
            message = await message_repo.get_by_id(token.entity_id)
            if message is None or message.recipient_user_id != user.id:
                await update.callback_query.answer("Сообщение недоступно.", show_alert=True)
                return
            await message_repo.mark_read(message.id)
            link = await link_repo.get_by_id(message.link_id)

            reply_token = await token_service.create_token(
                CallbackTokenType.REPLY,
                entity_id=message.id,
                ttl_seconds=3600,
            )
            reveal_token: Optional[str] = None
            if message.is_reveal_allowed:
                reveal_token_obj = await token_service.create_token(
                    CallbackTokenType.REVEAL_AUTHOR,
                    entity_id=message.id,
                    ttl_seconds=3600,
                )
                reveal_token = reveal_token_obj.token

            buttons = [[InlineKeyboardButton("Ответить анонимно", callback_data=reply_token.token)]]
            if reveal_token:
                buttons.append([InlineKeyboardButton("Раскрыть автора", callback_data=reveal_token)])

            body_lines = [f'Валентинка по ссылке "{link.label if link else ""}":', message.text]
            await update.callback_query.edit_message_text(
                "\n\n".join(body_lines),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        if token.type == CallbackTokenType.REPLY:
            message = await message_repo.get_by_id(token.entity_id)
            if message is None or message.recipient_user_id != user.id:
                await update.callback_query.answer("Сообщение недоступно.", show_alert=True)
                return
            await state_store.set_state(
                user_id=user.id,
                state="await_reply_text",
                data={"reply_to_message_id": message.id},
            )
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
            await update.callback_query.message.reply_text("Введите текст ответа (1–2000 символов).")  # type: ignore[union-attr]
            return

        if token.type == CallbackTokenType.REVEAL_AUTHOR:
            reveal_service = RevealAuthorService(message_repo, user_repo, link_repo)
            try:
                result = await reveal_service.execute(token.entity_id)
            except PermissionError:
                await update.callback_query.answer("Автор запретил раскрытие.", show_alert=True)
                return
            except ValueError:
                await update.callback_query.answer("Сообщение не найдено.", show_alert=True)
                return

            sender = result.sender
            if sender is None:
                await update.callback_query.answer("Автор анонимен.", show_alert=True)
                return

            display_name = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            contact_button = InlineKeyboardButton(
                text="Перейти в чат",
                url=f"tg://user?id={sender.telegram_user_id}",
            )
            text = f"Автор: {display_name or 'без имени'}"
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
            await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[contact_button]]))  # type: ignore[union-attr]
            return

    await update.callback_query.answer("Неизвестное действие.", show_alert=True)


async def handle_reply_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: int,
    state_data: Optional[dict[str, Any]] = None,
) -> None:
    if update.effective_user is None or update.message is None:
        return
    if len(text) < 1 or len(text) > 2000:
        await update.message.reply_text("Ответ должен быть от 1 до 2000 символов.")
        return

    reply_to_message_id = (state_data or {}).get("reply_to_message_id")
    if reply_to_message_id is None:
        await update.message.reply_text("Сессия ответа устарела.")
        session_maker = _get_session_maker(context)
        async with session_maker() as session:
            state_store = DialogStateStore(session)
            await state_store.clear_state(user_id)
        return

    session_maker = _get_session_maker(context)
    async with session_maker() as session:
        message_repo = SqlAlchemyMessageRepository(session)
        thread_repo = SqlAlchemyThreadRepository(session)
        thread_msg_repo = SqlAlchemyThreadMessageRepository(session)
        user_repo = SqlAlchemyUserRepository(session)
        state_store = DialogStateStore(session)

        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if user is None:
            await update.message.reply_text("Пользователь не найден.")
            return

        reply_service = ReplyToMessageService(message_repo, thread_repo, thread_msg_repo)
        try:
            result: ReplyResult = await reply_service.execute(
                message_id=int(reply_to_message_id),
                from_user_id=user.id,
                text=text,
            )
        except ValueError:
            await update.message.reply_text("Сообщение не найдено.")
            await state_store.clear_state(user_id)
            return

        await state_store.clear_state(user_id)
        recipient_id = result.reply.to_user_id
        recipient = await user_repo.get_by_id(recipient_id)

    await update.message.reply_text("Ответ отправлен.")

    if recipient is not None:
        notify_text = f"Вам ответили на валентинку:\n{text[:200]}"
        try:
            await context.bot.send_message(chat_id=recipient.telegram_user_id, text=notify_text)
        except Exception as exc:  # pragma: no cover - notification failures are non-critical
            logger.warning("Failed to notify reply recipient %s: %s", recipient.telegram_user_id, exc)
