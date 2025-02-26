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
            # Для usersAI с in_progress используем специальный фильтр
            filter_criteria = (
                {"typeGpt": {"$exists": True}} 
                if collection_name == "UsersAI" and "in_progress" in data
                else {"chatId": data["chatId"]}
            )
            
            # Для usersAI с in_progress не используем upsert
            use_upsert = not (collection_name == "UsersAI" and "in_progress" in data)
            result = collection.update_one(
                filter_criteria,
                {"$set": data},
                upsert=use_upsert
            )
            
            return result.upserted_id or result.modified_count if use_upsert else result.modified_count
        
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
            "timestamp": datetime.utcnow()
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
