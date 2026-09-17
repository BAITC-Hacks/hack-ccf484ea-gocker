import argparse
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from app.bot.bot import create_bot_and_dispatcher
from app.config import settings
from app.database import init_db
from app.web.routes import setup_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("finance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.db_path)
    yield


def create_fastapi_app() -> FastAPI:
    app = FastAPI(title="Finance Student App", lifespan=lifespan)
    setup_web_app(app)
    return app


async def run_bot_polling():
    if not settings.bot_token:
        logger.warning(
            "BOT_TOKEN не задан в переменных окружения или .env файле. Бот в Telegram не запущен."
        )
        return

    logger.info("Запуск Telegram-бота...")
    bot, dp = create_bot_and_dispatcher()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_web_server():
    app = create_fastapi_app()
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Веб-сервер и Mini App запущены на http://%s:%s", settings.host, settings.port)
    await server.serve()


async def async_main():
    parser = argparse.ArgumentParser(description="Учёт личных расходов студента")
    parser.add_argument("--web-only", action="store_true", help="Запустить только веб-интерфейс")
    parser.add_argument("--bot-only", action="store_true", help="Запустить только Telegram бота")
    args = parser.parse_args()

    await init_db(settings.db_path)

    if args.web_only:
        await run_web_server()
    elif args.bot_only:
        if not settings.bot_token:
            logger.error("Для режима --bot-only необходимо указать BOT_TOKEN в .env")
            sys.exit(1)
        await run_bot_polling()
    else:
        tasks = [run_web_server()]
        if settings.bot_token:
            tasks.append(run_bot_polling())
        else:
            logger.info("BOT_TOKEN не указан. Запускается полнофункциональный веб-интерфейс на порту %s.", settings.port)
        await asyncio.gather(*tasks)


def main():
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Приложение остановлено.")


if __name__ == "__main__":
    main()
