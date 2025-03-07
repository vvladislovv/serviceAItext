from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from Messages.settingsmsg import new_message, update_message
from Messages.inlinebutton import (
    backstep_menu_message,
    ai_menu_back,
    get_image_generation_keyboard,
)
from database.settingsdata import get_state_ai, get_table_data, add_to_table
from services.logging import logs_bot
from ai_services.openai_services import OpenAIService
from aiogram.types import FSInputFile

router = Router(name=__name__)


class GenerationState(StatesGroup):
    waiting_count = State()
    waiting_prompt = State()


# Словарь для хранения выбранного количества изображений для каждого пользователя
user_image_counts = {}


@router.callback_query(F.data == "ignore")
async def handle_ignore(call: CallbackQuery):
    """Обработчик нажатия неактивной кнопки"""
    await call.answer("Сначала выберите количество изображений")


@router.callback_query(F.data == "Analize_image")
async def handle_analyze_image(call: CallbackQuery):
    """Обработчик кнопки анализа изображения"""
    try:
        # Проверяем лимиты пользователя
        data_gpt = await get_state_ai(call.from_user.id)
        model = "gpt-4-vision-preview"
        remaining_requests = data_gpt.get(model, 0)

        if remaining_requests <= 0:
            await call.answer(
                "У вас закончились запросы для анализа изображений", show_alert=True
            )
            return

        await update_message(
            call.message,
            "🖼️ Отправьте изображение для анализа, и я подробно его опишу.",
            await backstep_menu_message(),
        )
        await add_to_table("UsersAI", {"chatId": call.from_user.id, "typeGpt": model})
    except Exception as e:
        await logs_bot("error", f"Error in handle_analyze_image: {e}")
        await call.answer("Произошла ошибка при обработке запроса")


@router.callback_query(F.data == "Generation_image")
async def handle_generation_image(call: CallbackQuery):
    """Обработчик кнопки генерации изображения"""
    try:
        # Получаем текущую модель пользователя из БД
        user_ai_list = await get_table_data("UsersAI")
        user_ai = next(
            (u for u in user_ai_list if u.get("chatId") == call.from_user.id), {}
        )
        model = user_ai.get("typeGpt", "dall-e3")

        # Проверяем, что используется правильная модель
        if model not in ["dall-e3", "dall-e3-hd"]:
            model = "dall-e-3"  # Устанавливаем значение по умолчанию

        # Проверяем лимиты пользователя
        data_gpt = await get_state_ai(call.from_user.id)
        remaining_requests = data_gpt.get(model, 0)

        if remaining_requests <= 0:
            await call.answer(
                f"У вас закончились запросы для генерации изображений в режиме {model}",
                show_alert=True,
            )
            return

        # Показываем клавиатуру выбора количества
        keyboard = await get_image_generation_keyboard()
        await update_message(
            call.message,
            f"🎨 Выберите количество изображений для генерации (модель {model}):",
            keyboard,
        )

        # Устанавливаем выбранную модель DALL-E
        await add_to_table("UsersAI", {"chatId": call.from_user.id, "typeGpt": model})

        # Очищаем предыдущий выбор пользователя
        user_image_counts[call.from_user.id] = None
    except Exception as e:
        await logs_bot("error", f"Error in handle_generation_image: {e}")
        await call.answer("Произошла ошибка при обработке запроса")


@router.callback_query(F.data.startswith("gen_count_"))
async def handle_generation_count(call: CallbackQuery):
    """Обработчик выбора количества изображений"""
    try:
        count = call.data.split("_")[-1]
        current_count = user_image_counts.get(call.from_user.id)

        # Если выбрано то же число, просто показываем уведомление
        if count == current_count:
            await call.answer("Это количество уже выбрано")
            return

        user_image_counts[call.from_user.id] = count

        # Обновляем клавиатуру с выбранным количеством
        keyboard = await get_image_generation_keyboard(count)
        await update_message(
            call.message,
            f"🎨 Выбрано {count} изображений\nНажмите '➡️ Продолжить' для ввода описания",
            keyboard,
        )
    except Exception as e:
        await logs_bot("error", f"Error in handle_generation_count: {e}")
        await call.answer("Произошла ошибка при обработке запроса")


