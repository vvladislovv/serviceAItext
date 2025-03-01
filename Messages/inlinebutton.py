from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from services.logging import logs_bot
from aiogram.types import InlineKeyboardButton as TypesInlineKeyboardButton


async def get_general_menu(current_num: str = None) -> InlineKeyboardMarkup:
    keyboard = [
        [
            TypesInlineKeyboardButton(
                text="🔄 Перезапуск Бота",
                callback_data="Restart"
            ),
            TypesInlineKeyboardButton(
                text="🔎 Выбрать нейросеть",
                callback_data="Mode"
            )
        ],
        [
            TypesInlineKeyboardButton(
                text="🖇️ Профиль пользователя",
                callback_data="Profile"
            ),
            TypesInlineKeyboardButton(
                text="🤖 Информация о боте",
                callback_data="Help"
            ),
        ],
        [
            TypesInlineKeyboardButton(
                text="💸 Подписка Plus",
                callback_data="Pay"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_main_keyboard_mode(current_model: str = None) -> InlineKeyboardMarkup:
    # Модели и их отображаемые названия
    models = {
        "claude-3-5-sonnet": "Claude 3.5 Sonnet",
        "claude-3-haiku": "Claude 3 Haiku",
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o mini",
        "gemini-1.5-flash": "Gemini 1.5 Flash",
        "deepseek-v3": "DeepSeek V3",
        "deepseek-r1": "DeepSeek R1",
        "o1-mini": "O1 Mini",
        "o1": "O1",
        "o3-mini": "O3 Mini"
    }
    
    # Формируем клавиатуру динамически
    keyboard = []
    row = []
    
    for model_id, model_name in models.items():
        # Добавляем галочку если модель выбрана
        button_text = f"{model_name} {'✅' if current_model == model_id else ''}"
        button = TypesInlineKeyboardButton(text=button_text, callback_data=model_id)
        
        row.append(button)
        if len(row) == 2:  # По две кнопки в ряду
            keyboard.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки, если есть
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку генерации речи
    keyboard.append([
        TypesInlineKeyboardButton(
            text=f"Генерация речи {'✅' if current_model in ['tts_hd', 'tts'] else ''}", 
            callback_data="TSSGenerat"
        )
    ])
    
    # Кнопка возврата
    keyboard.append([
        TypesInlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="BackButton")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def ai_menu_back() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой возврата в главное меню выбора.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой
    """
    try:
        keyboard = [
            [
                TypesInlineKeyboardButton(
                    text="🔎 Вернуться в меню выбора",
                    callback_data="Mode_new"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error in ai_menu_back: {e}")
        # Возвращаем пустую клавиатуру в случае ошибки
        return InlineKeyboardMarkup(inline_keyboard=[])


async def backstep_menu_message() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой возврата назад.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой
    """
    try:
        keyboard = [
            [
                TypesInlineKeyboardButton(
                    text="⬅️ Вернуться назад",
                    callback_data="BackButton"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error in backstep_menu_message: {e}")
        # Возвращаем пустую клавиатуру в случае ошибки
        return InlineKeyboardMarkup(inline_keyboard=[])
    

async def backstep_menu_message_pass() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой возврата назад.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой
    """
    try:
        keyboard = [
            [
                TypesInlineKeyboardButton(
                    text="⬅️ Вернуться назад",
                    callback_data="BackButton"
                )
            ],
            [
                TypesInlineKeyboardButton(
                    text="⭐️ Telegram Stars",
                    callback_data="PayStar"
                ),
                TypesInlineKeyboardButton(
                    text="💳 Банковская карта",
                    callback_data="PayCard"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error in backstep_menu_message: {e}")
        # Возвращаем пустую клавиатуру в случае ошибки
        return InlineKeyboardMarkup(inline_keyboard=[])
    

async def tts_quality_menu(has_tts=True, has_tts_hd=True):
    """Создает клавиатуру для выбора качества TTS"""
    keyboard = []
    
    # Добавляем только доступные опции
    row = []
    if has_tts:
        row.append(
            TypesInlineKeyboardButton(
                text="Стандартное качество", 
                callback_data="tts_quality_standard"
            )
        )
    
    if has_tts_hd:
        row.append(
            TypesInlineKeyboardButton(
                text="HD качество", 
                callback_data="tts_quality_hd"
            )
        )
    
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку возврата
    keyboard.append([
        TypesInlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data="back_to_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def create_tts_example_keyboard(quality: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с примером голоса и кнопкой возврата к выбору голоса
    
    Args:
        quality: str - текущее качество TTS ('tts' или 'tts-hd')
        
    Returns:
        InlineKeyboardMarkup: созданная клавиатура
    """
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔊 Послушать пример", 
                    callback_data="tts_example"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к выбору голоса",
                    callback_data="back_to_voice_selection"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Вернуться в главное меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error creating TTS example keyboard: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])

async def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для профиля пользователя"""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="💸 Купить Plus", 
                    callback_data="Pay"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад", 
                    callback_data="BackButton"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error creating profile keyboard: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])
    

async def get_pay_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оплаты"""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад", 
                    callback_data="BackButton"
                ),
                InlineKeyboardButton(
                    text="Продлить Plus", 
                    callback_data="ExtendPlus"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error creating pay keyboard: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])
    

async def get_payment_link_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с ссылкой на оплату"""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад", 
                    callback_data="Pay"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Ссылка на оплату 💳", 
                    url="https://www.google.com"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error creating payment link keyboard: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])