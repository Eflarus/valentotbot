from __future__ import annotations

from typing import Any, Mapping

Translations = Mapping[str, Mapping[str, str]]


MESSAGES: Translations = {
    "greeting_menu": {
        "ru": "Привет! Главное меню:\n• Мои ссылки (/links)\n• Мои сообщения (/messages)\n• Статистика (/stats)\n• Настройки\n• Помощь",
        "en": "Hi! Main menu:\n• My links (/links)\n• My messages (/messages)\n• Statistics (/stats)\n• Settings\n• Help",
    },
    "invalid_link": {
        "ru": "Ссылка недействительна или выключена.",
        "en": "The link is invalid or disabled.",
    },
    "send_prompt": {
        "ru": "Отправь анонимное сообщение.",
        "en": "Send an anonymous message.",
    },
    "reveal_choice": {
        "ru": "Выбери режим раскрытия автора:",
        "en": "Choose author reveal mode:",
    },
    "choose_option": {
        "ru": "Выберите один из вариантов.",
        "en": "Choose one of the options.",
    },
    "enter_text": {
        "ru": "Введите текст сообщения (1–2000 символов).",
        "en": "Enter message text (1–2000 chars).",
    },
    "text_only": {
        "ru": "Доступны только текстовые сообщения.",
        "en": "Only text messages are allowed.",
    },
    "message_too_short": {
        "ru": "Сообщение должно быть от 1 до 2000 символов.",
        "en": "Message must be 1–2000 characters.",
    },
    "session_expired": {
        "ru": "Сессия устарела, начните заново по ссылке.",
        "en": "Session expired, start again via the link.",
    },
    "message_sent": {
        "ru": "Ваше сообщение отправлено!",
        "en": "Your message has been sent!",
    },
    "reply_prompt": {
        "ru": "Введите текст ответа (1–2000 символов).",
        "en": "Enter reply text (1–2000 chars).",
    },
    "reply_sent": {
        "ru": "Ответ отправлен.",
        "en": "Reply sent.",
    },
    "no_messages": {
        "ru": "Сообщений не найдено по выбранным фильтрам.",
        "en": "No messages found for selected filters.",
    },
    "user_not_found": {
        "ru": "Пользователь не найден.",
        "en": "User not found.",
    },
    "link_not_found": {
        "ru": "Ссылка не найдена или недоступна.",
        "en": "Link not found or not available.",
    },
    "links_header": {
        "ru": "Мои ссылки:",
        "en": "My links:",
    },
    "no_links": {
        "ru": "У вас нет ссылок. Нажмите 'Создать ссылку'.",
        "en": "You have no links. Press 'Create link'.",
    },
    "enter_link_label": {
        "ru": "Введите название ссылки (label).",
        "en": "Enter link label.",
    },
    "enter_link_prompt": {
        "ru": "Введите промпт (опционально) или отправьте '-' чтобы пропустить.",
        "en": "Enter prompt (optional) or send '-' to skip.",
    },
    "link_created": {
        "ru": "Ссылка создана:",
        "en": "Link created:",
    },
    "link_toggled_on": {
        "ru": "Ссылка включена.",
        "en": "Link enabled.",
    },
    "link_toggled_off": {
        "ru": "Ссылка выключена.",
        "en": "Link disabled.",
    },
    "stats_header": {
        "ru": "Статистика:",
        "en": "Statistics:",
    },
    "stats_links_none": {
        "ru": "По ссылкам: нет данных",
        "en": "Per-link: no data",
    },
}


def translate(key: str, lang: str, **kwargs: Any) -> str:
    entry = MESSAGES.get(key, {})
    text = entry.get(lang) or entry.get("ru") or ""
    if kwargs:
        return text.format(**kwargs)
    return text


def resolve_lang(language_code: str | None) -> str:
    if language_code and language_code.lower().startswith("en"):
        return "en"
    return "ru"
