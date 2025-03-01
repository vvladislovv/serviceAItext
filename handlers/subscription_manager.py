from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, LabeledPrice
from config.confpaypass import cost_star
from Messages.localization import MESSAGES
import asyncio
from Messages.inlinebutton import backstep_menu_message, get_payment_link_keyboard
from Messages.settingsmsg import new_message, update_message
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