from pymongo import MongoClient
from config.config import get_config
from typing import Any, List, Dict
from services.logging import logs_bot
from datetime import datetime

config = get_config()

# Подключение к MongoDB
client = MongoClient(config.db.uri)
db = client[config.db.name]

async def init_db():
    """
    Инициализация базы данных MongoDB.
    """
    try:
        # Проверяем подключение к базе данных
        client.admin.command('ping')
        await logs_bot("info", "MongoDB connection established successfully")
    except Exception as e:
        await logs_bot("error", f"MongoDB connection error: {str(e)}")

async def add_to_table(collection_name: str, data: dict) -> Any:
    """
    Общая функция для добавления данных в коллекцию MongoDB.
    
    Аргументы:
        collection_name: str - Название коллекции
        data: dict - Данные для вставки
    """
    try:
        collection = db[collection_name]
        
        # Объединяем логику обработки в один универсальный update
        if collection_name in ["Users", "UsersAI", "UsersPayPass", "StaticAIUsers", "ChatHistory"]: 
            # Всегда используем chatId как критерий фильтрации
            filter_criteria = {"chatId": data["chatId"]}
            
            # Для всех коллекций используем upsert
            result = collection.update_one(
                filter_criteria,
                {"$set": data},
                upsert=True
            )
            
            return result.upserted_id or result.modified_count
        
        # Для остальных коллекций - обычная вставка
        result = collection.insert_one(data)
        return result.inserted_id

    except Exception as e:
        error_msg = f"Database insertion error in {collection_name}: {str(e)}"
        await logs_bot("error", error_msg)
        return False

async def get_table_data(collection_name: str) -> List[dict]:
    """
    Функция для получения данных из указанной коллекции.
    
    Аргументы:
        collection_name: str - Название коллекции
        
    Возвращает:
        Список словарей с данными из коллекции
    """
    try:
        collection = db[collection_name]
        # Добавляем фильтр для поиска по chatId
        records = list(collection.find({}))
        if not records:
            await logs_bot("warning", f"No records found in {collection_name}")
        return records
    except Exception as e:
        error_msg = f"Error retrieving data from {collection_name}: {str(e)}"
        await logs_bot("error", error_msg)
        return []

async def delete_table(collection_name: str, user_id: int) -> bool:
    """
    Удаляет запись из коллекции по её идентификатору.
    
    Аргументы:
        collection_name: str - Название коллекции
        user_id: int - Уникальный идентификатор записи для удаления
        
    Возвращает:
        bool: True если запись была успешно удалена, False если запись не найдена
    """
    try:
        collection = db[collection_name]
        result = collection.delete_one({"chatId": user_id})
        if result.deleted_count > 0:
            await logs_bot("info", f"Deleted record from {collection_name} for user_id: {user_id}")
            return True
        else:
            await logs_bot("warning", f"Record not found in {collection_name} for user_id: {user_id}")
            return False
    except Exception as e:
        error_msg = f"Error deleting record from {collection_name}: {str(e)}"
        await logs_bot("error", error_msg)
        return False

async def get_state_ai(chat_id: int) -> Dict[str, int]:
    """
    Получает и расшифровывает статистику использования GPT для конкретного пользователя.
    """
    try:
        collection = db["StaticAIUsers"] 
        record = collection.find_one({"chatId": chat_id})
        
        if record and "dataGpt" in record:
            return record["dataGpt"]
        # Возвращаем словарь с начальным значением для всех моделей
        return {}
    except Exception as e:
        error_msg = f"Error getting GPT stats for user {chat_id}: {str(e)}"
        await logs_bot("error", error_msg)
        return {}


async def get_user_history(user_id: int, limit: int = 5) -> list:
    """
    Получает историю сообщений пользователя для контекста OpenAI
    """
    try:
        collection = db["ChatHistory"]
        # Получаем последние сообщения пользователя
        messages = list(collection.find(
            {"chatId": user_id}
        ).sort("timestamp", -1).limit(limit))

        # Формируем контекст для OpenAI
        context = []
        # Идем от старых к новым сообщениям
        for msg in reversed(messages):
            context.append({
                "role": "user",
                "content": msg["message_text"]
            })
            context.append({
                "role": "assistant",
                "content": msg["response_text"]
            })

        await logs_bot("debug", f"Retrieved history for user {user_id}, messages count: {len(messages)}")
        return context

    except Exception as e:
        await logs_bot("error", f"Error getting history: {e}")
        return []

async def save_chat_history(data: dict) -> bool:
    """
    Сохраняет сообщение в историю чата
    """
    try:
        collection = db["ChatHistory"]
        
        # Создаем новую запись
        chat_data = {
            "chatId": data["user_id"],
            "message_text": data["message_text"],
            "response_text": data["response_text"],
            "model": data["model"],
            "timestamp": datetime.now().strftime("%H:%M %d-%m-%Y")
        }

        # Сохраняем новое сообщение
        result = collection.insert_one(chat_data)
        
        # Оставляем только последние 5 сообщений для пользователя
        old_messages = collection.find(
            {"chatId": data["user_id"]}
        ).sort("timestamp", -1).skip(5)
        
        for old_msg in old_messages:
            collection.delete_one({"_id": old_msg["_id"]})

        success = bool(result.inserted_id)
        if success:
            await logs_bot("debug", f"Saved message for user {data['user_id']}")
        return success

    except Exception as e:
        await logs_bot("error", f"Error saving chat: {e}")
        return False

