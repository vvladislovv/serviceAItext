from aiogram import Router, F
from aiogram.types import CallbackQuery
from Messages.inlinebutton import get_main_keyboard_mode, backstep_menu_message, get_general_menu
from Messages.localization import MESSAGES
from database.settingsdata import get_table_data, add_to_table, delete_user_history
from Messages.settingsmsg import new_message, update_message
from services.logging import logs_bot
from aiogram.fsm.context import FSMContext
router = Router(name=__name__)

@router.callback_query(F.data.in_({
    "Mode", "Mode_new", 
    "claude-3-5-sonnet", "claude-3-haiku", 
    "gpt-4o-mini", "gemini-1.5-flash", "gpt-4o",
    "deepseek-v3", "deepseek-r1", "o1-mini", "o1", "o3-mini"
}))
async def general_main_mode(call: CallbackQuery):
    get_data_user = await get_table_data("UsersAI")
    
    # Находим пользователя в списке записей
    user_data = next((user for user in get_data_user if user.get('chatId') == call.from_user.id), None)
    current_model = user_data.get('typeGpt', 'gpt-4o-mini') if user_data else 'gpt-4o-mini'

    if call.data != "Mode" and call.data != "Mode_new":
        if call.data == current_model:
            # Если выбрана та же модель, просто отвечаем на callback без обновления сообщения
            await call.answer()
            return
        
        # Если выбрана новая модель
        current_model = call.data
        await add_to_table("UsersAI", {
            "chatId": call.from_user.id,
            "typeGpt": current_model
        })
    
    # Обновляем сообщение только при смене модели или открытии меню
    keyboard = await get_main_keyboard_mode(current_model)
    try:
        if call.data == "Mode_new":
            await new_message(
                call.message, 
                MESSAGES['ru']['mode_ai'], 
                keyboard
            )
        else:
            await update_message(
                call.message, 
                MESSAGES['ru']['mode_ai'], 
                keyboard
            )
    except Exception as e:
        await call.answer("Произошла ошибка при обновлении сообщения")
        return


@router.callback_query(F.data == "Restart")
async def general_main_restart(call: CallbackQuery):
    try:
        
        # Очищаем историю
        await delete_user_history(call.from_user.id)
        
        # Обновляем сообщение
        await update_message(
            call.message,
            MESSAGES['ru']['reset_context'],
            await backstep_menu_message()
        )
        
    except Exception as e:
        await call.answer("Произошла ошибка при перезапуске")
        await logs_bot("error", f"Error in restart handler: {str(e)}")



@router.callback_query(F.data == "BackButton")
async def utils_back_button(call: CallbackQuery, state :FSMContext):
    await state.clear()
    await update_message(call.message, MESSAGES['ru']['start'], await get_general_menu())
