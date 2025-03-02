from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, LabeledPrice
from config.confpaypass import cost_star
from Messages.localization import MESSAGES
import asyncio
from Messages.inlinebutton import backstep_menu_message, get_payment_link_keyboard
from Messages.settingsmsg import new_message, update_message
from database.settingsdata import add_to_table
from datetime import datetime, timedelta
from services.logging import logs_bot
from config.confpaypass import get_default_limits
router = Router(name=__name__)

@router.callback_query(F.data == "PayStar")
async def pay_star_menu(call: CallbackQuery, bot: Bot):
    prices = [LabeledPrice(label="XTR", amount=cost_star)]
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Подписка Plus",
        description=f"{MESSAGES['ru']["plus_info"]}"
                      f"{MESSAGES['ru']["cost_plus"]} {cost_star}⭐️",
        prices=prices,
        provider_token="",
        payload=f"{cost_star}_stars",
        currency="XTR"
    )

    await asyncio.sleep(1)

    await new_message(call.message, MESSAGES['ru']['pay_star_back'],
                                   await backstep_menu_message())

# card plus pay
@router.callback_query(F.data == "PayCard")
async def pay_card_button(call: CallbackQuery):
    await update_message(call.message, MESSAGES['ru']['pay_card'], await get_payment_link_keyboard())



async def update_pass_date(chat_id: int, user_pay_pass: str):
    # Convert input strings to datetime objects for proper comparison
    current_time = datetime.now()
    updated_pass = (current_time + timedelta(days=7)).strftime("%H:%M %d-%m-%Y")
    created_at = current_time.strftime("%H:%M %d-%m-%Y")
    
    datupdat = user_pay_pass.get("updated_pass", "")    
    tarif = user_pay_pass.get("tarif", "NoBase")

   # Convert both timestamps to datetime objects
    try:
        datupdat_dt = datetime.strptime(datupdat, "%H:%M %d-%m-%Y")
        created_at_dt = datetime.strptime(created_at, "%H:%M %d-%m-%Y")
    except ValueError as e:
        await logs_bot("error", f"Date parsing error for user {chat_id}: {str(e)}")
        return

    # Update only if created_at is greater than datupdat
    if created_at_dt >= datupdat_dt:
        await logs_bot("info", f"Updating pass date for user {chat_id}")
        await add_to_table("UsersPayPass", {
            "chatId": chat_id,
            "updated_pass": updated_pass
        })

        if tarif == "NoBase":
            static_ai_user = {
                'chatId': int(chat_id),
                'dataGpt': get_default_limits()
            }
        else:
            pass 
    
        await add_to_table("StaticAIUsers", static_ai_user)
    else:
        await logs_bot("info", f"Pass date for user {chat_id} is still valid, no update needed")