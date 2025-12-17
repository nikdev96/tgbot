#!/usr/bin/env python3
"""
Migration script: Replace Korean (ko) with Chinese (zh) in user preferences
"""
import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: str = "data/translator_bot.db"):
    """Migrate Korean language preferences to Chinese"""
    db_file = Path(db_path)

    if not db_file.exists():
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check how many users have 'ko' in preferences
        cursor.execute("""
            SELECT COUNT(*) FROM user_language_preferences
            WHERE language_code = 'ko'
        """)
        ko_count = cursor.fetchone()[0]

        print(f"📊 Found {ko_count} user preferences with Korean (ko)")

        if ko_count == 0:
            print("✅ No migration needed - no Korean preferences found")
            conn.close()
            return True

        # Update all 'ko' entries to 'zh'
        cursor.execute("""
            UPDATE user_language_preferences
            SET language_code = 'zh'
            WHERE language_code = 'ko'
        """)

        updated_count = cursor.rowcount
        conn.commit()

        print(f"✅ Successfully migrated {updated_count} preferences from Korean (ko) to Chinese (zh)")

        # Verify migration
        cursor.execute("""
            SELECT COUNT(*) FROM user_language_preferences
            WHERE language_code = 'zh'
        """)
        zh_count = cursor.fetchone()[0]

        print(f"📊 Total Chinese (zh) preferences after migration: {zh_count}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/translator_bot.db"
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)
