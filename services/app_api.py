from fastapi import FastAPI, HTTPException, Depends, status, APIRouter
from fastapi.security import APIKeyHeader
import uvicorn
from config.config import get_config
from services.logging import logs_bot
from aiohttp import ClientSession
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from database.settingsdata import get_table_data, get_state_ai, add_to_table
from services.api_models import (
    ModelUpdate, BroadcastMessage, TimeRange, UsageStats,
     UserDetail, SubscriptionUpdate, ChatHistory
)

config = get_config()

# Настройка аутентификации
API_KEY = config.telegram.api_key
api_key_header = APIKeyHeader(name="X-API-Key")

# Создаем роутеры для группировки эндпоинтов
admin_router = APIRouter(prefix="/admin", tags=["admin"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
users_router = APIRouter(prefix="/users", tags=["users"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI."""
    global session
    session = ClientSession()
    await logs_bot("info", "FastAPI started")
    yield
    await session.close()
    await logs_bot("info", "FastAPI stopped")

app = FastAPI(
    title="AI Bot API",
    description="API для управления и мониторинга AI бота",
    version="1.0.0",
    lifespan=lifespan
)

async def run_fastapi():
    """Запуск FastAPI сервера."""
    try:
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    except asyncio.CancelledError:
        await logs_bot("info", "FastAPI task cancelled")
    except Exception as e:
        await logs_bot("error", f"FastAPI error: {e}")

# Функция для проверки API ключа
def verify_api_key(api_key: str = Depends(api_key_header)):
    """Проверка API ключа."""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

# Базовые эндпоинты
@app.get("/", tags=["general"])
async def read_root():
    """Корневой эндпоинт.
    
    Пример вызова:
    GET /
    """
    return {"message": "AI Bot API", "version": "1.0.0"}

@app.get("/ping", tags=["general"])
async def ping(api_key: str = Depends(verify_api_key)):
    """Эндпоинт для проверки работоспособности API.
    
    Пример вызова:
    GET /ping
    Заголовок: X-API-Key: ваш_api_ключ
    """
    try:
        return {"message": "PONG!", "status": "OK"}
    except Exception as e:
        await logs_bot("error", f"Ping endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )

# Эндпоинты для администрирования
@admin_router.post("/update_model")
async def update_model(model_data: ModelUpdate, api_key: str = Depends(verify_api_key)):
    """Обновление доступных запросов для определенной модели.
    
    Пример вызова:
    POST /admin/update_model
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "model_name": "gpt-4",
        "available_requests": 50
    }
    """
    try:
        users = await get_table_data("Users")
        
        for user in users:
            user_id = user.get("chatId")
            if user_id:
                ai_state = await get_state_ai(user_id)
                ai_state[model_data.model_name] = model_data.available_requests
                await add_to_table("StaticAIUsers", {
                    "chatId": user_id,
                    "dataGpt": ai_state
                })
        
        return {"status": "success", "message": f"Updated {len(users)} users"}
    except Exception as e:
        await logs_bot("error", f"Update model endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating model: {str(e)}"
        )

@admin_router.post("/broadcast")
async def broadcast_message(broadcast_data: BroadcastMessage, api_key: str = Depends(verify_api_key)):
    """Отправка сообщения всем или выбранным пользователям.
    
    Пример вызова:
    POST /admin/broadcast
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "message_text": "Ваше сообщение",
        "target_users": [123, 456]  // опционально
    }
    """
    try:
        if broadcast_data.target_users:
            users = []
            for user_id in broadcast_data.target_users:
                user_data = await get_table_data("Users", {"chatId": user_id})
                if user_data:
                    users.append(user_data[0])
        else:
            users = await get_table_data("Users")
        
        return {
            "status": "queued", 
            "message": f"Broadcasting to {len(users)} users",
            "target_users": [u.get("chatId") for u in users]
        }
    except Exception as e:
        await logs_bot("error", f"Broadcast endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error broadcasting message: {str(e)}"
        )

@admin_router.post("/update_subscription")
async def update_subscription(sub_data: SubscriptionUpdate, api_key: str = Depends(verify_api_key)):
    """Обновление подписки пользователя.
    
    Пример вызова:
    POST /admin/update_subscription
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "user_id": 123,
        "tariff": "Premium",
        "expiry_date": "2024-12-31"  // опционально
    }
    """
    try:
        users = await get_table_data("Users", {"chatId": sub_data.user_id})
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {sub_data.user_id} not found"
            )
        
        update_data = {
            "chatId": sub_data.user_id,
            "tarif": sub_data.tariff
        }
        
        if sub_data.expiry_date:
            update_data["expiry_date"] = datetime.strptime(sub_data.expiry_date, "%Y-%m-%d")
        
        await add_to_table("UsersPayPass", update_data)
        
        if sub_data.tariff == "Premium":
            ai_state = await get_state_ai(sub_data.user_id)
            ai_state["gpt-4o"] = 100
            ai_state["gpt-4o-mini"] = 200
            await add_to_table("StaticAIUsers", {
                "chatId": sub_data.user_id,
                "dataGpt": ai_state
            })
        
        return {"status": "success", "message": f"Updated subscription for user {sub_data.user_id}"}
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"Update subscription endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating subscription: {str(e)}"
        )

# Эндпоинты для аналитики
@analytics_router.post("/usage", response_model=UsageStats)
async def get_usage_stats(time_range: TimeRange, api_key: str = Depends(verify_api_key)):
    """Получение статистики использования бота за определенный период.
    
    Пример вызова:
    POST /analytics/usage
    Заголовок: X-API-Key: ваш_api_ключ
    Тело запроса:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    """
    try:
        start_date = datetime.strptime(time_range.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(time_range.end_date, "%Y-%m-%d").date()
        
        history = await get_table_data("ChatHistory")
        
        filtered_history = [
            h for h in history 
            if h.get("timestamp") and 
            start_date <= h.get("timestamp").date() <= end_date
        ]
        
        total_requests = len(filtered_history)
        
        requests_by_model = {}
        for h in filtered_history:
            model = h.get("model", "unknown")
            requests_by_model[model] = requests_by_model.get(model, 0) + 1
        
        requests_by_day = {}
        for h in filtered_history:
            if h.get("timestamp"):
                day = h.get("timestamp").date().isoformat()
                requests_by_day[day] = requests_by_day.get(day, 0) + 1
        
        response_times = [
            h.get("response_time", 0) for h in filtered_history 
            if h.get("response_time")
        ]
        average_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return UsageStats(
            total_requests=total_requests,
            requests_by_model=requests_by_model,
            requests_by_day=requests_by_day,
            average_response_time=average_response_time
        )
    except Exception as e:
        await logs_bot("error", f"Usage stats endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting usage stats: {str(e)}"
        )

# Эндпоинты для работы с пользователями
@users_router.get("/{user_id}/chat_history", response_model=ChatHistory)
async def get_chat_history(user_id: int, limit: int = 10, api_key: str = Depends(verify_api_key)):
    """Получение истории чата пользователя."""
    try:
        users = await get_table_data("Users", {"chatId": user_id})
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        history = await get_table_data("ChatHistory", {"chatId": user_id})
        
        history.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
        
        limited_history = history[:limit]
        
        messages = []
        for h in limited_history:
            messages.append({
                "user_message": h.get("message_text", ""),
                "bot_response": h.get("response_text", ""),
                "model": h.get("model", "unknown"),
                "timestamp": h.get("timestamp", "").isoformat() if h.get("timestamp") else None
            })
        
        return ChatHistory(
            user_id=user_id,
            messages=messages,
            total_messages=len(history)
        )
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"Chat history endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting chat history: {str(e)}"
        )

@users_router.get("/{user_id}", response_model=UserDetail)
async def get_user_detail(user_id: int, api_key: str = Depends(verify_api_key)):
    """Получение детальной информации о конкретном пользователе."""
    try:
        users = await get_table_data("Users", {"chatId": user_id})
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        user = users[0]
        
        history = await get_table_data("ChatHistory", {"chatId": user_id})
        
        ai_state = await get_state_ai(user_id)
        
        model_counts = {}
        for h in history:
            model = h.get("model", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1
        
        favorite_model = max(model_counts.items(), key=lambda x: x[1])[0] if model_counts else "none"
        
        return UserDetail(
            user_id=user_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            requests_count=len(history),
            favorite_model=favorite_model,
            remaining_requests=ai_state
        )
    except HTTPException:
        raise
    except Exception as e:
        await logs_bot("error", f"User detail endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user details: {str(e)}"
        )

# Подключаем роутеры к приложению
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(users_router)


