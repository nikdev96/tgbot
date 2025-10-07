"""
Room command handlers for creating and managing translation rooms
"""
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..core.app import audit_logger
from ..services.analytics import is_user_disabled, update_user_activity, get_user_preferences
from ..services.room_manager import RoomManager
from ..services.language import detect_language
from ..utils.room_keyboards import (
    build_rooms_main_menu,
    build_room_info_keyboard,
    build_members_list_keyboard,
    build_language_selection_keyboard
)
from ..states.room_states import RoomCreation, RoomJoining

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register room command handlers"""
    dp.message.register(room_command, Command("room"))

    # Register FSM handlers
    dp.message.register(handle_room_name, RoomCreation.waiting_for_name)
    dp.callback_query.register(handle_room_language_selection, RoomCreation.waiting_for_language, F.data.startswith("room_lang_"))
    dp.callback_query.register(handle_join_language_selection, RoomJoining.waiting_for_language, F.data.startswith("room_lang_"))
    dp.callback_query.register(handle_cancel, F.data == "room_cancel")

    # Register main callback handler
    dp.callback_query.register(room_callback, F.data.startswith("room_"))


async def room_command(message: Message):
    """Handle /room command - main rooms menu"""
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /room")
        await message.reply("❌ Access disabled")
        return

    # Update activity
    await update_user_activity(user_id, message.from_user)

    # Check if user has active room
    active_room = await RoomManager.get_active_room(user_id)

    if active_room:
        # Show room info if already in room
        members = await RoomManager.get_room_members(active_room.id)

        text = (
            f"🏠 *Комната: {active_room.code}*\n\n"
            f"👥 Участники: {len(members)}/{active_room.max_members}\n"
            f"⏰ Истекает: {active_room.expires_at.strftime('%Y-%m-%d %H:%M') if active_room.expires_at else 'Никогда'}\n\n"
            f"💬 Отправляйте сообщения - они будут переведены для всех участников!"
        )
        keyboard = build_room_info_keyboard(active_room, user_id)
        await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        # Show main menu
        text = (
            "🏠 *Переговорные комнаты*\n\n"
            "Создайте или присоединитесь к комнате для общения с автопереводом!\n\n"
            "*Возможности:*\n"
            "• Каждый пишет на своём языке\n"
            "• Сообщения автоматически переводятся для других\n"
            "• Ваш оригинальный текст сохраняется\n"
            "• Поддержка 2-10 участников"
        )
        keyboard = build_rooms_main_menu()
        await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Handle cancel button"""
    await state.clear()
    text = "❌ Операция отменена.\n\nИспользуйте /room для возврата в меню."
    await callback.message.edit_text(text)
    await callback.answer("Отменено")


