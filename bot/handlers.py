import asyncio
import logging
import time
import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot import db
from bot.content import BASE_DIR, Content
from bot.keyboards import (
    AnswerCB,
    CategoryCB,
    LevelCB,
    NavCB,
    answer_keyboard,
    categories_keyboard,
    error_keyboard,
    levels_keyboard,
    main_menu_keyboard,
    result_keyboard,
    stats_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()

MAIN_MENU_TEXT = (
    "👋 Привет! Это <b>AI REALITY</b> — игра, где нужно отличить фото или стих, "
    "сделанный человеком, от того, что сгенерировала нейросеть.\n"
    "Выбери раздел:"
)

CATEGORIES_TEXT = "Выбери категорию:"

# Serializes answer handling per chat so a near-simultaneous double tap
# on the same photo can't be counted twice.
_locks: dict[int, asyncio.Lock] = {}


def _lock_for(chat_id: int) -> asyncio.Lock:
    lock = _locks.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[chat_id] = lock
    return lock


class GameStates(StatesGroup):
    playing = State()
    finished = State()


def _new_session_id() -> str:
    return uuid.uuid4().hex[:6]


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, content: Content) -> None:
    await state.clear()
    await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(NavCB.filter(F.action == "menu"))
async def on_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(CategoryCB.filter())
async def on_category_chosen(
    callback: CallbackQuery, callback_data: CategoryCB, state: FSMContext, content: Content
) -> None:
    category = content.get_category(callback_data.category_id)
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await state.clear()
    text = f"{category.title}\nВыбери уровень:"
    await callback.message.edit_text(text, reply_markup=levels_keyboard(category))
    await callback.answer()


@router.callback_query(LevelCB.filter())
async def on_level_chosen(
    callback: CallbackQuery,
    callback_data: LevelCB,
    state: FSMContext,
    content: Content,
    bot: Bot,
) -> None:
    await callback.answer()
    await _start_level(
        bot=bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        category_id=callback_data.category_id,
        level=callback_data.level,
    )


@router.callback_query(NavCB.filter(F.action == "categories"))
async def on_back_to_categories(
    callback: CallbackQuery, state: FSMContext, content: Content
) -> None:
    await state.clear()
    try:
        await callback.message.edit_text(CATEGORIES_TEXT, reply_markup=categories_keyboard(content))
    except Exception:
        await callback.message.answer(CATEGORIES_TEXT, reply_markup=categories_keyboard(content))
    await callback.answer()


@router.callback_query(NavCB.filter(F.action == "stats"))
async def on_stats(callback: CallbackQuery, content: Content) -> None:
    stats = await db.get_user_stats(callback.from_user.id)

    lines = ["📊 <b>Твоя статистика по категориям:</b>", ""]
    for category in content.categories:
        total, correct = stats.get(category.id, (0, 0))
        if total:
            pct = round(correct / total * 100)
            lines.append(f"{category.title}: <b>{pct}%</b> ({correct} из {total})")
        else:
            lines.append(f"{category.title}: ещё нет ответов")

    text = "\n".join(lines)
    try:
        await callback.message.edit_text(text, reply_markup=stats_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=stats_keyboard())
    await callback.answer()


@router.callback_query(NavCB.filter(F.action.in_({"retry", "next"})))
async def on_result_action(
    callback: CallbackQuery,
    callback_data: NavCB,
    state: FSMContext,
    content: Content,
    bot: Bot,
) -> None:
    category_id = callback_data.category_id
    level = callback_data.level

    if callback_data.action == "next":
        next_level = content.get_next_level(category_id, level)
        if next_level is None:
            await callback.answer("Следующего уровня пока нет", show_alert=True)
            return
        level = next_level.level

    await callback.answer()
    await _start_level(
        bot=bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        category_id=category_id,
        level=level,
    )


async def _start_level(
    *, bot: Bot, chat_id: int, state: FSMContext, content: Content, category_id: str, level: int
) -> None:
    level_obj = content.get_level(category_id, level)
    if level_obj is None:
        await bot.send_message(chat_id, "Уровень не найден 🙁", reply_markup=error_keyboard())
        return

    session_id = _new_session_id()
    await state.set_state(GameStates.playing)
    await state.set_data(
        {
            "session_id": session_id,
            "category_id": category_id,
            "level": level,
            "index": 0,
            "correct": 0,
            "answered_index": -1,
        }
    )
    await _send_question(bot=bot, chat_id=chat_id, state=state, content=content)


