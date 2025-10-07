"""
Keyboard builders for room feature
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_rooms_main_menu() -> InlineKeyboardMarkup:
    """
    Build main rooms menu keyboard

    Returns:
        InlineKeyboardMarkup with Create/Join buttons
    """
    keyboard = [
        [
            InlineKeyboardButton(text="➕ Create Room", callback_data="room_create"),
            InlineKeyboardButton(text="🔑 Join Room", callback_data="room_join")
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
        InlineKeyboardButton(text="👥 Members", callback_data="room_members"),
        InlineKeyboardButton(text="ℹ️ Info", callback_data="room_info")
    ])

    # Second row - Leave/Close button
    if room.creator_id == user_id:
        # Creator can close room
        keyboard.append([
            InlineKeyboardButton(text="🔒 Close Room", callback_data="room_close")
        ])
    else:
        # Regular members can leave
        keyboard.append([
            InlineKeyboardButton(text="👋 Leave Room", callback_data="room_leave")
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
            InlineKeyboardButton(text="◀️ Back to Room", callback_data="room_info")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
