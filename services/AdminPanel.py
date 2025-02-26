from aiogram import Router, types
from aiogram.filters import Command
from database.settingsdata import add_to_table
from config.confpaypass import get_paypass
from services.logging import logs_bot
from services.openai_services import new_message


router = Router(name=__name__)

# команды для админки (работают)

@router.message(Command("adminpanel"))
async def command_start(message: types.Message):
    await message.answer("Panel")


@router.message(Command("reset"))
async def command_reset(message: types.Message):
    await message.answer("Reset")


@router.message(Command("state"))
async def command_state(message: types.Message):
    await message.answer("State")



@router.message(Command("allboost"))
async def command_allboost(message: types.Message):
    try:
        # Получаем данные о всех моделях из NoBase подписки
        paypass = get_paypass("Pro")
        paypass_dict = paypass.dict()
        
        # Создаем словарь с лимитами 100 для всех моделей
        limits = {}
        for model_name in paypass_dict:
            if model_name not in ["image_recognition", "speech_to_text"]:  # Пропускаем флаги
                # Преобразуем имена моделей в API-имена
                api_name = model_name.replace("_", "-")
                print(api_name)
                if api_name == "gemini-1-5-flash":
                    api_name = "gemini-1.5-flash"
                limits[api_name] = 100
        
        # Обновляем данные пользователя
        user_data = {
            "chatId": message.from_user.id,
            "dataGpt": limits
        }
        
        # Сохраняем в базу данных
        await add_to_table("StaticAIUsers", user_data)
        
        await new_message(message, "✅ Все модели AI активированы с лимитом 100 запросов!", None) 
        
        await logs_bot("info", f"User {message.from_user.id} activated all models with 100 requests")
        
    except Exception as e:
        await new_message(message, "⚠️ Произошла ошибка при активации моделей. Попробуйте позже.", None)
        await logs_bot("error", f"Error in allboost command: {str(e)}")
