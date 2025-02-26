from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from Messages.settingsmsg import new_message, update_message
from Messages.utils import escape_markdown
from services.logging import logs_bot
from services.openai_services import OpenAIService
from Messages.inlinebutton import tts_quality_menu
from Messages.settingsmsg import answer_voice
import os

router = Router(name=__name__)
openai_service = OpenAIService()

# Определение состояний для FSM
class TTSStates(StatesGroup):
    waiting_for_quality = State()  # Ожидание выбора качества (HD или обычное)
    waiting_for_voice = State()    # Ожидание выбора голоса
    waiting_for_text = State()     # Ожидание ввода текста для озвучивания

# Голоса для TTS
TTS_VOICES = {
    "alloy": "Alloy (нейтральный)",
    "echo": "Echo (мужской)",
    "fable": "Fable (британский)",
    "onyx": "Onyx (глубокий)",
    "nova": "Nova (женский)",
    "shimmer": "Shimmer (мелодичный)"
}

# Обработчик кнопки "Генерация речи"
@router.callback_query(F.data == "TSSGenerat")
async def tts_start(call: CallbackQuery, state: FSMContext):
    """Начало процесса генерации речи"""
    try:
        # Создаем клавиатуру для выбора качества
        
        
        # Отправляем сообщение с выбором качества
        await update_message(
            call.message,
            "Выберите качество генерации речи:",
            await tts_quality_menu()
        )
        
        # Устанавливаем состояние ожидания выбора качества
        await state.set_state(TTSStates.waiting_for_quality)
        
    except Exception as e:
        await logs_bot("error", f"Error in tts_start: {str(e)}")
        await call.answer("Произошла ошибка при запуске генерации речи")

# Обработчик выбора качества
@router.callback_query(TTSStates.waiting_for_quality, F.data.startswith("tts_quality_"))
async def tts_select_quality(call: CallbackQuery, state: FSMContext):
    """Обработка выбора качества и предложение выбрать голос"""
    try:
        # Определяем выбранное качество
        quality = "tts_hd" if call.data == "tts_quality_hd" else "tts"
        
        # Сохраняем выбранное качество в состоянии
        await state.update_data(quality=quality)
        
        # Создаем клавиатуру для выбора голоса
        keyboard = []
        row = []
        
        for voice_id, voice_name in TTS_VOICES.items():
            # Добавляем кнопку для каждого голоса
            button = types.InlineKeyboardButton(
                text=voice_name,
                callback_data=f"tts_voice_{voice_id}"
            )
            
            row.append(button)
            if len(row) == 2:  # По две кнопки в ряду
                keyboard.append(row)
                row = []
        
        # Добавляем оставшиеся кнопки, если есть
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку возврата
        keyboard.append([
            types.InlineKeyboardButton(text="⬅️ Вернуться к выбору качества", callback_data="TSSGenerat")
        ])
        
        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Отправляем сообщение с выбором голоса
        await update_message(
            call.message,
            f"Выбрано {'HD' if quality == 'tts_hd' else 'стандартное'} качество\\. Теперь выберите голос:",
            markup
        )
        
        # Устанавливаем состояние ожидания выбора голоса
        await state.set_state(TTSStates.waiting_for_voice)
        
    except Exception as e:
        await logs_bot("error", f"Error in tts_select_quality: {str(e)}")
        await call.answer("Произошла ошибка при выборе качества")

# Обработчик выбора голоса
@router.callback_query(TTSStates.waiting_for_voice, F.data.startswith("tts_voice_"))
async def tts_select_voice(call: CallbackQuery, state: FSMContext):
    """Обработка выбора голоса и запрос текста для озвучивания"""
    try:
        # Извлекаем ID голоса из callback_data
        voice_id = call.data.replace("tts_voice_", "")
        
        # Сохраняем выбранный голос в состоянии
        await state.update_data(voice=voice_id)
        
        # Получаем данные о выбранном качестве
        data = await state.get_data()
        quality = data.get("quality", "tts")
        
        # Создаем клавиатуру с примером и возвратом
        keyboard = [
            [
                types.InlineKeyboardButton(
                    text="🔊 Пример: 'Привет, мир!'", 
                    callback_data="tts_example"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Вернуться к выбору голоса", 
                    callback_data=f"tts_quality_{'hd' if quality == 'tts_hd' else 'standard'}"
                )
            ]
        ]
        markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Отправляем сообщение с инструкцией ввести текст
        voice_name = TTS_VOICES.get(voice_id, voice_id)
        await update_message(
            call.message,
            f"Выбран голос: *{escape_markdown(voice_name)}*\\.\n\n"
            f"Теперь введите текст, который хотите озвучить, или нажмите кнопку для прослушивания примера\\.",
            markup
        )
        
        # Устанавливаем состояние ожидания ввода текста
        await state.set_state(TTSStates.waiting_for_text)
        
    except Exception as e:
        await logs_bot("error", f"Error in tts_select_voice: {str(e)}")
        await call.answer("Произошла ошибка при выборе голоса")

