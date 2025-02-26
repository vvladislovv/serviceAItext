import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from services.app_api import run_fastapi 
from services.logging import logs_bot

from config.config import get_config
from database.settingsdata import init_db
from handlers.chat import router as chat_router
from handlers.common import router as common_router
from services.AdminPanel import router as admin_router
from handlers.voice_chat import router as voice_router
config = get_config()

async def on_routers(dp: Dispatcher):
    routers = [
            admin_router,
            chat_router,
            common_router,
            voice_router
        ]
        
    for router in routers:
        dp.include_router(router)

async def main() -> None:
    """Основная функция для запуска бота и FastAPI."""
    await init_db()

    try:
        # Инициализация бота
        bot = Bot(
            token=config.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        dp = Dispatcher()
        
        # Подключаем роутер
        await on_routers(dp)
        await bot.delete_webhook(drop_pending_updates=True)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(init_db())
            tg.create_task(dp.start_polling(bot))
            tg.create_task(run_fastapi())
        
        await logs_bot("info", "Bot is ready to work")

    except Exception as e:
        await logs_bot("error", f"Application error: {e}")
    finally:
        # Закрываем сессию бота при завершении
        await bot.session.close()
        await logs_bot("info", "Bot session closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as Error:
        asyncio.run(logs_bot("error", f"Bot work off.. {Error}"))

