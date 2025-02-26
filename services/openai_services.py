from openai import OpenAI
from config.config import get_config
import time
import json
import requests
from services.logging import logs_bot
from Messages.settingsmsg import new_message, update_message, send_typing_action
from Messages.utils import download_voice_user, escape_markdown
from database.settingsdata import get_user_history, save_chat_history
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import os

config = get_config()
last_messages = {}

@dataclass
class MessageResponse:
    """Структура для хранения ответа и сообщения"""
    response: str
    message: object

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url
        )
        self.default_system_message = "Ты полезный ассистент, который помнит контекст разговора."
        # Базовые URL для разных провайдеров ProxyAPI
        self.proxy_base_urls = {
            "openai": "https://api.proxyapi.ru/openai",
            "anthropic": "https://api.proxyapi.ru/anthropic",
            "google": "https://api.proxyapi.ru/google",
            "deepseek": "https://api.proxyapi.ru/deepseek"
        }
        

    async def _make_api_request(self, api_func, *args, **kwargs) -> Optional[str]:
        """Общий обработчик API запросов с обработкой ошибок"""
        try:
            return await api_func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {api_func.__name__}: {str(e)}"
            await logs_bot("error", error_msg)
            return None

    async def _make_proxy_request(self, provider: str, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Выполняет запрос к ProxyAPI"""
        try:
            base_url = self.proxy_base_urls.get(provider)
            if not base_url:
                await logs_bot("error", f"Unknown provider: {provider}")
                return None
                
            url = f"{base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.client.api_key}"
            }
            
            # Для Anthropic добавляем специальный заголовок
            if provider == "anthropic":
                headers["Anthropic-Version"] = "2023-06-01"
                
            await logs_bot("debug", f"Making request to {url}")
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            if response.status_code != 200:
                await logs_bot("error", f"ProxyAPI error: {response.status_code} - {response.text}")
                return None
                
            return response.json()
        except Exception as e:
            await logs_bot("error", f"Error in _make_proxy_request: {str(e)}")
            return None
        

    async def text_to_speech(self, text: str, voice: str = "alloy", model: str = "tts") -> Optional[str]:
        """
        Преобразование текста в речь
        
        Args:
            text: Текст для озвучивания
            voice: Голос (alloy, echo, fable, onyx, nova, shimmer)
            model: Модель TTS (tts или tts_hd)
            
        Returns:
            Optional[str]: Путь к созданному аудиофайлу или None в случае ошибки
        """
        try:
            # Нормализуем модель
            tts_model = "tts-1-hd" if model == "tts_hd" else "tts-1"
            
            await logs_bot("debug", f"Starting TTS generation with model: {tts_model}, voice: {voice}")
            
            # Создаем директорию для временных файлов, если её нет
            os.makedirs("temp", exist_ok=True)
            
            # Для стандартного OpenAI API
            if self.client.base_url == "https://api.openai.com/v1":
                response = self.client.audio.speech.create(
                    model=tts_model,
                    voice=voice,
                    input=text
                )
                
                if response:
                    speech_file_path = f"temp/speech_{voice}_{int(time.time())}.mp3"
                    response.stream_to_file(speech_file_path)
                    return speech_file_path
            else:
                # Для ProxyAPI
                data = {
                    "model": tts_model,
                    "voice": voice,
                    "input": text
                }
                
                # Выполнение запроса через ProxyAPI
                await logs_bot("debug", f"Sending TTS request to ProxyAPI: {json.dumps(data)}")
                
                # Используем requests напрямую для получения бинарных данных
                url = f"{self.proxy_base_urls['openai']}/v1/audio/speech"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.client.api_key}"
                }
                
                response = requests.post(url, headers=headers, json=data, timeout=60)
                
                if response.status_code == 200:
                    # Сохраняем аудио во временный файл
                    speech_file_path = f"temp/speech_{voice}_{int(time.time())}.mp3"
                    with open(speech_file_path, "wb") as f:
                        f.write(response.content)
                    
                    await logs_bot("debug", f"TTS file saved to {speech_file_path}")
                    return speech_file_path
                else:
                    await logs_bot("error", f"ProxyAPI error: {response.status_code} - {response.text}")
            
            await logs_bot("warning", "Empty or invalid response from TTS API")
            return None
            
        except Exception as e:
            await logs_bot("error", f"Error in text_to_speech: {str(e)}")
            import traceback
            await logs_bot("error", traceback.format_exc())
            return None

    async def speech_to_text(self, audio_path: str, model: str = "whisper-1") -> str:
        """Конвертация аудио в текст"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file
                )
                return transcript.text
        except Exception as e:
            await logs_bot("error", f"Error in speech_to_text: {str(e)}")
            return ""

    async def _prepare_messages(self, user_message: str, context: list, system_message: str = None):
        """Подготавливает список сообщений для OpenAI API с правильным контекстом"""
        messages = []
        
        # Добавляем системное сообщение, если оно есть
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        
        # Проверяем, что контекст существует и является списком
        if context and isinstance(context, list):
            # Берем последние 5 пар сообщений (или меньше, если контекст короче)
            context_pairs = []
            
            # Преобразуем контекст в пары "вопрос-ответ"
            i = 0
            while i < len(context) - 1 and len(context_pairs) < 5:
                user_msg = context[i]
                assistant_msg = context[i + 1]
                
                # Проверяем, что оба сообщения не пустые
                if user_msg and assistant_msg:
                    context_pairs.append((user_msg, assistant_msg))
                
                i += 2
            
            # Добавляем последние 5 пар в сообщения
            for user_msg, assistant_msg in context_pairs[-5:]:
                messages.extend([
                    {"role": "user", "content": str(user_msg)},
                    {"role": "assistant", "content": str(assistant_msg)}
                ])
        
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        
        # Логируем для отладки
        await logs_bot("debug", f"Prepared {len(messages)} messages for API")
        
        return messages

    async def chat_completion_with_context(self, user_message: str, context: list, model_gpt: str) -> str:
        """Обработка сообщения с учетом контекста"""
        try:
            # Подготавливаем сообщения
            messages = await self._prepare_messages(
                user_message, 
                context,
                self.default_system_message
            )
            
            # Добавляем логирование для отладки
            await logs_bot("debug", f"Sending request to API with model: {model_gpt}")
            
            # Проверяем, что модель существует и доступна
            if not model_gpt:
                await logs_bot("error", "Model name is empty or None")
                return "Ошибка: не указана модель AI\\."
            
            # Маршрутизация запросов в зависимости от модели
            if model_gpt in ["o1-mini", "o1", "o3mini"]:
                # Для моделей O1 используем специальный формат
                return await self._process_o1(messages, model_gpt)
            elif model_gpt in ["claude-3-5-sonnet", "claude-3-haiku"]:
                # Для моделей Claude используем специальный формат
                return await self._process_claude(messages, model_gpt)
            elif model_gpt in ["gemini-1.5-flash"]:
                # Для моделей Gemini используем специальный формат
                return await self._process_gemini(messages, model_gpt)
            elif model_gpt in ["deepseek-v3", "deepseek-r1"]:
                # Для моделей DeepSeek используем специальный формат
                return await self._process_deepseek(messages, model_gpt)
            else:
                # Для моделей OpenAI используем стандартный формат
                try:
                    response = self.client.chat.completions.create(
                        model=model_gpt,
                        messages=messages,
                    )
                except Exception as api_error:
                    await logs_bot("error", f"OpenAI API error: {str(api_error)}")
                    return f"Ошибка API: {escape_markdown(str(api_error)[:100])}\\."
                
                # Проверяем ответ
                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    return content
                
                # Если ответ пустой или некорректный
                await logs_bot("warning", "Empty or invalid response from OpenAI")
                return "Не удалось получить ответ от модели\\."
                
        except Exception as e:
            # Подробное логирование ошибки
            error_details = f"Error details: {str(e)}\nModel: {model_gpt}"
            await logs_bot("error", f"Error in chat completion: {error_details}")
            return "Произошла ошибка при обработке запроса\\."

    async def _process_o1(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к моделям O1, O1-mini, O3-mini через OpenAI API"""
        try:
            # Преобразуем сообщения в формат, поддерживаемый моделями O1
            processed_messages = []
            system_content = None
            
            # Обрабатываем системное сообщение
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    processed_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Если есть системное сообщение, добавляем его в контекст
            if system_content:
                # Для первого пользовательского сообщения добавляем системный контекст
                if processed_messages and processed_messages[0]["role"] == "user":
                    processed_messages[0]["content"] = f"Контекст: {system_content}\n\n{processed_messages[0]['content']}"
                else:
                    # Если нет пользовательских сообщений, создаем новое
                    processed_messages.insert(0, {
                        "role": "user",
                        "content": f"Контекст: {system_content}"
                    })
            
            # Выполняем запрос к API
            response = self.client.chat.completions.create(
                model=model,
                messages=processed_messages,
            )
            
            # Обрабатываем ответ
            if response and response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            
            await logs_bot("warning", f"Empty or invalid response from {model}")
            return f"Не удалось получить ответ от модели {model}\\."
            
        except Exception as e:
            await logs_bot("error", f"Error in _process_o1 for {model}: {str(e)}")
            return f"Произошла ошибка при обработке запроса {model}\\."

    async def _process_deepseek(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к DeepSeek моделям"""
        try:
            # Маппинг моделей
            model_mapping = {
                "deepseek-v3": "deepseek-chat",
                "deepseek-r1": "deepseek-chat"
            }
            
            deepseek_model = model_mapping.get(model, "deepseek-chat")
            
            # Подготовка данных для запроса
            data = {
                "model": deepseek_model,
                "messages": messages
            }
            
            # Выполнение запроса
            response = await self._make_proxy_request("deepseek", "/chat/completions", data)
            
            if response and "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            
            await logs_bot("warning", f"Empty or invalid response from DeepSeek: {response}")
            return "Не удалось получить ответ от модели DeepSeek\\."
            
        except Exception as e:
            await logs_bot("error", f"Error in _process_deepseek: {str(e)}")
            return "Произошла ошибка при обработке запроса DeepSeek\\."

    async def _process_claude(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к Claude моделям"""
        try:
            # Маппинг моделей
            model_mapping = {
                "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
                "claude-3-haiku": "claude-3-haiku-20240307"
            }
            
            claude_model = model_mapping.get(model, model)
            
            # Преобразуем сообщения в формат Claude
            claude_messages = []
            for msg in messages:
                if msg["role"] != "system":  # Системные сообщения обрабатываются отдельно
                    claude_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Находим системное сообщение
            system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), None)
            
            # Подготовка данных для запроса
            data = {
                "model": claude_model,
                "messages": claude_messages,
                "max_tokens": 1024
            }
            
            # Добавляем системное сообщение, если оно есть
            if system_content:
                data["system"] = system_content
            
            # Выполнение запроса
            response = await self._make_proxy_request("anthropic", "/v1/messages", data)
            
            if response and "content" in response and len(response["content"]) > 0:
                # Извлекаем текст из ответа
                for content_item in response["content"]:
                    if content_item["type"] == "text":
                        return content_item["text"]
            
            await logs_bot("warning", f"Empty or invalid response from Claude: {response}")
            return "Не удалось получить ответ от модели Claude\\."
            
        except Exception as e:
            await logs_bot("error", f"Error in _process_claude: {str(e)}")
            return "Произошла ошибка при обработке запроса Claude\\."

    async def _process_gemini(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к Gemini моделям"""
        try:
            # Преобразуем сообщения в формат Gemini
            gemini_contents = []
            
            # Обрабатываем системное сообщение
            system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), None)
            
            # Если есть системное сообщение, добавляем его как сообщение от модели
            if system_content:
                gemini_contents.append({
                    "role": "model",
                    "parts": [{"text": system_content}]
                })
            
            # Добавляем остальные сообщения
            for msg in messages:
                if msg["role"] != "system":  # Пропускаем системные сообщения, они уже обработаны
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_contents.append({
                        "role": role,
                        "parts": [{"text": msg["content"]}]
                    })
            
            # Подготовка данных для запроса
            data = {
                "contents": gemini_contents
            }
            
            # Определяем эндпоинт в зависимости от модели
            endpoint = f"/v1/models/{model}:generateContent"
            
            # Выполнение запроса
            response = await self._make_proxy_request("google", endpoint, data)
            
            if response and "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if len(parts) > 0 and "text" in parts[0]:
                        return parts[0]["text"]
            
            await logs_bot("warning", f"Empty or invalid response from Gemini: {response}")
            return "Не удалось получить ответ от модели Gemini\\."
            
        except Exception as e:
            await logs_bot("error", f"Error in _process_gemini: {str(e)}")
            return "Произошла ошибка при обработке запроса Gemini\\."

