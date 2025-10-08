"""
Room Manager service for handling translation rooms
"""
import logging
from typing import Optional, List, Dict
from aiogram.types import Message
from aiogram import Bot

from ..core.app import db, bot
from ..models.room import Room, RoomMember, room_from_dict, member_from_dict
from ..services.translation import translate_text
from ..services.language import detect_language
from ..core.constants import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages translation rooms"""

    @staticmethod
    async def create_room(user_id: int, language_code: str, name: Optional[str] = None) -> str:
        """
        Create a new room

        Args:
            user_id: Creator user ID
            language_code: Creator's language
            name: Optional room name

        Returns:
            Room code
        """
        code = await db.create_room(user_id, language_code, name)
        logger.info(f"Room {code} created by user {user_id}")
        return code

    @staticmethod
    async def join_room(code: str, user_id: int, language_code: str) -> tuple[bool, str]:
        """
        Join room by code

        Args:
            code: Room code
            user_id: User ID to join
            language_code: User's language

        Returns:
            (success, message)
        """
        # Get room
        room_data = await db.get_room_by_code(code)
        if not room_data:
            return False, "❌ Room not found or closed"

        room = room_from_dict(room_data)

        # Check if expired
        if room.is_expired():
            await db.close_room(room.id)
            return False, "❌ Room has expired"

        # Check if already a member
        active_room = await db.get_user_active_room(user_id)
        if active_room:
            if active_room['id'] == room.id:
                return False, f"✅ You are already in room {code}"
            else:
                return False, f"❌ You are already in room {active_room['code']}"

        # Join room
        success = await db.join_room(room.id, user_id, language_code)
        if success:
            logger.info(f"User {user_id} joined room {code}")
            return True, f"✅ Joined room {code}"
        else:
            return False, "❌ Room is full or error occurred"

    @staticmethod
    async def leave_room(user_id: int) -> tuple[bool, str]:
        """
        Leave current active room

        Args:
            user_id: User ID

        Returns:
            (success, message)
        """
        active_room = await db.get_user_active_room(user_id)
        if not active_room:
            return False, "❌ You are not in any room"

        success = await db.leave_room(active_room['id'], user_id)
        if success:
            logger.info(f"User {user_id} left room {active_room['code']}")
            return True, f"✅ Left room {active_room['code']}"
        else:
            return False, "❌ Error leaving room"

    @staticmethod
    async def get_active_room(user_id: int) -> Optional[Room]:
        """
        Get user's active room

        Args:
            user_id: User ID

        Returns:
            Room object or None
        """
        room_data = await db.get_user_active_room(user_id)
        if not room_data:
            return None
        return room_from_dict(room_data)

    @staticmethod
    async def get_room_members(room_id: int) -> List[RoomMember]:
        """
        Get all members of a room

        Args:
            room_id: Room ID

        Returns:
            List of RoomMember objects
        """
        members_data = await db.get_room_members(room_id)
        return [member_from_dict(m) for m in members_data]

    @staticmethod
    async def close_room(room_id: int, user_id: int) -> tuple[bool, str]:
        """
        Close room (only creator can close)

        Args:
            room_id: Room ID
            user_id: User attempting to close

        Returns:
            (success, message)
        """
        # Get room to check creator
        members = await RoomManager.get_room_members(room_id)
        creator = next((m for m in members if m.is_creator()), None)

        if not creator or creator.user_id != user_id:
            return False, "❌ Only the room creator can close the room"

        success = await db.close_room(room_id)
        if success:
            logger.info(f"Room {room_id} closed by creator {user_id}")
            return True, "✅ Room closed"
        else:
            return False, "❌ Error closing room"

    @staticmethod
    async def broadcast_message(
        message: Message,
        room_id: int,
        sender_id: int,
        text: str,
        source_lang: str
    ):
        """
        Broadcast translated message to all room members

        Args:
            message: Original message object
            room_id: Room ID
            sender_id: Sender user ID
            text: Message text
            source_lang: Source language code
        """
        logger.info(f"🔍 DEBUG: broadcast_message called - room_id={room_id}, sender_id={sender_id}, text_len={len(text)}")

        # Get all members except sender
        members = await RoomManager.get_room_members(room_id)
        other_members = [m for m in members if m.user_id != sender_id]

        logger.info(f"🔍 DEBUG: Room has {len(members)} members, {len(other_members)} recipients")

        if not other_members:
            logger.info(f"No other members in room {room_id}")
            return

        # Get sender info
        sender = next((m for m in members if m.user_id == sender_id), None)
        if not sender:
            logger.error(f"Sender {sender_id} not found in room members")
            return

        sender_name = sender.display_name()
        sender_flag = SUPPORTED_LANGUAGES.get(source_lang, {}).get('flag', '🏳️')

        # Collect target languages from room members
        target_langs = {m.language_code for m in other_members}

        # Remove source language from targets
        if source_lang in target_langs:
            target_langs.remove(source_lang)

        if not target_langs:
            logger.info(f"All members speak {source_lang}, no translation needed")
            return

        # Translate to all unique target languages in the room
        translations = await translate_text(text, source_lang, target_langs)

        if not translations:
            logger.error(f"Translation failed for room {room_id}")
            await message.reply("❌ Translation failed")
            return

        # Send translated messages to each member
        for member in other_members:
            if member.language_code not in translations:
                continue

            translation = translations[member.language_code]
            target_flag = SUPPORTED_LANGUAGES.get(member.language_code, {}).get('flag', '🏳️')

            # Format message
            formatted_message = (
                f"💬 {sender_name} {sender_flag}:\n"
                f"→ {target_flag} {translation}"
            )

            try:
                await bot.send_message(member.user_id, formatted_message)
                logger.info(f"Message sent to user {member.user_id} in room {room_id}")
            except Exception as e:
                logger.error(f"Error sending message to user {member.user_id}: {e}")

        # Save message to history
        await db.save_room_message(room_id, sender_id, text, source_lang)
        logger.info(f"Message broadcast in room {room_id}: {len(other_members)} recipients")

    @staticmethod
    async def handle_room_message(message: Message, room: Room, text: Optional[str] = None):
        """
        Handle message in room context

        Args:
            message: Telegram message
            room: Room object
            text: Optional text override (for voice transcriptions)
        """
        user_id = message.from_user.id

        logger.info(f"🔍 DEBUG: handle_room_message called - user_id={user_id}, room={room.code}, message_id={message.message_id}, text_provided={text is not None}")

        # Use provided text or get from message
        if text is None:
            text = message.text

        if not text:
            await message.reply("❌ Empty message")
            return

        # Detect language
        source_lang = detect_language(text)
        if not source_lang:
            await message.reply(
                "❌ Could not detect language. Please use supported languages."
            )
            return

        logger.info(f"🔍 DEBUG: Broadcasting message - room_id={room.id}, sender={user_id}, lang={source_lang}")

        # Broadcast to other members
        await RoomManager.broadcast_message(
            message,
            room.id,
            user_id,
            text,
            source_lang
        )

        logger.info(f"🔍 DEBUG: Broadcast completed - room_id={room.id}, sender={user_id}")


# Global instance
room_manager = RoomManager()
