from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from services.logging import logs_bot


async def get_general_menu(current_num: str = None) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔄 Перезапуск Бота",
                callback_data="Restart"
            ),
            InlineKeyboardButton(
                text="🔎 Выбрать нейросеть",
                callback_data="Mode"
            )
        ],
        [
            InlineKeyboardButton(
                text="🖇️ Профиль пользователя",
                callback_data="Profile"
            ),
            InlineKeyboardButton(
                text="🤖 Информация о боте",
                callback_data="Help"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💸 Подписка Plus",
                callback_data="Pay"
            ),
            InlineKeyboardButton(
                text="🔊 Генерация речи",
                callback_data="TSSGenerat"
            )
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
        button = InlineKeyboardButton(text=button_text, callback_data=model_id)
        
        row.append(button)
        if len(row) == 2:  # По две кнопки в ряду
            keyboard.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки, если есть
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку генерации речи
    keyboard.append([
        InlineKeyboardButton(
            text=f"Генерация речи {'✅' if current_model in ['tts_hd', 'tts'] else ''}", 
            callback_data="TSSGenerat"
        )
    ])
    
    # Кнопка возврата
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="BackButton")
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
                InlineKeyboardButton(
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
                InlineKeyboardButton(
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
    

async def tts_quality_menu() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора качества TTS.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с выбором качества и кнопкой возврата
    """
    try:
        keyboard = [
            [
                InlineKeyboardButton(text="Стандартное качество", callback_data="tts_quality_standard"),
                InlineKeyboardButton(text="HD качество", callback_data="tts_quality_hd")
            ],
            [
                InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="Mode_new")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception as e:
        await logs_bot("error", f"Error in tts_quality_menu: {e}")
        # Возвращаем пустую клавиатуру в случае ошибки
        return InlineKeyboardMarkup(inline_keyboard=[])