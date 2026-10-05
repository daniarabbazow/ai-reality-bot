from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.content import Category, Content, ContentType


class TypeCB(CallbackData, prefix="typ"):
    type_id: str


class CategoryCB(CallbackData, prefix="cat"):
    category_id: str


class LevelCB(CallbackData, prefix="lvl"):
    category_id: str
    level: int


class AnswerCB(CallbackData, prefix="ans"):
    session_id: str
    index: int
    answer: str  # "real" | "ai"


class NavCB(CallbackData, prefix="nav"):
    # "menu" | "types" | "categories" | "retry" | "next" | "stats"
    # | "reveal_ask" | "reveal" | "reveal_back"
    action: str
    type_id: str = ""
    category_id: str = ""
    level: int = 0


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📂 Категории", callback_data=NavCB(action="types").pack())
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=NavCB(action="stats").pack())
    )
    return builder.as_markup()


def types_keyboard(content: Content) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for content_type in content.types:
        builder.row(
            InlineKeyboardButton(
                text=content_type.title,
                callback_data=TypeCB(type_id=content_type.id).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=NavCB(action="menu").pack())
    )
    return builder.as_markup()


def categories_keyboard(content_type: ContentType) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in content_type.categories:
        builder.row(
            InlineKeyboardButton(
                text=category.title,
                callback_data=CategoryCB(category_id=category.id).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=NavCB(action="types").pack())
    )
    return builder.as_markup()


def stats_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=NavCB(action="menu").pack())
    )
    return builder.as_markup()


def levels_keyboard(category: Category, type_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for level in sorted(category.levels, key=lambda l: l.level):
        builder.row(
            InlineKeyboardButton(
                text=level.title,
                callback_data=LevelCB(category_id=category.id, level=level.level).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ К категориям",
            callback_data=NavCB(action="categories", type_id=type_id).pack(),
        )
    )
    return builder.as_markup()


def answer_keyboard(session_id: str, index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🧑 Real",
            callback_data=AnswerCB(session_id=session_id, index=index, answer="real").pack(),
        ),
        InlineKeyboardButton(
            text="🤖 AI",
            callback_data=AnswerCB(session_id=session_id, index=index, answer="ai").pack(),
        ),
    )
    return builder.as_markup()


def result_keyboard(
    *,
    category_id: str,
    level: int,
    type_id: str,
    all_correct: bool,
    is_last_level: bool,
    offer_reveal: bool = True,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not all_correct:
        builder.row(
            InlineKeyboardButton(
                text="🔁 Пройти заново",
                callback_data=NavCB(
                    action="retry", category_id=category_id, level=level
                ).pack(),
            )
        )
        if offer_reveal:
            builder.row(
                InlineKeyboardButton(
                    text="👀 Посмотреть правильные ответы",
                    callback_data=NavCB(
                        action="reveal_ask", category_id=category_id, level=level
                    ).pack(),
                )
            )
    if all_correct and not is_last_level:
        builder.row(
            InlineKeyboardButton(
                text="➡️ К следующему уровню",
                callback_data=NavCB(
                    action="next", category_id=category_id, level=level
                ).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="📋 К уровням категории",
            callback_data=CategoryCB(category_id=category_id).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📂 Вернуться к категориям",
            callback_data=NavCB(action="categories", type_id=type_id).pack(),
        )
    )
    return builder.as_markup()


def reveal_confirm_keyboard(category_id: str, level: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да",
            callback_data=NavCB(action="reveal", category_id=category_id, level=level).pack(),
        ),
        InlineKeyboardButton(
            text="⬅️ Назад", callback_data=NavCB(action="reveal_back").pack()
        ),
    )
    return builder.as_markup()


def error_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📂 К типам", callback_data=NavCB(action="types").pack())
    )
    return builder.as_markup()
