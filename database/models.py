from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, List, Any

class Users(BaseModel):
    chatId: int
    idMessage: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    created_at: datetime = datetime.now().replace(second=0, microsecond=0)

class UsersAI(BaseModel):
    chatId: int
    typeGpt: str
    in_progress: bool = False
    context: List[Any]

class UsersPayPass(BaseModel):
    chatId: int
    id_pass: int 
    tarif: str
    created_at: datetime = datetime.now().replace(second=0, microsecond=0)

class StaticAIUsers(BaseModel):
    chatId: int
    dataGpt : Dict[str, int]
    created_at: datetime = datetime.now().replace(second=0, microsecond=0)

class ChatHistory(BaseModel):
    user_id: int
    message_text: str
    response_text: str
    model: str
    timestamp: datetime = datetime.now()
    context: Optional[List[Dict[str, Any]]] = None
    
