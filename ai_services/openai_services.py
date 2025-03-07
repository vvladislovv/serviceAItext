from openai import OpenAI
from config.config import get_config
import time
import requests
from services.logging import logs_bot
from database.settingsdata import (
    save_voice_to_mongodb,
    get_voice_from_mongodb,
)
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
            api_key=config.openai.api_key, base_url=config.openai.base_url
        )
        self.default_system_message = "Ты полезный ассистент, для дизайнеров и все делаем в сфере графиики и искуства"
        # Базовые URL для разных провайдеров ProxyAPI
        self.proxy_base_urls = {
            "openai": "https://api.proxyapi.ru/openai",
            "anthropic": "https://api.proxyapi.ru/anthropic",
            "google": "https://api.proxyapi.ru/google",
            "deepseek": "https://api.proxyapi.ru/deepseek",
        }

    async def _make_api_request(self, api_func, *args, **kwargs) -> Optional[str]:
        """Общий обработчик API запросов с обработкой ошибок"""
        try:
            return await api_func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {api_func.__name__}: {str(e)}"
            await logs_bot("error", error_msg)
            return None

    async def _make_proxy_request(
        self, provider: str, endpoint: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Выполняет запрос к ProxyAPI"""
        try:
            base_url = self.proxy_base_urls.get(provider)
            if not base_url:
                await logs_bot("error", f"Unknown provider: {provider}")
                return None

            url = f"{base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.client.api_key}",
            }

            # Для Anthropic добавляем специальный заголовок
            if provider == "anthropic":
                headers["Anthropic-Version"] = "2023-06-01"

            await logs_bot("debug", f"Making request to {url}")
            response = requests.post(url, headers=headers, json=data, timeout=60)

            if response.status_code != 200:
                await logs_bot(
                    "error", f"ProxyAPI error: {response.status_code} - {response.text}"
                )
                return None

            return response.json()
        except Exception as e:
            await logs_bot("error", f"Error in _make_proxy_request: {str(e)}")
            return None

    async def text_to_speech(
        self, text: str, voice: str = "alloy", model: str = "tts"
    ) -> Optional[str]:
        """
        Преобразование текста в речь и сохранение в MongoDB

        Args:
            text: Текст для озвучивания
            voice: Голос (alloy, echo, fable, onyx, nova, shimmer)
            model: Модель TTS (tts или tts-hd)

        Returns:
            Optional[str]: Виртуальный путь к аудиофайлу или None в случае ошибки
        """
        try:
            # Нормализуем модель
            tts_model = "tts-1-hd" if model == "tts-hd" else "tts-1"

            await logs_bot(
                "debug",
                f"Starting TTS generation with model: {tts_model}, voice: {voice}",
            )

            # Для стандартного OpenAI API
            if self.client.base_url == "https://api.openai.com/v1":
                try:
                    response = self.client.audio.speech.create(
                        model=tts_model, voice=voice, input=text
                    )

                    if response:
                        # Получаем бинарные данные
                        audio_data = response.content

                        # Генерируем уникальное имя файла
                        timestamp = int(time.time())
                        voice_name = f"tts_{voice}_{timestamp}.mp3"

                        # Сохраняем в MongoDB
                        virtual_path = await save_voice_to_mongodb(
                            0, audio_data, voice_name
                        )

                        await logs_bot(
                            "info", f"TTS saved to MongoDB with path: {virtual_path}"
                        )
                        return virtual_path
                    else:
                        await logs_bot("error", "Empty response from OpenAI API")
                        return None
                except Exception as api_error:
                    await logs_bot("error", f"OpenAI API error: {str(api_error)}")
                    return None

            # Для ProxyAPI
            else:
                # Определяем URL для запроса
                url = f"{self.proxy_base_urls['openai']}/v1/audio/speech"

                # Подготавливаем данные для запроса
                data = {"model": tts_model, "voice": voice, "input": text}

                # Заголовки запроса
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.client.api_key}",
                }

                # Отправляем запрос
                await logs_bot("debug", f"Sending TTS request to ProxyAPI: {url}")
                response = requests.post(url, headers=headers, json=data, timeout=60)

                if response.status_code == 200:
                    # Получаем бинарные данные
                    audio_data = response.content

                    # Генерируем уникальное имя файла
                    timestamp = int(time.time())
                    voice_name = f"tts_{voice}_{timestamp}.mp3"

                    # Сохраняем в MongoDB
                    virtual_path = await save_voice_to_mongodb(
                        0, audio_data, voice_name
                    )

                    await logs_bot(
                        "info", f"TTS saved to MongoDB with path: {virtual_path}"
                    )
                    return virtual_path
                else:
                    await logs_bot(
                        "error",
                        f"ProxyAPI error: {response.status_code} - {response.text}",
                    )
                    return None

        except Exception as e:
            await logs_bot("error", f"Error in text_to_speech: {str(e)}")
            import traceback

            await logs_bot("error", traceback.format_exc())
            return None

    async def generate_image(
        self, prompt: str, model_gpt: str, userid: int, num: int = 1
    ) -> List[str]:
        """
        Генерирует изображения с помощью DALL-E

        Args:
            prompt: Текстовое описание для генерации
            model_gpt: Модель для генерации (dall-e-3 или dall-e-3-hd)
            userid: ID пользователя
            num: Количество изображений (1-4)

        Returns:
            List[str]: Список путей к сгенерированным изображениям
        """
        try:
            save_directory = "./info_save/images"
            saved_images = []

            # Создаем директорию если её нет
            os.makedirs(save_directory, exist_ok=True)

            # Очищаем промпт для имени файла
            clean_prompt = "".join(
                char for char in prompt[:30] if char.isalnum() or char in (" ", "_")
            ).strip()
            clean_prompt = clean_prompt.replace(" ", "_")

            # Настройки качества и размера
            quality = "hd" if model_gpt == "dall-e-3-hd" else "standard"
            size = "1792x1024" if model_gpt == "dall-e-3-hd" else "1024x1024"

            # Конвертируем название модели для API
            api_model = "dall-e-3"

            await logs_bot(
                "info",
                f"Starting image generation: {num} images with model {api_model}",
            )

            # Генерируем изображения
            for i in range(num):
                try:
                    response = self.client.images.generate(
                        model=api_model, prompt=prompt, size=size, quality=quality, n=1
                    )

                    if response and response.data:
                        image_url = response.data[0].url

                        # Создаем имя файла: user_id_prompt_number.png
                        image_filename = f"{userid}_{clean_prompt}_image_{i+1}.png"
                        image_path = os.path.join(save_directory, image_filename)

                        # Скачиваем и сохраняем изображение
                        img_data = requests.get(image_url).content
                        with open(image_path, "wb") as image_file:
                            image_file.write(img_data)

                        saved_images.append(image_path)
                        await logs_bot(
                            "info",
                            f"Successfully generated and saved image {i+1} as {image_filename}",
                        )
                    else:
                        await logs_bot("error", f"Empty response for image {i+1}")

                except Exception as e:
                    await logs_bot("error", f"Error generating image {i+1}: {e}")
                    continue

            return saved_images

        except Exception as e:
            await logs_bot("error", f"Error in image generation: {e}")
            raise

    async def analyze_image(self, image_url: str, prompt: str, model_gpt: str) -> str:
        """
        Анализирует изображение с помощью GPT-4 Vision

        Args:
            image_url: URL изображения для анализа
            prompt: Промпт для анализа
            model_gpt: Модель для анализа

        Returns:
            str: Результат анализа
        """
        try:
            # Используем GPT-4 Vision для анализа
            model = "gpt-4-vision-preview"

            await logs_bot("info", f"Starting image analysis with model {model}")

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                max_tokens=500,
            )

            if response and response.choices:
                result = response.choices[0].message.content
                await logs_bot("info", "Successfully analyzed image")
                return result
            else:
                await logs_bot("error", "Empty response from image analysis")
                return "Не удалось проанализировать изображение."

        except Exception as e:
            if "Insufficient balance" in str(e):
                await logs_bot("error", "Insufficient balance to run this request.")
                return "❌ У вас недостаточно средств для выполнения этого запроса. Пожалуйста, пополните баланс."
            await logs_bot("error", f"Error in image analysis: {e}")
            return "Произошла ошибка при анализе изображения. Пожалуйста, попробуйте позже."

    async def speech_to_text(self, virtual_path: str, model: str = "whisper-1") -> str:
        """
        Конвертация аудио в текст

        Args:
            virtual_path: Виртуальный путь к файлу в MongoDB
            model: Модель для распознавания речи

        Returns:
            str: Распознанный текст
        """
        try:
            await logs_bot("debug", f"Starting speech-to-text for path: {virtual_path}")

            # Получаем данные из MongoDB
            voice_data = await get_voice_from_mongodb(virtual_path)

            if not voice_data:
                await logs_bot(
                    "error", f"Voice data not found for path: {virtual_path}"
                )
                return ""

            await logs_bot(
                "debug",
                f"Retrieved voice data from MongoDB, size: {len(voice_data)} bytes",
            )

            # Создаем временный файл для OpenAI API
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix=".oga") as temp_file:
                temp_file.write(voice_data)
                temp_path = temp_file.name

            try:
                # Используем временный файл для распознавания
                with open(temp_path, "rb") as audio_file:
                    await logs_bot(
                        "debug", f"Sending file to OpenAI API for transcription"
                    )
                    transcript = self.client.audio.transcriptions.create(
                        model=model, file=audio_file
                    )

                # Удаляем временный файл
                os.unlink(temp_path)

                await logs_bot("info", f"Transcription result: {transcript.text}")
                return transcript.text

            except Exception as e:
                # В случае ошибки удаляем временный файл
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

        except Exception as e:
            await logs_bot("error", f"Error in speech_to_text: {str(e)}")
            import traceback

            await logs_bot("error", traceback.format_exc())
            return ""

    async def _prepare_messages(
        self, user_message: str, context: list, system_message: str = None
    ):
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add last 5 messages from context
        for msg in context[-5:]:
            messages.extend(
                [
                    {"role": "user", "content": msg[0]},
                    {"role": "assistant", "content": msg[1]},
                ]
            )

        messages.append({"role": "user", "content": user_message})
        return messages

    async def chat_completion_with_context(
        self, user_message: str, context: list, model_gpt: str
    ) -> str:
        """Обработка сообщения с учетом контекста"""
        try:
            # Подготавливаем сообщения
            messages = await self._prepare_messages(
                user_message, context, self.default_system_message
            )

            # Добавляем логирование для отладки
            await logs_bot("debug", f"Sending request to API with model: {model_gpt}")

            # Проверяем, что модель существует и доступна
            if not model_gpt:
                await logs_bot("error", "Model name is empty or None")
                return "Ошибка: не указана модель AI."

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
                    return f"Ошибка API: {str(api_error)[:100]}."
                # Проверяем ответ
                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    return content

                # Если ответ пустой или некорректный
                await logs_bot("warning", "Empty or invalid response from OpenAI")
                return "Не удалось получить ответ от модели."

        except Exception as e:
            # Подробное логирование ошибки
            error_details = f"Error details: {str(e)}\nModel: {model_gpt}"
            await logs_bot("error", f"Error in chat completion: {error_details}")
            return "Произошла ошибка при обработке запроса."

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
                    processed_messages.append(
                        {"role": msg["role"], "content": msg["content"]}
                    )

            # Если есть системное сообщение, добавляем его в контекст
            if system_content:
                # Для первого пользовательского сообщения добавляем системный контекст
                if processed_messages and processed_messages[0]["role"] == "user":
                    processed_messages[0][
                        "content"
                    ] = f"Контекст: {system_content}\n\n{processed_messages[0]['content']}"
                else:
                    # Если нет пользовательских сообщений, создаем новое
                    processed_messages.insert(
                        0, {"role": "user", "content": f"Контекст: {system_content}"}
                    )

            # Выполняем запрос к API
            response = self.client.chat.completions.create(
                model=model,
                messages=processed_messages,
            )

            # Обрабатываем ответ
            if response and response.choices and len(response.choices) > 0:
                return response.choices[0].message.content

            await logs_bot("warning", f"Empty or invalid response from {model}")
            return f"Не удалось получить ответ от модели {model}."

        except Exception as e:
            await logs_bot("error", f"Error in _process_o1 for {model}: {str(e)}")
            return f"Произошла ошибка при обработке запроса {model}."

    async def _process_deepseek(
        self, messages: List[Dict[str, Any]], model: str
    ) -> str:
        """Обработка запросов к DeepSeek моделям"""
        try:
            # Маппинг моделей
            model_mapping = {
                "deepseek-v3": "deepseek-chat",
                "deepseek-r1": "deepseek-chat",
            }

            deepseek_model = model_mapping.get(model, "deepseek-chat")

            # Подготовка данных для запроса
            data = {"model": deepseek_model, "messages": messages}

            # Выполнение запроса
            response = await self._make_proxy_request(
                "deepseek", "/chat/completions", data
            )

            if response and "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]

            await logs_bot(
                "warning", f"Empty or invalid response from DeepSeek: {response}"
            )
            return "Не удалось получить ответ от модели DeepSeek."

        except Exception as e:
            await logs_bot("error", f"Error in _process_deepseek: {str(e)}")
            return "Произошла ошибка при обработке запроса DeepSeek."

    async def _process_claude(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к Claude моделям"""
        try:
            # Маппинг моделей
            model_mapping = {
                "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
                "claude-3-haiku": "claude-3-haiku-20240307",
            }

            claude_model = model_mapping.get(model, model)

            # Преобразуем сообщения в формат Claude
            claude_messages = []
            for msg in messages:
                if (
                    msg["role"] != "system"
                ):  # Системные сообщения обрабатываются отдельно
                    claude_messages.append(
                        {"role": msg["role"], "content": msg["content"]}
                    )

            # Находим системное сообщение
            system_content = next(
                (msg["content"] for msg in messages if msg["role"] == "system"), None
            )

            # Подготовка данных для запроса
            data = {
                "model": claude_model,
                "messages": claude_messages,
                "max_tokens": 1024,
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

            await logs_bot(
                "warning", f"Empty or invalid response from Claude: {response}"
            )
            return "Не удалось получить ответ от модели Claude."

        except Exception as e:
            await logs_bot("error", f"Error in _process_claude: {str(e)}")
            return "Произошла ошибка при обработке запроса Claude."

    async def _process_gemini(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Обработка запросов к Gemini моделям"""
        try:
            # Преобразуем сообщения в формат Gemini
            gemini_contents = []

            # Обрабатываем системное сообщение
            system_content = next(
                (msg["content"] for msg in messages if msg["role"] == "system"), None
            )

            # Если есть системное сообщение, добавляем его как сообщение от модели
            if system_content:
                gemini_contents.append(
                    {"role": "model", "parts": [{"text": system_content}]}
                )

            # Добавляем остальные сообщения
            for msg in messages:
                if (
                    msg["role"] != "system"
                ):  # Пропускаем системные сообщения, они уже обработаны
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_contents.append(
                        {"role": role, "parts": [{"text": msg["content"]}]}
                    )

            # Подготовка данных для запроса
            data = {"contents": gemini_contents}

            # Определяем эндпоинт в зависимости от модели
            endpoint = f"/v1/models/{model}:generateContent"

            # Выполнение запроса
            response = await self._make_proxy_request("google", endpoint, data)

            if (
                response
                and "candidates" in response
                and len(response["candidates"]) > 0
            ):
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if len(parts) > 0 and "text" in parts[0]:
                        return parts[0]["text"]

            await logs_bot(
                "warning", f"Empty or invalid response from Gemini: {response}"
            )
            return "Не удалось получить ответ от модели Gemini."

        except Exception as e:
            await logs_bot("error", f"Error in _process_gemini: {str(e)}")
            return "Произошла ошибка при обработке запроса Gemini."


openai_service = OpenAIService()
