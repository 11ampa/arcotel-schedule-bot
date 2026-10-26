#!/usr/bin/env python3
"""точка входа telegram-бота расписания акта (ф) спбгут."""
from __future__ import annotations

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import BOT_TOKEN
from bot.handlers import menu, inline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("arcotel_bot")


async def setup_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="главное меню расписания"),
        BotCommand(command="schedule", description="показать расписание"),
        BotCommand(command="help", description="справка и возможности"),
        BotCommand(command="clean", description="удалить сообщение"),
    ]
    await bot.set_my_commands(commands)


async def main() -> int:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. укажите токен в .env файле.")
        return 1

    logger.info("запуск бота расписания arcotel...")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(inline.router)

    await setup_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("бот успешно подключен к telegram api и слушает события.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except (KeyboardInterrupt, SystemExit):
        logger.info("бот остановлен.")
