from aiogram import Router, types
from aiogram.filters import Command
from database.settingsdata import add_to_table, get_state_ai
from config.confpaypass import get_paypass
from services.logging import logs_bot
from services.openai_services import new_message
from datetime import datetime


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
    try:
        # Получаем текущее состояние пользователя
        chat_id = message.from_user.id
        data_gpt = await get_state_ai(chat_id)
        
        # Форматируем данные для вывода
        state_info = "Текущее состояние:\n\n"
        for model, count in data_gpt.items():
            state_info += f"{model}: {count}\n"
        
        await message.answer(state_info)
    except Exception as e:
        await logs_bot("error", f"Error in state command: {e}")
        await message.answer(f"Ошибка: {str(e)}")


@router.message(Command("allboost"))
async def command_allboost(message: types.Message):
    try:
        chat_id = message.from_user.id
        
        # Получаем текущие данные пользователя
        existing_data = await get_state_ai(chat_id)
        
        # Получаем данные о всех моделях из Pro подписки
        paypass = get_paypass("Pro")
        paypass_dict = paypass.dict()
        
        # Создаем словарь с лимитами 100 для всех моделей
        limits = {}
        
        # Маппинг имен моделей из PayPass в API-имена
        model_mapping = {
            'gpt_4o_mini': 'gpt-4o-mini',
            'gpt_4o': 'gpt-4o',
            'claude_3_5_sonnet': 'claude-3-5-sonnet',
            'claude_3_haiku': 'claude-3-haiku',
            'gemini_1_5_flash': 'gemini-1.5-flash',
            'deepseek_v3': 'deepseek-v3',
            'deepseek_r1': 'deepseek-r1',
            'o1_mini': 'o1-mini',
            'o1': 'o1',
            'tts': 'tts',
            'tts_hd': 'tts-hd',
            'o3_mini': 'o3-mini'
        }
        
        # Заполняем словарь лимитов
        for model_name, api_name in model_mapping.items():
            if model_name in paypass_dict and model_name not in ["image_recognition", "speech_to_text"]:
                current_value = existing_data.get(api_name, 0)
                limits[api_name] = current_value + 100
        
        # Создаем или обновляем запись пользователя
        user_data = {
            "chatId": chat_id,
            "dataGpt": limits,
            "updated_at": datetime.now().replace(second=0, microsecond=0)
        }
        
        # Сохраняем в базу данных
        await add_to_table("StaticAIUsers", user_data)
        
        await new_message(message, "✅ Все модели AI активированы с лимитом +100 запросов!", None) 
        await logs_bot("info", f"User {chat_id} activated all models with +100 requests")
        
    except Exception as e:
        await new_message(message, f"⚠️ Произошла ошибка при активации моделей: {str(e)}", None)
        await logs_bot("error", f"Error in allboost command: {str(e)}")
