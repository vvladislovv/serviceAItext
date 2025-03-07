import asyncio
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from Messages.localization import MESSAGES
from Messages.utils import create_user_data
from Messages.settingsmsg import new_message, update_message, send_typing_action
from services.logging import logs_bot
from aiogram.fsm.context import FSMContext
from database.settingsdata import get_state_ai, get_table_data, add_to_table
from services.AiModule import AI_choice
from services.anti_spam import spam_controller
from Messages.inlinebutton import get_general_menu, ai_menu_back
from handlers.image_handler import handle_image_analysis

router = Router(name=__name__)


@router.message(CommandStart())
async def command_start(message: types.Message):
    """Обработчик команды /start."""
    try:
        # Отправляем приветственное сообщение
        await send_typing_action(message, "typing")
        await new_message(message, MESSAGES["ru"]["start"], await get_general_menu())

        # Сохраняем информацию о пользователе
        await create_user_data(message)

    except Exception as e:
        await logs_bot("error", f"Error in start command: {e}")


@router.message(F.text | F.voice | F.audio | F.photo)
async def handle_message(message: types.Message, state: FSMContext):
    try:
        # Проверяем состояние генерации изображения
        current_state = await state.get_state()
        if current_state == "GenerationState:waiting_prompt":
            if not message.text:
                await new_message(
                    message,
                    "❌ Пожалуйста, отправьте текстовое описание изображения.",
                    None,
                )
                return

            state_data = await state.get_data()
            image_count = state_data.get("image_count", 1)

            # Проверяем лимиты пользователя
            data_gpt = await get_state_ai(message.from_user.id)
            user_ai = next(
                (
                    u
                    for u in await get_table_data("UsersAI")
                    if u.get("chatId") == message.from_user.id
                ),
                {},
            )
            model_type = user_ai.get("typeGpt", "dall-e-3")
            remaining_requests = data_gpt.get(model_type, 0)

            if remaining_requests <= 0:
                await new_message(
                    message,
                    "⚠️ У вас закончились доступные запросы для генерации изображений. "
                    "Пожалуйста, обновите подписку.",
                    None,
                )
                await state.clear()
                return

            # Импортируем функцию генерации из нового модуля
            from handlers.image_handler import handle_image_generation

            success = await handle_image_generation(message, message.text, image_count)

            if success:
                # Обновляем статистику использования
                user_data = await get_state_ai(message.from_user.id)
                if model_type in user_data:
                    user_data[model_type] -= 1
                await add_to_table(
                    "StaticAIUsers",
                    {"chatId": message.from_user.id, "dataGpt": user_data},
                )

            await state.clear()
            return

        # Проверка на спам
        can_send, wait_time = await spam_controller.check_spam(message.from_user.id)
        if not can_send:
            await new_message(
                message,
                f"Пожалуйста, подождите {wait_time:.1f} секунд перед отправкой следующего сообщения",
                None,
            )
            return

        chat_id = message.from_user.id
        await create_user_data(message)
        data_gpt = await get_state_ai(chat_id)

        # Получаем данные пользователя
        user_ai_list = await get_table_data("UsersAI")
        user_ai = next((u for u in user_ai_list if u.get("chatId") == chat_id), {})
        type_gpt = user_ai.get("typeGpt", "gpt-4o-mini")
        remaining_requests = data_gpt.get(type_gpt, 0)

        if remaining_requests <= 0:
            await new_message(
                message,
                "⚠️ У вас закончились доступные запросы для этого типа AI. "
                "Пожалуйста, обновите подписку.",
                None,
            )
            return

        # Устанавливаем in_progress
        await add_to_table("UsersAI", {"chatId": chat_id, "in_progress": True})

        try:
            await send_typing_action(message, "typing")

            # Обработка изображений
            if message.photo:
                # Получаем файл с наилучшим качеством
                photo = message.photo[-1]
                file_info = await message.bot.get_file(photo.file_id)
                file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"

                # Импортируем функцию анализа из нового модуля

                success = await handle_image_analysis(message, file_url)

                if success:
                    # Обновляем статистику
                    user_data = await get_state_ai(message.from_user.id)
                    if type_gpt in user_data:
                        user_data[type_gpt] -= 1
                    await add_to_table(
                        "StaticAIUsers",
                        {"chatId": message.from_user.id, "dataGpt": user_data},
                    )
            else:
                # Обычная обработка текста/голоса
                response, msg_old = await AI_choice(message, type_gpt)

                if response is not None and msg_old is not None:
                    # Обновляем статистику
                    user_data = await get_state_ai(message.from_user.id)
                    if type_gpt in user_data:
                        user_data[type_gpt] -= 1
                    await add_to_table(
                        "StaticAIUsers",
                        {"chatId": message.from_user.id, "dataGpt": user_data},
                    )

                    await asyncio.sleep(0.10)
                    await update_message(msg_old, str(response), await ai_menu_back())
                else:
                    await new_message(
                        message, "❌ Не удалось обработать ваш запрос", None
                    )

        finally:
            # Сбрасываем in_progress
            await add_to_table("UsersAI", {"chatId": chat_id, "in_progress": False})

    except Exception as e:
        await logs_bot("error", f"Error in handle_message: {str(e)}")
        error_msg = "⚠️ Произошла ошибка при обработке запроса.\n_Пожалуйста, попробуйте позже или выберите другую модель_."
        await new_message(message, error_msg, None)
        # Очищаем состояние в случае ошибки
        await state.clear()