async def delete_user_history(user_id: int) -> bool:
    """
    Удаляет всю историю чата пользователя и сбрасывает контекст
    
    Args:
        user_id: int - ID пользователя
        
    Returns:
        bool: True если удаление прошло успешно
    """
    try:
        # Удаляем историю чата
        chat_history = db["ChatHistory"]
        chat_history.delete_many({"chatId": user_id})
        
        # Сбрасываем контекст в usersAI
        users_ai = db["UsersAI"]
        users_ai.update_one(
            {"chatId": user_id},
            {"$set": {"context": []}},
            upsert=True
        )
        
        await logs_bot("info", f"Successfully deleted history for user {user_id}")
        return True
        
    except Exception as e:
        await logs_bot("error", f"Error deleting history for user {user_id}: {str(e)}")
        return False

async def user_exists(collection_name: str, chat_id: int) -> bool:
    """
    Проверяет, существует ли пользователь с указанным chat_id в коллекции
    
    Args:
        collection_name: str - Название коллекции
        chat_id: int - ID пользователя
        
    Returns:
        bool: True если пользователь существует, False если нет
    """
    try:
        collection = db[collection_name]
        result = collection.find_one({"chatId": chat_id})
        return result is not None
    except Exception as e:
        await logs_bot("error", f"Error checking user existence in {collection_name}: {str(e)}")
        return False

async def save_voice_to_mongodb(user_id: int, voice_data: bytes, voice_name: str) -> str:
    """
    Сохраняет голосовое сообщение в MongoDB
    
    Args:
        user_id: ID пользователя
        voice_data: Бинарные данные голосового сообщения
        voice_name: Имя файла голосового сообщения
        
    Returns:
        str: Виртуальный путь к файлу (для совместимости)
    """
    try:
        collection = db["VoiceMessages"]
        
        # Создаем виртуальный путь к файлу (для совместимости)
        virtual_path = f"./info_save/audio_user/{user_id}_{voice_name}"
        
        # Кодируем бинарные данные в base64 для хранения в MongoDB
        import base64
        encoded_data = base64.b64encode(voice_data).decode('utf-8')
        
        # Создаем запись для MongoDB
        voice_record = {
            "chatId": user_id,
            "voice_data": encoded_data,
            "voice_name": voice_name,
            "virtual_path": virtual_path,
            "timestamp": datetime.now().strftime("%H:%M %d-%m-%Y")
        }
        
        # Проверяем, существует ли уже запись для этого пользователя и голоса
        existing = collection.find_one({"chatId": user_id, "voice_name": voice_name})
        if existing:
            # Обновляем существующую запись
            collection.update_one(
                {"chatId": user_id, "voice_name": voice_name},
                {"$set": {
                    "voice_data": encoded_data,
                    "virtual_path": virtual_path,
                    "timestamp": datetime.now().strftime("%H:%M %d-%m-%Y")
                }}
            )
            await logs_bot("info", f"Updated voice message for user {user_id}")
        else:
            # Создаем новую запись
            collection.insert_one(voice_record)
            await logs_bot("info", f"Created new voice message for user {user_id}")
        
        return virtual_path
        
    except Exception as e:
        await logs_bot("error", f"Error saving voice to MongoDB: {str(e)}")
        return None

async def get_voice_from_mongodb(virtual_path: str) -> bytes:
    """
    Получает голосовое сообщение из MongoDB по виртуальному пути
    
    Args:
        virtual_path: Виртуальный путь к файлу
        
    Returns:
        bytes: Бинарные данные голосового сообщения или None
    """
    try:
        collection = db["VoiceMessages"]
        
        # Логируем для отладки
        await logs_bot("debug", f"Searching for voice message with path: {virtual_path}")
        
        voice_record = collection.find_one({"virtual_path": virtual_path})
        
        if voice_record and "voice_data" in voice_record:
            # Декодируем данные из base64
            import base64
            try:
                voice_data = base64.b64decode(voice_record["voice_data"])
                await logs_bot("debug", f"Found voice data of size: {len(voice_data)} bytes")
                return voice_data
            except Exception as decode_error:
                await logs_bot("error", f"Error decoding base64 data: {str(decode_error)}")
                return None
        
        # Если не нашли по точному пути, попробуем поискать по частичному совпадению
        if not voice_record:
            await logs_bot("debug", f"Trying partial match for voice path: {virtual_path}")
            # Извлекаем имя файла из виртуального пути
            file_name = virtual_path.split('/')[-1]
            voice_records = list(collection.find({"voice_name": {"$regex": file_name.split('_')[-1]}}))
            
            if voice_records and len(voice_records) > 0:
                voice_record = voice_records[0]  # Берем первое совпадение
                if "voice_data" in voice_record:
                    import base64
                    try:
                        voice_data = base64.b64decode(voice_record["voice_data"])
                        await logs_bot("debug", f"Found voice data by partial match, size: {len(voice_data)} bytes")
                        return voice_data
                    except Exception as decode_error:
                        await logs_bot("error", f"Error decoding base64 data: {str(decode_error)}")
                        return None
        
        await logs_bot("warning", f"Voice message not found in MongoDB: {virtual_path}")
        return None
        
    except Exception as e:
        await logs_bot("error", f"Error retrieving voice from MongoDB: {str(e)}")
        import traceback
        await logs_bot("error", traceback.format_exc())
        return None
