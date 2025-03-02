import asyncio
import logging
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

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
        logger.info("Инициализация базы данных...")
        await init_db()
        logger.info("База данных успешно инициализирована")

        logger.info("Инициализация бота...")
        bot = Bot(
            token=config.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        dp = Dispatcher()
        
        logger.info("Подключение роутеров...")
        await on_routers(dp)
        
        logger.info("Запуск бота и FastAPI...")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(dp.start_polling(bot))
            tg.create_task(run_fastapi())
        
        logger.info("Приложение успешно запущено")

    except Exception as e:
        logger.error(f"Ошибка приложения: {e}")
    finally:
        logger.info("Закрытие сессии бота...")
        await bot.session.close()
        logger.info("Сессия бота закрыта")

if __name__ == "__main__":
    """
    Точка входа в приложение.
    Запускает основную функцию и обрабатывает возможные исключения.
    """
    try:
        logger.info("Запуск приложения...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено вручную")
    except Exception as Error:
        logger.error(f"Работа приложения остановлена из-за ошибки: {Error}")