# Обработчик примера
@router.callback_query(TTSStates.waiting_for_text, F.data == "tts_example")
async def tts_example(call: CallbackQuery, state: FSMContext):
    """Генерация примера голосового сообщения"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        quality = data.get("quality", "tts")
        voice = data.get("voice", "alloy")
        
        # Отправляем сообщение о генерации
        await call.answer("Генерация примера...")
        
        # Генерируем голосовое сообщение
        await generate_voice_message(
            call.message, 
            "Привет, мир!", 
            voice, 
            quality
        )
        
    except Exception as e:
        await logs_bot("error", f"Error in tts_example: {str(e)}")
        await call.answer("Произошла ошибка при генерации примера")

# Обработчик ввода текста
@router.message(TTSStates.waiting_for_text)
async def tts_process_text(message: Message, state: FSMContext):
    """Обработка введенного текста и генерация голосового сообщения"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        quality = data.get("quality", "tts")
        voice = data.get("voice", "alloy")
        
        # Проверяем, что текст не пустой
        if not message.text or len(message.text.strip()) == 0:
            await new_message(
                message, 
                "Пожалуйста, введите текст для озвучивания\\."
            )
            return
        
        # Проверяем длину текста
        if len(message.text) > 1000:
            await new_message(
                message, 
                "Текст слишком длинный\\. Максимальная длина: 1000 символов\\."
            )
            return
        
        # Генерируем голосовое сообщение
        await generate_voice_message(
            message, 
            message.text, 
            voice, 
            quality
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        await logs_bot("error", f"Error in tts_process_text: {str(e)}")
        await new_message(
            message, 
            "Произошла ошибка при генерации голосового сообщения\\."
        )

async def generate_voice_message(message: Message, text: str, voice: str, model: str = "tts"):
    """
    Генерирует голосовое сообщение с использованием OpenAI API
    
    Args:
        message: Объект сообщения для ответа
        text: Текст для озвучивания
        voice: Идентификатор голоса (alloy, echo, fable, onyx, nova, shimmer)
        model: Модель TTS (tts или tts_hd)
    """
    try:
        # Отправляем индикатор "печатает..."
        await message.bot.send_chat_action(
            chat_id=message.chat.id, 
            action="record_voice"
        )
        
        # Генерируем голосовое сообщение через ProxyAPI
        audio_path = await openai_service.text_to_speech(text, voice, model)
        
        if not audio_path or not os.path.exists(audio_path):
            await logs_bot("error", f"Audio file not found: {audio_path}")
            await new_message(
                message, 
                "Не удалось сгенерировать голосовое сообщение\\. Попробуйте позже\\."
            )
            return
        
        # Отправляем голосовое сообщение
        try:
            # Используем FSInputFile вместо открытия файла напрямую
            from aiogram.types import FSInputFile
            voice_file = FSInputFile(audio_path)
            
            # Экранируем специальные символы в подписи
            voice_name = TTS_VOICES.get(voice, voice)
            caption = f"🔊 Голос: {voice_name}"
            
            # Отправляем без использования Markdown
            await answer_voice(message, voice_file, caption)
            
            # Удаляем временный файл
            try:
                os.remove(audio_path)
            except Exception as e:
                await logs_bot("warning", f"Failed to remove temp file {audio_path}: {e}")
        except Exception as send_error:
            await logs_bot("error", f"Error sending voice message: {send_error}")
            await new_message(
                message, 
                "Ошибка при отправке голосового сообщения\\."
            )
        
    except Exception as e:
        await logs_bot("error", f"Error in generate_voice_message: {str(e)}")
        await new_message(
            message, 
            "Произошла ошибка при генерации голосового сообщения\\."
        )