async def AI_choice(message, model: str) -> Tuple[str, object]:
    """Основной обработчик сообщений"""
    message_text = None
    await send_typing_action(message)
    # Обработка предыдущего сообщения
    if message.from_user.id in last_messages:
        try:
            old_message, old_text = last_messages[message.from_user.id]
            await update_message(old_message, old_text, None)
        except Exception as e:
            await logs_bot('error', f"Error removing keyboard: {e}")

    # Создание сообщения о процессе
    model_display_name = escape_markdown(model)  # Используем функцию escape_markdown
    processing_text = f"🤖 *{model_display_name}* обрабатывает ваш запрос\\.\\.\\."
    msg_old = await new_message(message, processing_text, None)

    try:
        # Обработка входящего сообщения
        if message.voice:
            audio_file_path = await download_voice_user(message)
            message_text = await openai_service.speech_to_text(audio_file_path, "whisper-1")
        elif message.text:
            message_text = message.text

        if not message_text:
            return "Не удалось обработать сообщение\\.", msg_old

        # Получение истории и обработка модели
        history = await get_user_history(message.from_user.id, 5)
        
        # Получение ответа от модели через универсальный обработчик
        response = await openai_service.chat_completion_with_context(
            message_text,
            history,
            model
        )

        # Очищаем ответ от технических деталей, если они есть
        if response and isinstance(response, str):
            # Проверяем на наличие технических деталей
            if "{'role':" in response or '{"role":' in response:
                try:
                    # Простая очистка без регулярных выражений
                    content_start = response.find("'content': '")
                    if content_start == -1:
                        content_start = response.find('"content": "')
                    
                    if content_start != -1:
                        content_start = response.find("'", content_start + 11)
                        if content_start == -1:
                            content_start = response.find('"', content_start + 11)
                        
                        content_end = response.rfind("'}")
                        if content_end == -1:
                            content_end = response.rfind('"')
                        
                        if content_start != -1 and content_end != -1:
                            response = response[content_start+1:content_end]
                            await logs_bot("debug", "Cleaned technical details from response")
                except Exception as e:
                    await logs_bot("warning", f"Failed to clean response: {e}")

        if response:
            # Подготовка и сохранение контекста
            try:
                # Получаем существующий контекст
                existing_context = []
                if history:
                    existing_context = history
                
                # Добавляем новую пару сообщений
                # Если контекст слишком длинный, удаляем старые сообщения
                max_context_length = 20  # Максимальное количество сообщений (10 пар)
                if len(existing_context) >= max_context_length:
                    # Удаляем старые сообщения, оставляя место для новой пары
                    existing_context = existing_context[-(max_context_length-2):]
                
                # Добавляем новую пару сообщений
                existing_context.append(message_text)
                existing_context.append(response)
                
                # Сохраняем историю чата
                history_data = {
                    "user_id": message.from_user.id,
                    "message_text": message_text,
                    "response_text": response,
                    "model": model,
                    "context": existing_context
                }
                await save_chat_history(history_data)
                await logs_bot("debug", f"Saved context with {len(existing_context)} messages")
                
            except Exception as save_err:
                await logs_bot('error', f"Error saving chat history: {save_err}")
            
            # Сохраняем текущее сообщение
            last_messages[message.from_user.id] = (msg_old, str(response))
            return response, msg_old

    except Exception as err:
        await logs_bot('error', f"Error in AI_choice: {err}")
        error_msg = "Извините, произошла ошибка при обработке вашего запроса\\."
        return error_msg, msg_old

    return "Не удалось получить ответ от модели\\.", msg_old

openai_service = OpenAIService() 
