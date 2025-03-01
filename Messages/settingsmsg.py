from aiogram.types import InlineKeyboardMarkup, Message
from services.logging import logs_bot
from Messages.utils import escape_markdown, process_ai_markdown
from aiogram.enums import ParseMode
import asyncio

async def new_message(message: Message, text: str, keyboard=None) -> Message:
    """
    Отправляет новое сообщение с текстом и опциональной клавиатурой.

    Args:
        message: Объект сообщения.
        text: Текст сообщения.
        keyboard: Клавиатура (InlineKeyboardMarkup, список или объект с методом as_markup).

    Returns:
        Объект отправленного сообщения.
    """
    try:
        # Экранируем текст для MarkdownV2
        escaped_text = escape_markdown(text)
        
        # Преобразуем клавиатуру
        markup = await prepare_keyboard(keyboard)
        
        try:
            # Пробуем отправить с MarkdownV2
            return await message.answer(
                text=escaped_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=markup
            )
        except Exception as md_error:
            await logs_bot("warning", f"MarkdownV2 formatting error: {md_error}")
            # Если не получилось, отправляем без форматирования
            return await message.answer(
                text=text,
                reply_markup=markup
            )
            
    except Exception as e:
        await logs_bot("error", f"Error in new_message: {e}")
        # Отправляем более информативное сообщение об ошибке
        print(e)
        return await message.answer("⚠️ Произошла ошибка при обработке запроса\\. Попробуйте позже\\.")

async def update_message(message: Message, text: str, keyboard=None) -> bool:
    """Обновляет существующее сообщение с новым текстом и опциональной клавиатурой."""
    try:
        # Обрабатываем форматирование для Telegram
        formatted_text = process_ai_markdown(text)
        
        markup = await prepare_keyboard(keyboard)
        
        try:
            # Пробуем отправить с MarkdownV2
            await message.edit_text(
                text=formatted_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=markup
            )
            return True
        except Exception as md_error:
            # Логируем ошибку для отладки
            await logs_bot("warning", f"MarkdownV2 formatting error: {md_error}")
            
            # Если не получилось с форматированием, пробуем без него
            try:
                await message.edit_text(
                    text=text,
                    reply_markup=markup
                )
                return True
            except Exception as plain_error:
                await logs_bot("error", f"Failed to send message without formatting: {plain_error}")
                return False
            
    except Exception as e:
        if "message is not modified" not in str(e):
            await logs_bot("error", f"Error in update_message: {e}")
        return False

async def prepare_keyboard(keyboard):
    """Подготовка клавиатуры"""
    if not keyboard:
        return None
        
    if isinstance(keyboard, InlineKeyboardMarkup):
        return keyboard
    elif isinstance(keyboard, list):
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    elif hasattr(keyboard, "as_markup"):
        return keyboard.as_markup()
    
    await logs_bot("warning", f"Unsupported keyboard type: {type(keyboard)}")
    return None


async def answer_voice(message, audio, caption):
    """Send voice message with caption"""
    return await message.answer_voice(audio, caption=caption)

async def send_typing_action(message: Message, action_type: str):
    """Отправка действия "печатает"""
    await message.bot.send_chat_action(
        chat_id=message.chat.id, 
        action=action_type
    )

async def maintain_typing_status(message: Message, duration: int = None):
    """
    Поддерживает статус 'печатает' до отмены.
    
    Args:
        message: Объект сообщения.
        duration: Максимальная продолжительность в секундах (None для бесконечного).
        
    Returns:
        Функцию для остановки статуса печатания.
    """
    # Флаг для контроля выполнения цикла
    is_running = True
    
    async def stop_typing():
        global is_running
        is_running = False
    
    # Запускаем асинхронную задачу
    async def typing_loop():
        try:
            await message.bot.send_chat_action(
                chat_id=message.chat.id, 
                action="typing"
            )
        except Exception as e:
            await logs_bot("error", f"Error in typing status loop: {e}")
    
    # Запускаем задачу в фоновом режиме
    await typing_loop()
    
    # Возвращаем функцию для остановки
    return stop_typing