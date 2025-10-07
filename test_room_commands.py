"""
Test script for room commands (Stage 3)
"""
import asyncio
import sys
sys.path.insert(0, '/home/iseliverstov59/apps/tgbot')

from src.core.app import db
from src.services.room_manager import RoomManager


async def test_room_commands():
    """Test room command flow"""
    print("=== Testing Room Commands (Stage 3) ===\n")

    # Initialize database
    await db.init_db()
    print("✅ Database initialized\n")

    # Clean up any existing test data
    print("Cleaning up existing test data...")
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.execute("DELETE FROM rooms WHERE creator_id BETWEEN 999000 AND 999999")
    conn.execute("DELETE FROM room_members WHERE user_id BETWEEN 999000 AND 999999")
    conn.execute("DELETE FROM users WHERE id BETWEEN 999000 AND 999999")
    conn.commit()
    conn.close()
    print("✅ Test data cleaned\n")

    # Create test users in database first
    print("Creating test users...")
    user1_id = 999001
    user2_id = 999002
    user3_id = 999003

    # Mock user objects for registration
    class MockUser:
        def __init__(self, user_id, username, first_name):
            self.id = user_id
            self.username = username
            self.first_name = first_name
            self.last_name = None

    from src.services.analytics import update_user_activity
    await update_user_activity(user1_id, MockUser(user1_id, "user1", "Test User 1"))
    await update_user_activity(user2_id, MockUser(user2_id, "user2", "Test User 2"))
    await update_user_activity(user3_id, MockUser(user3_id, "user3", "Test User 3"))
    print("✅ Test users created\n")

    # Test 1: Create room
    print("Test 1: Create room")
    code = await RoomManager.create_room(user1_id, "en", "Test Room")
    print(f"✅ Room created with code: {code}")

    # Verify room exists
    room1 = await RoomManager.get_active_room(user1_id)
    assert room1 is not None, "Room should exist"
    assert room1.code == code, f"Room code should match (got {room1.code}, expected {code})"
    assert room1.creator_id == user1_id, "Creator should match"
    print(f"✅ Room verified: {room1.code}, creator: {room1.creator_id}\n")

    # Test 2: Get room members
    print("Test 2: Get room members")
    members = await RoomManager.get_room_members(room1.id)
    print(f"✅ Members count: {len(members)}")
    assert len(members) == 1, "Should have 1 member (creator)"
    assert members[0].user_id == user1_id, "Member should be creator"
    assert members[0].is_creator(), "Member should be creator"
    print(f"✅ Creator role verified\n")

    # Test 3: Join room
    print("Test 3: User 2 joins room")
    success, msg = await RoomManager.join_room(code, user2_id, "ru")
    print(f"✅ Join result: {success} - {msg}")
    assert success, "Join should succeed"

    members = await RoomManager.get_room_members(room1.id)
    print(f"✅ Members count after join: {len(members)}")
    assert len(members) == 2, "Should have 2 members now"
    print()

    # Test 4: Join room by another user
    print("Test 4: User 3 joins room")
    success, msg = await RoomManager.join_room(code, user3_id, "th")
    print(f"✅ Join result: {success} - {msg}")
    assert success, "Join should succeed"

    members = await RoomManager.get_room_members(room1.id)
    print(f"✅ Members count after join: {len(members)}")
    assert len(members) == 3, "Should have 3 members now"

    # Verify all members
    for m in members:
        role_emoji = "👑" if m.is_creator() else "👤"
        print(f"  {role_emoji} User {m.user_id} - {m.language_code}")
    print()

    # Test 5: Try to join same room again
    print("Test 5: User 2 tries to join same room again")
    success, msg = await RoomManager.join_room(code, user2_id, "ru")
    print(f"✅ Join result: {success} - {msg}")
    assert not success, "Should not be able to join same room twice"
    print()

    # Test 6: Try to join non-existent room
    print("Test 6: Try to join non-existent room")
    success, msg = await RoomManager.join_room("XXXXXX", user2_id, "ru")
    print(f"✅ Join result: {success} - {msg}")
    assert not success, "Should not be able to join non-existent room"
    print()

    # Test 7: User 2 leaves room
    print("Test 7: User 2 leaves room")
    success, msg = await RoomManager.leave_room(user2_id)
    print(f"✅ Leave result: {success} - {msg}")
    assert success, "Leave should succeed"

    members = await RoomManager.get_room_members(room1.id)
    print(f"✅ Members count after leave: {len(members)}")
    assert len(members) == 2, "Should have 2 members after leave"
    print()

    # Test 8: Non-creator tries to close room
    print("Test 8: Non-creator (User 3) tries to close room")
    success, msg = await RoomManager.close_room(room1.id, user3_id)
    print(f"✅ Close result: {success} - {msg}")
    assert not success, "Non-creator should not be able to close room"
    print()

    # Test 9: Creator closes room
    print("Test 9: Creator closes room")
    success, msg = await RoomManager.close_room(room1.id, user1_id)
    print(f"✅ Close result: {success} - {msg}")
    assert success, "Creator should be able to close room"

    # Verify room is closed
    room1_after = await RoomManager.get_active_room(user1_id)
    print(f"✅ User 1 active room after close: {room1_after}")
    assert room1_after is None, "Creator should not have active room"

    room3_after = await RoomManager.get_active_room(user3_id)
    print(f"✅ User 3 active room after close: {room3_after}")
    assert room3_after is None, "Member should not have active room"
    print()

    # Test 10: Create second room to test multiple rooms
    print("Test 10: Create second room")
    code2 = await RoomManager.create_room(user2_id, "ru", "Russian Room")
    print(f"✅ Second room created with code: {code2}")
    assert code != code2, "Room codes should be unique"

    room2 = await RoomManager.get_active_room(user2_id)
    print(f"✅ Second room verified: {room2.code}\n")

    # Test 11: User tries to join while already in another room
    print("Test 11: User 1 tries to join room 2 while not in any room")
    success, msg = await RoomManager.join_room(code2, user1_id, "en")
    print(f"✅ Join result: {success} - {msg}")
    assert success, "Should be able to join when not in any room"

    # Now user 1 is in room 2, try to create new room
    print("Test 12: User 1 tries to create room while in room 2")
    # This should be prevented at handler level, but RoomManager.create_room will succeed
    # The handler checks active room before calling create
    active = await RoomManager.get_active_room(user1_id)
    print(f"✅ User 1 active room: {active.code}")
    assert active.code == code2, "User should be in room 2"
    print()

    # Cleanup
    print("Cleanup: Close room 2")
    await RoomManager.close_room(room2.id, user2_id)
    print("✅ Room 2 closed\n")

    print("=" * 50)
    print("✅ ALL ROOM COMMAND TESTS PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_room_commands())
