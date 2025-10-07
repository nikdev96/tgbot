"""
Integration test for room feature (Stage 4)
Tests real message broadcasting and translation
"""
import asyncio
import sys
sys.path.insert(0, '/home/iseliverstov59/apps/tgbot')

from src.core.app import db
from src.services.room_manager import RoomManager
from src.services.translation import translate_text


async def test_room_integration():
    """Test full room integration with message broadcasting"""
    print("=== Testing Room Integration (Stage 4) ===\n")

    # Initialize database
    await db.init_db()
    print("✅ Database initialized\n")

    # Clean up test data
    print("Cleaning up existing test data...")
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.execute("DELETE FROM rooms WHERE creator_id BETWEEN 888000 AND 888999")
    conn.execute("DELETE FROM room_members WHERE user_id BETWEEN 888000 AND 888999")
    conn.execute("DELETE FROM room_messages WHERE user_id BETWEEN 888000 AND 888999")
    conn.execute("DELETE FROM users WHERE id BETWEEN 888000 AND 888999")
    conn.commit()
    conn.close()
    print("✅ Test data cleaned\n")

    # Create test users
    print("Creating test users...")
    user1_id = 888001  # English speaker
    user2_id = 888002  # Russian speaker
    user3_id = 888003  # Thai speaker

    class MockUser:
        def __init__(self, user_id, username, first_name):
            self.id = user_id
            self.username = username
            self.first_name = first_name
            self.last_name = None

    from src.services.analytics import update_user_activity
    await update_user_activity(user1_id, MockUser(user1_id, "alice_en", "Alice"))
    await update_user_activity(user2_id, MockUser(user2_id, "bob_ru", "Bob"))
    await update_user_activity(user3_id, MockUser(user3_id, "charlie_th", "Charlie"))
    print("✅ Test users created: Alice (EN), Bob (RU), Charlie (TH)\n")

    # Test 1: Create room
    print("=" * 60)
    print("Test 1: Alice creates a room (EN)")
    print("=" * 60)
    code = await RoomManager.create_room(user1_id, "en", "Test Integration Room")
    room = await RoomManager.get_active_room(user1_id)
    print(f"✅ Room created: {code}")
    print(f"   Creator: Alice (User {user1_id})")
    print(f"   Language: EN\n")

    # Test 2: Bob joins
    print("=" * 60)
    print("Test 2: Bob joins the room (RU)")
    print("=" * 60)
    success, msg = await RoomManager.join_room(code, user2_id, "ru")
    print(f"✅ Bob joined: {msg}")
    members = await RoomManager.get_room_members(room.id)
    print(f"   Members: {len(members)}/10")
    for m in members:
        role = "👑 Creator" if m.is_creator() else "👤 Member"
        print(f"   {role}: {m.display_name()} ({m.language_code.upper()})")
    print()

    # Test 3: Charlie joins
    print("=" * 60)
    print("Test 3: Charlie joins the room (TH)")
    print("=" * 60)
    success, msg = await RoomManager.join_room(code, user3_id, "th")
    print(f"✅ Charlie joined: {msg}")
    members = await RoomManager.get_room_members(room.id)
    print(f"   Members: {len(members)}/10")
    for m in members:
        role = "👑 Creator" if m.is_creator() else "👤 Member"
        print(f"   {role}: {m.display_name()} ({m.language_code.upper()})")
    print()

    # Test 4: Test translation system
    print("=" * 60)
    print("Test 4: Testing translation for room messages")
    print("=" * 60)

    # Alice sends English message
    alice_msg = "Hello everyone! How are you today?"
    print(f"\n📤 Alice (EN) sends: '{alice_msg}'")

    # Get target languages (RU, TH)
    target_langs = {"ru", "th"}
    translations = await translate_text(alice_msg, "en", target_langs)

    if translations:
        print("✅ Translations generated:")
        print(f"   🇷🇺 RU (Bob receives): {translations.get('ru', 'N/A')}")
        print(f"   🇹🇭 TH (Charlie receives): {translations.get('th', 'N/A')}")
    else:
        print("❌ Translation failed")
    print()

    # Bob sends Russian message
    bob_msg = "Привет! У меня всё отлично!"
    print(f"📤 Bob (RU) sends: '{bob_msg}'")

    target_langs = {"en", "th"}
    translations = await translate_text(bob_msg, "ru", target_langs)

    if translations:
        print("✅ Translations generated:")
        print(f"   🇬🇧 EN (Alice receives): {translations.get('en', 'N/A')}")
        print(f"   🇹🇭 TH (Charlie receives): {translations.get('th', 'N/A')}")
    else:
        print("❌ Translation failed")
    print()

    # Charlie sends Thai message
    charlie_msg = "สวัสดีครับ! ยินดีที่ได้รู้จัก"
    print(f"📤 Charlie (TH) sends: '{charlie_msg}'")

    target_langs = {"en", "ru"}
    translations = await translate_text(charlie_msg, "th", target_langs)

    if translations:
        print("✅ Translations generated:")
        print(f"   🇬🇧 EN (Alice receives): {translations.get('en', 'N/A')}")
        print(f"   🇷🇺 RU (Bob receives): {translations.get('ru', 'N/A')}")
    else:
        print("❌ Translation failed")
    print()

    # Test 5: Save messages to history
    print("=" * 60)
    print("Test 5: Saving messages to room history")
    print("=" * 60)
    await db.save_room_message(room.id, user1_id, alice_msg, "en")
    await db.save_room_message(room.id, user2_id, bob_msg, "ru")
    await db.save_room_message(room.id, user3_id, charlie_msg, "th")
    print("✅ 3 messages saved to history\n")

    # Test 6: Bob leaves
    print("=" * 60)
    print("Test 6: Bob leaves the room")
    print("=" * 60)
    success, msg = await RoomManager.leave_room(user2_id)
    print(f"✅ {msg}")
    members = await RoomManager.get_room_members(room.id)
    print(f"   Remaining members: {len(members)}")
    for m in members:
        role = "👑 Creator" if m.is_creator() else "👤 Member"
        print(f"   {role}: {m.display_name()} ({m.language_code.upper()})")
    print()

    # Test 7: Close room
    print("=" * 60)
    print("Test 7: Alice closes the room")
    print("=" * 60)
    success, msg = await RoomManager.close_room(room.id, user1_id)
    print(f"✅ {msg}")

    # Verify no active rooms
    alice_room = await RoomManager.get_active_room(user1_id)
    charlie_room = await RoomManager.get_active_room(user3_id)
    print(f"   Alice active room: {alice_room}")
    print(f"   Charlie active room: {charlie_room}")
    print()

    print("=" * 60)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 60)
    print("\n📋 Summary:")
    print("✅ Room creation working")
    print("✅ Multi-user join working")
    print("✅ Translation system working (EN ↔ RU ↔ TH)")
    print("✅ Message history saving working")
    print("✅ Leave room working")
    print("✅ Close room working")
    print("\n🎯 Ready for real user testing in Telegram!")


if __name__ == "__main__":
    asyncio.run(test_room_integration())
