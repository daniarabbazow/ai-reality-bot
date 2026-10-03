import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from bot import db
from bot.config import ConfigError, load_config
from bot.content import ContentError, load_content
from bot.handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _start_health_server() -> None:
    """Открывает HTTP-порт, чтобы хостинг (Render и т.п.) считал сервис
    живым и чтобы внешний пингер (UptimeRobot) мог не давать ему засыпать."""
    port = os.getenv("PORT")
    if not port:
        return

    app = web.Application()
    app.router.add_get("/", lambda _request: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(port))
    await site.start()
    logger.info("Health-check сервер слушает порт %s", port)


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

    await _start_health_server()

    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
