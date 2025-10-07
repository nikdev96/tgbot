"""
Keyboard builders for room feature
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def build_rooms_main_menu() -> InlineKeyboardMarkup:
    """
    Build main rooms menu keyboard

    Returns:
        InlineKeyboardMarkup with Create/Join buttons
    """
    keyboard = [
        [
            InlineKeyboardButton(text="➕ Создать комнату", callback_data="room_create"),
            InlineKeyboardButton(text="🔑 Присоединиться", callback_data="room_join")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_room_info_keyboard(room, user_id: int) -> InlineKeyboardMarkup:
    """
    Build room info keyboard with management buttons

    Args:
        room: Room object
        user_id: Current user ID

    Returns:
        InlineKeyboardMarkup with room management buttons
    """
    keyboard = []

    # First row - Members and Info
    keyboard.append([
        InlineKeyboardButton(text="👥 Участники", callback_data="room_members"),
        InlineKeyboardButton(text="ℹ️ Инфо", callback_data="room_info")
    ])

    # Second row - Leave/Close button
    if room.creator_id == user_id:
        # Creator can close room
        keyboard.append([
            InlineKeyboardButton(text="🔒 Закрыть комнату", callback_data="room_close")
        ])
    else:
        # Regular members can leave
        keyboard.append([
            InlineKeyboardButton(text="👋 Выйти из комнаты", callback_data="room_leave")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_members_list_keyboard(room) -> InlineKeyboardMarkup:
    """
    Build members list keyboard with back button

    Args:
        room: Room object

    Returns:
        InlineKeyboardMarkup with back button
    """
    keyboard = [
        [
            InlineKeyboardButton(text="◀️ Назад к комнате", callback_data="room_info")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_language_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Build language selection keyboard

    Returns:
        InlineKeyboardMarkup with language options
    """
    from ..core.constants import SUPPORTED_LANGUAGES

    keyboard = []

    # Create rows of 2 languages each
    row = []
    for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
        flag = lang_info.get('flag', '🏳️')
        name = lang_info.get('name', lang_code.upper())

        button = InlineKeyboardButton(
            text=f"{flag} {name}",
            callback_data=f"room_lang_{lang_code}"
        )
        row.append(button)

        # Add row when we have 2 buttons
        if len(row) == 2:
            keyboard.append(row)
            row = []

    # Add remaining button if any
    if row:
        keyboard.append(row)

    # Add cancel button
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="room_cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