@router.callback_query(F.data == "enter_prompt")
async def handle_enter_prompt(call: CallbackQuery, state: FSMContext):
    """Обработчик кнопки ввода промпта"""
    try:
        count = user_image_counts.get(call.from_user.id)
        if not count:
            await call.answer("Сначала выберите количество изображений")
            return

        await state.update_data(image_count=int(count))
        await state.set_state(GenerationState.waiting_prompt)

        await update_message(
            call.message,
            f"📝 Отлично! Теперь отправьте описание для генерации {count} изображений:",
            await backstep_menu_message(),
        )
    except Exception as e:
        await logs_bot("error", f"Error in handle_enter_prompt: {e}")
        await call.answer("Произошла ошибка при обработке запроса")


async def handle_image_generation(message: types.Message, prompt: str, count: int):
    """Обработка генерации изображений"""
    try:
        # Получаем тип модели из БД
        user_ai_list = await get_table_data("UsersAI")
        user_ai = next(
            (u for u in user_ai_list if u.get("chatId") == message.from_user.id), {}
        )
        model_type = user_ai.get("typeGpt", "dall-e-3")

        # Проверяем, что используется правильная модель
        if model_type not in ["dall-e-3", "dall-e-3-hd"]:
            model_type = "dall-e-3"

        # Проверяем лимиты
        data_gpt = await get_state_ai(message.from_user.id)
        remaining_requests = data_gpt.get(model_type, 0)

        if remaining_requests <= 0:
            await new_message(
                message,
                f"⚠️ У вас закончились запросы для модели {model_type}. "
                "Пожалуйста, обновите подписку или выберите другую модель.",
                None,
            )
            return False

        model_display_name = (
            "DALL-E 3 HD" if model_type == "dall-e-3-hd" else "DALL-E 3"
        )
        msg_old = await new_message(
            message,
            f"🎨 Генерирую {count} изображений используя {model_display_name}...",
            None,
        )

        # Генерируем изображения
        openai_service = OpenAIService()
        image_paths = await openai_service.generate_image(
            prompt, model_type, message.from_user.id, count
        )

        if image_paths and isinstance(image_paths, list):
            # Отправляем изображения с текстом
            for path in image_paths:
                try:
                    # Используем FSInputFile для отправки файла
                    photo = FSInputFile(path)
                    await message.answer_photo(
                        photo=photo,
                        caption=f"✨ Генерация завершена успешно!\nИспользована модель: {model_display_name}",
                    )
                except Exception as e:
                    await logs_bot("error", f"Error sending photo: {e}")

            # Обновляем сообщение о завершении
            await update_message(
                msg_old,
                "Генерация завершена успешно! Проверьте отправленные изображения.",
                await ai_menu_back(),
            )
            return True
        else:
            await update_message(msg_old, "❌ Ошибка при генерации изображений", None)
            return False
    except Exception as e:
        await logs_bot("error", f"Error in handle_image_generation: {e}")
        return False


async def handle_image_analysis(message: types.Message, file_url: str):
    """Обработка анализа изображений"""
    try:
        msg_old = await new_message(message, "🔍 Анализирую изображение...", None)

        # Получаем тип модели
        user_ai = next(
            (
                u
                for u in await get_table_data("UsersAI")
                if u.get("chatId") == message.from_user.id
            ),
            {},
        )
        model_type = "gpt-4-vision-preview"  # Всегда используем эту модель для анализа

        # Проверяем лимиты
        data_gpt = await get_state_ai(message.from_user.id)
        remaining_requests = data_gpt.get(model_type, 0)

        if remaining_requests <= 0:
            await update_message(
                msg_old,
                "⚠️ У вас закончились запросы для анализа изображений. "
                "Пожалуйста, обновите подписку.",
                None,
            )
            return False

        openai_service = OpenAIService()
        response = await openai_service.analyze_image(
            file_url,
            "Пожалуйста, опиши что изображено на этой картинке. Дай подробный анализ.",
            model_type,
        )

        if response:
            await update_message(msg_old, response, await ai_menu_back())
            return True
        else:
            await update_message(
                msg_old, "❌ Не удалось проанализировать изображение", None
            )
            return False
    except Exception as e:
        await logs_bot("error", f"Error in handle_image_analysis: {e}")
        await update_message(
            msg_old, "❌ Произошла ошибка при анализе изображения", None
        )
        return False