async def room_callback(callback: CallbackQuery, state: FSMContext):
    """Handle room-related callbacks"""
    user_id = callback.from_user.id
    action = callback.data.split("_", 1)[1]

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update activity
    await update_user_activity(user_id, callback.from_user)

    if action == "create":
        # Create a new room
        await handle_create_room(callback, state)

    elif action == "join":
        # Show join instructions
        text = (
            "🔑 *Присоединиться к комнате*\n\n"
            "Чтобы присоединиться, отправьте команду:\n"
            "`/room join КОД`\n\n"
            "Пример: `/room join ABC123`\n\n"
            "Попросите создателя комнаты поделиться кодом!"
        )
        await callback.message.edit_text(text, parse_mode="Markdown")
        await callback.answer()

    elif action == "leave":
        # Leave current room
        success, msg = await RoomManager.leave_room(user_id)
        if success:
            text = (
                "👋 *Вы покинули комнату*\n\n"
                "Вы вышли из комнаты.\n"
                "Используйте /room чтобы создать или присоединиться к другой."
            )
            await callback.message.edit_text(text, parse_mode="Markdown")
            audit_logger.info(f"ROOM_ACTION: User {user_id} left room")
        else:
            await callback.message.edit_text(msg, parse_mode="Markdown")
        await callback.answer(msg)

    elif action == "close":
        # Close room (creator only)
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        success, msg = await RoomManager.close_room(active_room.id, user_id)
        if success:
            text = (
                f"🔒 *Комната закрыта*\n\n"
                f"Комната {active_room.code} была закрыта.\n"
                f"Все участники уведомлены."
            )
            await callback.message.edit_text(text, parse_mode="Markdown")

            # Notify all members
            members = await RoomManager.get_room_members(active_room.id)
            for member in members:
                if member.user_id != user_id:
                    try:
                        from ..core.app import bot
                        await bot.send_message(
                            member.user_id,
                            f"🔒 Комната {active_room.code} была закрыта создателем."
                        )
                    except Exception as e:
                        logger.error(f"Error notifying user {member.user_id}: {e}")

            audit_logger.info(f"ROOM_ACTION: User {user_id} closed room {active_room.code}")
        else:
            await callback.message.edit_text(msg, parse_mode="Markdown")
        await callback.answer(msg)

    elif action == "members":
        # Show members list
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        members = await RoomManager.get_room_members(active_room.id)
        if not members:
            await callback.answer("❌ No members found", show_alert=True)
            return

        from ..core.constants import SUPPORTED_LANGUAGES

        text = f"👥 *Комната {active_room.code} - Участники*\n\n"
        for member in members:
            lang_info = SUPPORTED_LANGUAGES.get(member.language_code, {})
            flag = lang_info.get('flag', '🏳️')
            role = "👑" if member.is_creator() else "👤"
            text += f"{role} {flag} {member.display_name()}\n"

        keyboard = build_members_list_keyboard(active_room)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()

    elif action == "info":
        # Show room info
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        members = await RoomManager.get_room_members(active_room.id)

        text = (
            f"🏠 *Комната: {active_room.code}*\n\n"
            f"👥 Участники: {len(members)}/{active_room.max_members}\n"
            f"⏰ Истекает: {active_room.expires_at.strftime('%Y-%m-%d %H:%M') if active_room.expires_at else 'Никогда'}\n\n"
            f"💬 Отправляйте сообщения - они будут переведены!"
        )
        keyboard = build_room_info_keyboard(active_room, user_id)
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
        await callback.answer()

    elif action == "share":
        # Share room invitation
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Не в комнате", show_alert=True)
            return

        members = await RoomManager.get_room_members(active_room.id)

        # Create share message
        from ..core.app import bot
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        # Create deep link for quick join
        deep_link = f"https://t.me/{bot_username}?start=join_{active_room.code}"

        share_text = (
            f"🎉 *Приглашение в комнату переводов!*\n\n"
            f"📌 Название: {active_room.name or '(без названия)'}\n"
            f"🔑 Код: `{active_room.code}`\n"
            f"👥 Участников: {len(members)}/{active_room.max_members}\n\n"
            f"💬 Присоединяйтесь для общения с автопереводом!\n"
            f"Каждый пишет на своём языке, сообщения переводятся автоматически.\n\n"
            f"*Два способа присоединиться:*\n"
            f"1️⃣ Нажмите на кнопку ниже\n"
            f"2️⃣ Отправьте команду: `/room join {active_room.code}`"
        )

        # Create keyboard with join button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Присоединиться к комнате", url=deep_link)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="room_info")]
        ])

        await callback.message.edit_text(share_text, parse_mode="Markdown", reply_markup=share_keyboard)
        await callback.answer("📤 Поделитесь этим сообщением!")


async def handle_create_room(callback: CallbackQuery, state: FSMContext):
    """Handle room creation - step 1: ask for room name"""
    user_id = callback.from_user.id

    # Check if user already in room
    active_room = await RoomManager.get_active_room(user_id)
    if active_room:
        await callback.answer(f"❌ Вы уже в комнате {active_room.code}", show_alert=True)
        return

    # Ask for room name
    text = (
        "📝 *Создание комнаты*\n\n"
        "Шаг 1 из 2: Введите название комнаты\n\n"
        "Например: `Команда разработки`, `Друзья`, `Проект XYZ`\n\n"
        "Или отправьте `/skip` чтобы пропустить"
    )

    await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(RoomCreation.waiting_for_name)
    await callback.answer()


async def handle_room_name(message: Message, state: FSMContext):
    """Handle room name input"""
    user_id = message.from_user.id
    room_name = message.text.strip()

    # Check for skip
    if room_name.lower() in ['/skip', 'skip', 'пропустить']:
        room_name = None

    # Validate name length
    if room_name and len(room_name) > 50:
        await message.reply(
            "❌ Название слишком длинное (макс. 50 символов).\n"
            "Попробуйте ещё раз или отправьте `/skip`"
        )
        return

    # Save room name to state
    await state.update_data(room_name=room_name)

    # Ask for language
    text = (
        f"📝 *Создание комнаты*\n\n"
        f"Название: {room_name or '(без названия)'}\n\n"
        f"Шаг 2 из 2: Выберите ваш язык"
    )

    keyboard = build_language_selection_keyboard()
    await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    await state.set_state(RoomCreation.waiting_for_language)


