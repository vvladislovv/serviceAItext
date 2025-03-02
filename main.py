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
from handlers.subscription_manager import router as subscription_manager
config = get_config()

async def on_routers(dp: Dispatcher):
    """
    Подключает все роутеры к диспетчеру бота.
    
    Args:
        dp (Dispatcher): Диспетчер бота Telegram.
    """
    routers = [
            admin_router,
            chat_router,
            common_router,
            voice_router,
            subscription_manager
        ]
        
    for router in routers:
        dp.include_router(router)
    
    await logs_bot("info", "All routers have been successfully connected")

async def main() -> None:
    """
    Основная функция для запуска бота и FastAPI.
    
    Инициализирует базу данных, настраивает и запускает бота Telegram
    и FastAPI сервер в асинхронном режиме.
    """
    try:
        # Инициализация базы данных
        await init_db()
        await logs_bot("info", "Database initialized successfully")

        # Инициализация бота
        bot = Bot(
            token=config.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        dp = Dispatcher()
        
        # Подключаем роутеры
        await on_routers(dp)
        await bot.delete_webhook(drop_pending_updates=True)
        await logs_bot("info", "Bot webhook deleted successfully")

        # Запускаем все сервисы асинхронно
        async with asyncio.TaskGroup() as tg:
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
    """
    Точка входа в приложение.
    Запускает основную функцию и обрабатывает возможные исключения.
    """
    try:
        asyncio.run(main())
    except Exception as Error:
        asyncio.run(logs_bot("error", f"Bot work stopped due to error: {Error}"))

