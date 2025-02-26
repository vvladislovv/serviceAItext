from services.logging import logs_bot
from database.settingsdata import add_to_table, user_exists
import os
from datetime import datetime


async def create_user_data(message) -> dict:
    from config.confpaypass import get_default_limits
    """
    Creates and stores initial user data across multiple database tables.
    Only creates data if it doesn't already exist.
    
    This function:
    1. Creates user profile data
    2. Initializes AI settings for the user
    3. Sets up payment/pass information
    4. Configures static AI data
    5. Starts chat history
    6. Logs the user's start
    7. Saves all data to respective database tables
    
    Args:
        message: Telegram message object containing user information
        
    Returns:
        dict: Dictionary containing all created user data
    """
    
    # Common user ID to be used across all tables
    chat_id = message.from_user.id
    
    # Create all data structures
    user_data = {
        'chatId': chat_id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    }
    
    user_ai = {
        'chatId': chat_id,
        'typeGpt': 'gpt-4o-mini',
        'in_progress': False
    }

    user_pay_pass = {
        'chatId': chat_id,
        'id_pass': 1,
        'tarif': 'NoBase',
    }

    static_ai_user = {
        'chatId': chat_id,
        'dataGpt': get_default_limits()
    }
    
    # Инициализируем историю чата только если она еще не существует
    chat_history = {
        'chatId': chat_id,
        'message_text': '',
        'response_text': '',
        'context': [],  # Пустой контекст для новых пользователей
        'model': 'gpt-4o-mini',
        'timestamp': datetime.utcnow()
    }
    
    # Log user start
    await logs_bot("info", f"User {chat_id} started the bot")
    
    # Проверяем и сохраняем данные только если они не существуют
    tables_data = [
        ("Users", user_data),
        ("UsersAI", user_ai),
        ("UsersPayPass", user_pay_pass),
        ("StaticAIUsers", static_ai_user)
    ]
    
    for table_name, data in tables_data:
        # Проверяем, существует ли запись
        if not await user_exists(table_name, chat_id):
            await add_to_table(table_name, data)
            await logs_bot("info", f"Created new record in {table_name} for user {chat_id}")
        else:
            await logs_bot("debug", f"User {chat_id} already exists in {table_name}, skipping creation")
    
    # Возвращаем созданные данные
    return {
        'Users': user_data,
        'UsersAI': user_ai,
        'UsersPayPass': user_pay_pass,
        'StaticAIUsers': static_ai_user,
        'ChatHistory': chat_history
    }

async def download_voice_user(message):
    voice_file_id = message.voice.file_id
    voice_file_info = await message.bot.get_file(voice_file_id)
    audio_dir = "./info_save/audio_user"
    os.makedirs(audio_dir, exist_ok=True)
    user_id = message.from_user.id
    audio_file_name = f"{user_id}_{voice_file_info.file_path.split('/')[-1]}"
    audio_file_path = os.path.join(audio_dir, audio_file_name)

    await message.bot.download_file(voice_file_info.file_path, audio_file_path)

    return  audio_file_path

def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы для Markdown V2
    
    Args:
        text: Исходный текст
        
    Returns:
        str: Экранированный текст
    """
    if not text:
        return ""
        
    # Список символов, которые нужно экранировать
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Экранируем каждый специальный символ
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
        
    return text

def process_ai_markdown(text: str) -> str:
    """Преобразует Markdown от OpenAI в MarkdownV2 для Telegram"""
    if not text:
        return ""
    
    # Экранируем специальные символы
    escape_chars = '_*[]()~`>#+-=|{}.!'
    
    # Обрабатываем текст построчно
    result = []
    in_code_block = False
    
    for line in text.split('\n'):
        if line.strip().startswith('```') or line.strip().endswith('```'):
            in_code_block = not in_code_block
            result.append(line)
        elif in_code_block:
            result.append(line)
        else:
            escaped_line = []
            for char in line:
                if char in escape_chars:
                    escaped_line.append(f'\\{char}')
                else:
                    escaped_line.append(char)
            result.append(''.join(escaped_line))
    
    return '\n'.join(result)

def escape_text(text: str) -> str:
    """Экранирует специальные символы, кроме блоков кода"""
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)