async def handle_room_language_selection(callback: CallbackQuery, state: FSMContext):
    """Handle language selection for room creation"""
    user_id = callback.from_user.id

    # Extract language code
    lang_code = callback.data.replace("room_lang_", "")

    # Get room name from state
    data = await state.get_data()
    room_name = data.get('room_name')

    # Create room
    try:
        code = await RoomManager.create_room(user_id, lang_code, room_name)

        from ..core.constants import SUPPORTED_LANGUAGES
        lang_info = SUPPORTED_LANGUAGES.get(lang_code, {})
        lang_flag = lang_info.get('flag', '🏳️')
        lang_name = lang_info.get('name', lang_code.upper())

        text = (
            f"✅ *Комната создана!*\n\n"
            f"📌 Название: {room_name or '(без названия)'}\n"
            f"🔑 Код комнаты: `{code}`\n"
            f"🗣️ Ваш язык: {lang_flag} {lang_name}\n\n"
            f"*Поделитесь кодом с другими:*\n"
            f"`/room join {code}`\n\n"
            f"💬 Начните отправлять сообщения!\n"
            f"Они будут автоматически переведены для всех участников."
        )

        room = await RoomManager.get_active_room(user_id)
        keyboard = build_room_info_keyboard(room, user_id)

        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        audit_logger.info(f"ROOM_ACTION: User {user_id} created room {code} with language {lang_code}")
        await callback.answer(f"✅ Комната {code} создана!")

        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error creating room: {e}")
        await callback.answer("❌ Ошибка создания комнаты", show_alert=True)
        await state.clear()


async def handle_join_command(message: Message, code: str, state: FSMContext):
    """
    Handle /room join CODE command - ask for language selection

    This is called from the main message handler when it detects 'room join' pattern
    """
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await message.reply("❌ Доступ запрещен")
        return

    # Update activity
    await update_user_activity(user_id, message.from_user)

    # Check if room exists
    room_data = await RoomManager.get_active_room(user_id)
    if room_data:
        await message.reply(f"❌ Вы уже в комнате {room_data.code}")
        return

    # Check if room code is valid
    from ..core.app import db
    room = await db.get_room_by_code(code.upper())
    if not room:
        await message.reply(f"❌ Комната {code.upper()} не найдена или закрыта")
        return

    # Save code to state and ask for language
    await state.update_data(room_code=code.upper())

    text = (
        f"🔑 *Присоединение к комнате {code.upper()}*\n\n"
        f"Выберите ваш язык для перевода:"
    )

    keyboard = build_language_selection_keyboard()
    await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    await state.set_state(RoomJoining.waiting_for_language)


async def handle_join_language_selection(callback: CallbackQuery, state: FSMContext):
    """Handle language selection for room joining"""
    user_id = callback.from_user.id

    # Extract language code
    lang_code = callback.data.replace("room_lang_", "")

    # Get room code from state
    data = await state.get_data()
    room_code = data.get('room_code')

    if not room_code:
        await callback.answer("❌ Ошибка: код комнаты не найден", show_alert=True)
        await state.clear()
        return

    # Join room
    success, msg = await RoomManager.join_room(room_code, user_id, lang_code)

    if success:
        active_room = await RoomManager.get_active_room(user_id)
        members = await RoomManager.get_room_members(active_room.id)

        from ..core.constants import SUPPORTED_LANGUAGES
        lang_info = SUPPORTED_LANGUAGES.get(lang_code, {})
        lang_flag = lang_info.get('flag', '🏳️')
        lang_name = lang_info.get('name', lang_code.upper())

        text = (
            f"✅ *Вы присоединились к комнате {room_code}!*\n\n"
            f"📌 Название: {active_room.name or '(без названия)'}\n"
            f"👥 Участники: {len(members)}/{active_room.max_members}\n"
            f"🗣️ Ваш язык: {lang_flag} {lang_name}\n\n"
            f"💬 Начните отправлять сообщения!\n"
            f"Ваши сообщения будут переведены на языки других участников."
        )

        keyboard = build_room_info_keyboard(active_room, user_id)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

        # Notify other members
        for member in members:
            if member.user_id != user_id:
                try:
                    from ..core.app import bot
                    user_name = callback.from_user.username or callback.from_user.first_name or f"Пользователь {user_id}"
                    await bot.send_message(
                        member.user_id,
                        f"👋 {user_name} присоединился к комнате!"
                    )
                except Exception as e:
                    logger.error(f"Error notifying member {member.user_id}: {e}")

        audit_logger.info(f"ROOM_ACTION: User {user_id} joined room {room_code} with language {lang_code}")
        await callback.answer(f"✅ Присоединились к {room_code}!")

        # Clear state
        await state.clear()
    else:
        await callback.message.edit_text(msg, parse_mode="Markdown")
        await callback.answer(msg, show_alert=True)
        await state.clear()
