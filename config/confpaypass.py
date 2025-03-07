from pydantic_settings import BaseSettings
from Messages.settingsmsg import new_message


# PayPass
class PayPassConfig:
    BASE_PRICE: int = 590
    PRO_PRICE: int = 990


class PayPass(BaseSettings):
    stable_diffusion: int
    midjourney: int
    kandinsky: int
    leonardo: int
    flux: int
    dall_e_3: int
    dall_e_3_hd: int
    gpt_4_vision_preview: int  # Added gpt-4-vision-preview


def get_paypass(type_pass: str):
    """
    Возвращает настройки лимитов в зависимости от типа подписки

    type_pass: str
    Base - Базовая подписка - 590
    Pro - Профессиональная подписка - 990
    """
    if type_pass == "Base":
        return PayPass(
            stable_diffusion=15,
            midjourney=15,
            kandinsky=15,
            leonardo=15,
            flux=15,
            dall_e_3=15,
            dall_e_3_hd=15,
            gpt_4_vision_preview=15,  # Added limit for gpt-4-vision-preview
        )
    elif type_pass == "Pro":
        return PayPass(
            stable_diffusion=15,
            midjourney=15,
            kandinsky=15,
            leonardo=15,
            flux=15,
            dall_e_3=15,
            dall_e_3_hd=15,
            gpt_4_vision_preview=15,  # Added limit for gpt-4-vision-preview
        )
    elif type_pass == "NoBase":
        return PayPass(
            stable_diffusion=15,
            midjourney=15,
            kandinsky=15,
            leonardo=15,
            flux=15,
            dall_e_3=15,
            dall_e_3_hd=15,
            gpt_4_vision_preview=15,  # Added limit for gpt-4-vision-preview
        )


async def send_paypass_info(user_id: int, paypass_data: dict):
    try:
        text = f"Информация о подписке: {paypass_data}"
        await new_message(user_id, text)
    except Exception as e:
        await new_message(
            user_id, f"Ошибка при отправке информации о подписке: {str(e)}"
        )


def get_default_limits():
    """
    Возвращает словарь с лимитами по умолчанию (NoBase)

    Returns:
        dict: Словарь с API-именами моделей и их лимитами
    """
    paypass = get_paypass("NoBase")

    # Получаем все атрибуты PayPass
    paypass_dict = paypass.dict()

    # Преобразуем имена моделей из PayPass в API-имена
    limits = {}

    # Маппинг имен моделей из PayPass в API-имена
    model_mapping = {
        "stable_diffusion": "stable-diffusion",
        "midjourney": "midjourney",
        "kandinsky": "kandinsky",
        "leonardo": "leonardo",
        "flux": "flux",
        "dall_e_3": "dall-e-3",
        "dall_e_3_hd": "dall-e-3-hd",
        "gpt_4_vision_preview": "gpt-4-vision-preview",  # Added mapping for gpt-4-vision-preview
    }

    # Заполняем словарь лимитов
    for model_name, api_name in model_mapping.items():
        if model_name in paypass_dict:
            limits[api_name] = paypass_dict[model_name]

    return limits
