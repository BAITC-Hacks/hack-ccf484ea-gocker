from datetime import date
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)


def get_main_menu_keyboard(web_app_url: str = "") -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Добавить расход"), KeyboardButton(text="Итоги за месяц")],
        [KeyboardButton(text="Список расходов"), KeyboardButton(text="Установить бюджет")],
        [KeyboardButton(text="Экспорт в CSV"), KeyboardButton(text="Тестовый пример ТЗ")],
    ]
    if web_app_url:
        keyboard.append([KeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=web_app_url))])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def get_categories_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Еда"), KeyboardButton(text="Транспорт")],
        [KeyboardButton(text="Жильё"), KeyboardButton(text="Учёба")],
        [KeyboardButton(text="Кафе"), KeyboardButton(text="Развлечения")],
        [KeyboardButton(text="Покупки"), KeyboardButton(text="Другая категория")],
        [KeyboardButton(text="Отмена")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def get_date_keyboard() -> ReplyKeyboardMarkup:
    today_str = date.today().isoformat()
    buttons = [
        [KeyboardButton(text=f"Сегодня ({today_str})")],
        [KeyboardButton(text="Вчера"), KeyboardButton(text="Ввести вручную")],
        [KeyboardButton(text="Отмена")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def get_skip_description_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Пропустить")],
        [KeyboardButton(text="Отмена")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def get_month_nav_keyboard(current_month: str, prefix: str = "summary") -> InlineKeyboardMarkup:
    year, month = map(int, current_month.split("-"))
    prev_m = 12 if month == 1 else month - 1
    prev_y = year - 1 if month == 1 else year
    prev_month_str = f"{prev_y:04d}-{prev_m:02d}"

    next_m = 1 if month == 12 else month + 1
    next_y = year + 1 if month == 12 else year
    next_month_str = f"{next_y:04d}-{next_m:02d}"

    inline_keyboard = [
        [
            InlineKeyboardButton(text="< Пред. месяц", callback_data=f"{prefix}:{prev_month_str}"),
            InlineKeyboardButton(text=f"{current_month}", callback_data="noop"),
            InlineKeyboardButton(text="След. месяц >", callback_data=f"{prefix}:{next_month_str}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def get_expense_item_keyboard(expense_id: int, current_month: str) -> InlineKeyboardMarkup:
    inline_keyboard = [
        [
            InlineKeyboardButton(
                text="Удалить этот расход",
                callback_data=f"del:{expense_id}:{current_month}",
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