_CAPTION_PREFIX = {"photo": "Фото", "text": "Стих"}


async def _send_question(
    *, bot: Bot, chat_id: int, state: FSMContext, content: Content
) -> None:
    data = await state.get_data()
    category_id = data["category_id"]
    level = data["level"]
    index = data["index"]

    level_obj = content.get_level(category_id, level)
    items = level_obj.items
    item = items[index]
    total = len(items)
    caption = f"{_CAPTION_PREFIX[item.type]} {index + 1}/{total}"
    markup = answer_keyboard(data["session_id"], index)

    try:
        if item.type == "photo":
            cached_file_id = await db.get_cached_file_id(item.id)
            photo = cached_file_id or FSInputFile(BASE_DIR / item.file)
            sent = await bot.send_photo(
                chat_id, photo=photo, caption=caption, reply_markup=markup
            )

            if not cached_file_id:
                file_id = sent.photo[-1].file_id
                await db.cache_file_id(item.id, file_id)
        else:
            text = f"{caption}\n\n{item.text}"
            await bot.send_message(chat_id, text, reply_markup=markup, parse_mode=None)
    except Exception:
        logger.exception("Не удалось отправить элемент %s", item.id)
        await bot.send_message(
            chat_id,
            "Не получилось загрузить вопрос, попробуй ещё раз",
            reply_markup=error_keyboard(),
        )
        return

    await state.update_data(sent_at=time.time())


@router.callback_query(AnswerCB.filter())
async def on_answer(
    callback: CallbackQuery,
    callback_data: AnswerCB,
    state: FSMContext,
    content: Content,
    bot: Bot,
) -> None:
    chat_id = callback.message.chat.id

    async with _lock_for(chat_id):
        data = await state.get_data()
        current_state = await state.get_state()

        if (
            current_state != GameStates.playing.state
            or data.get("session_id") != callback_data.session_id
            or data.get("index") != callback_data.index
            or callback_data.index <= data.get("answered_index", -1)
        ):
            await callback.answer("Эта игра уже завершена 🙂", show_alert=False)
            return

        await state.update_data(answered_index=callback_data.index)

        category_id = data["category_id"]
        level = data["level"]
        index = data["index"]
        level_obj = content.get_level(category_id, level)
        item = level_obj.items[index]

        is_correct = callback_data.answer == item.answer
        sent_at = data.get("sent_at")
        response_time = (time.time() - sent_at) if sent_at else None

        await db.log_answer(
            user_id=callback.from_user.id,
            session_id=callback_data.session_id,
            category_id=category_id,
            level=level,
            item_id=item.id,
            user_answer=callback_data.answer,
            is_correct=is_correct,
            response_time_sec=response_time,
        )

        correct = data["correct"] + (1 if is_correct else 0)
        await state.update_data(correct=correct)

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.warning("Не удалось убрать клавиатуру у сообщения")

        await callback.answer()

        total = len(level_obj.items)
        if index + 1 < total:
            await state.update_data(index=index + 1)
            await _send_question(bot=bot, chat_id=chat_id, state=state, content=content)
        else:
            await _finish_level(
                bot=bot,
                chat_id=chat_id,
                state=state,
                content=content,
                correct=correct,
                total=total,
            )


async def _finish_level(
    *,
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    content: Content,
    correct: int,
    total: int,
) -> None:
    data = await state.get_data()
    category_id = data["category_id"]
    level = data["level"]
    level_obj = content.get_level(category_id, level)

    all_correct = correct == total
    is_last_level = content.is_last_level(category_id, level)

    if all_correct:
        lines = [
            f"🏁 {level_obj.title} пройден!",
            f"Верных ответов: <b>{correct} из {total}</b>",
            "🎉 Идеально! Ни одной ошибки.",
        ]
    else:
        lines = [
            f"🚫 {level_obj.title} не пройден.",
            f"Верных ответов: <b>{correct} из {total}</b>",
            "Чтобы пройти уровень, нужно ответить правильно на все вопросы — без единой ошибки.",
        ]
    if is_last_level:
        lines.append("Это был последний уровень в категории — скоро добавим новые!")

    await state.set_state(GameStates.finished)
    await state.set_data({"category_id": category_id, "level": level})

    await bot.send_message(
        chat_id,
        "\n".join(lines),
        reply_markup=result_keyboard(
            category_id=category_id,
            level=level,
            all_correct=all_correct,
            is_last_level=is_last_level,
        ),
    )
