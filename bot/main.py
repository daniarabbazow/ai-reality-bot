import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot import db
from bot.config import ConfigError, load_config
from bot.content import ContentError, load_content
from bot.handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        config = load_config()
    except ConfigError as e:
        logger.error("Ошибка конфигурации: %s", e)
        sys.exit(1)

    try:
        content = load_content()
    except ContentError as e:
        logger.error("Ошибка в content.json: %s", e)
        sys.exit(1)

    await db.init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    dispatcher["content"] = content

    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
