from services.logging import logs_bot
from Messages.settingsmsg import new_message, update_message, send_typing_action
from Messages.utils import download_voice_user
from database.settingsdata import (
    get_user_history,
    save_chat_history,
)
from typing import Tuple
from ai_services.openai_services import openai_service

last_messages = {}


async def AI_choice(message, model: str, image_url: str = None) -> Tuple[str, object]:
    """Основной обработчик сообщений"""
    message_text = None

    # Запускаем статус "печатает" и получаем функцию для его остановки

    # Обработка предыдущего сообщения
    if message.from_user.id in last_messages:
        try:
            old_message, old_text = last_messages[message.from_user.id]
            await update_message(old_message, old_text, None)
        except Exception as e:
            await logs_bot("error", f"Error removing keyboard: {e}")

    # Обработка изображения если оно есть
    if image_url:
        # Используем стандартный промпт для анализа изображения
        analysis_prompt = (
            "Пожалуйста, опиши что изображено на этой картинке. Дай подробный анализ."
        )
        response = await openai_service.analyze_image(image_url, analysis_prompt, model)
        msg_old = await new_message(message, "🔍 Анализирую изображение...", None)
        return response, msg_old

    # Создание сообщения о процессе
    model_display_name = model  # Используем функцию
    processing_text = f"🤖 *{model_display_name}* обрабатывает ваш запрос..."
    msg_old = await new_message(message, processing_text, None)
    await send_typing_action(message, "typing")
    try:
        # Обработка входящего сообщения
        if message.voice:
            audio_file_path = await download_voice_user(message)
            message_text = await openai_service.speech_to_text(
                audio_file_path, "whisper-1"
            )
        elif message.text:
            message_text = message.text

        if not message_text:
            return "Не удалось обработать сообщение.", msg_old

        # Получение истории и обработка модели
        history = await get_user_history(message.from_user.id, 5)

        if model == "stable_diffusion":
            pass
        elif model == "midjourney":
            pass
        elif model == "kandinsky":
            pass
        elif model == "leonardo":
            pass
        elif model == "flux":
            pass

        # NOT USE DALLY 3 AND 3 HD

        # Получение ответа от модели через универсальный обработчик
        response = await openai_service.chat_completion_with_context(
            message_text, history, model
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
                            response = response[content_start + 1 : content_end]
                            await logs_bot(
                                "debug", "Cleaned technical details from response"
                            )
                except Exception as e:
                    await logs_bot("warning", f"Failed to clean response: {e}")

        if response:
            # Подготовка и сохранение контекста
            try:
                # Получаем существующий контекст
                context_to_save = []
                if history and any(entry[0] for entry in history):
                    context_to_save.extend(entry[0] for entry in history)
                context_to_save.append(message_text)
                context_to_save.append(response)
                # Сохраняем историю чата
                history_data = {
                    "user_id": message.from_user.id,
                    "message_text": message_text,
                    "response_text": response,
                    "model": model,
                    "context": context_to_save,
                }
                await save_chat_history(history_data)
                await logs_bot(
                    "debug", f"Saved context with {len(context_to_save)} messages"
                )

            except Exception as save_err:
                await logs_bot("error", f"Error saving chat history: {save_err}")

            # Сохраняем текущее сообщение
            last_messages[message.from_user.id] = (msg_old, str(response))

            return response, msg_old

    except Exception as err:

        await logs_bot("error", f"Error in AI_choice: {err}")
        error_msg = "Извините, произошла ошибка при обработке вашего запроса."
        return error_msg, msg_old

    return "Не удалось получить ответ от модели.", msg_old
