#!/usr/bin/env python3
"""
cleanup_bins.py - Database cleanup script for bin data
Version: 1.0.0
Purpose: Remove ALL bin-related data from database to start fresh
Created: 2025-06-13
"""

import sqlite3
import os
import sys
from datetime import datetime

# Configuration
DB_PATH = '/home/life/data/database/life.db'

def confirm_action():
    """Ask user to confirm the destructive action"""
    print("🚨 WARNING: This will DELETE ALL bin-related data from the database!")
    print("\nThis will remove:")
    print("- All calendar events with category 'bin'")
    print("- All entries from bin_collections table")
    print("- All bin-related settings (refuse_*_day)")
    print("- This action CANNOT be undone!")
    
    response = input("\nAre you sure you want to continue? Type 'YES' to confirm: ")
    return response == 'YES'

def backup_database():
    """Create a backup before making changes"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False

def clean_bin_data():
    """Remove all bin-related data from database"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Count existing data before deletion
        cursor.execute("SELECT COUNT(*) FROM events WHERE category = 'bin'")
        bin_events_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bin_collections")
        bin_collections_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'refuse_%_day'")
        bin_settings_count = cursor.fetchone()[0]
        
        print(f"\n📊 Found bin data:")
        print(f"   - Bin calendar events: {bin_events_count}")
        print(f"   - Bin collection entries: {bin_collections_count}")
        print(f"   - Bin settings: {bin_settings_count}")
        
        if bin_events_count == 0 and bin_collections_count == 0 and bin_settings_count == 0:
            print("✅ No bin data found to clean!")
            return True
        
        # Delete bin-related calendar events
        cursor.execute("DELETE FROM events WHERE category = 'bin'")
        deleted_events = cursor.rowcount
        print(f"🗑️  Deleted {deleted_events} bin calendar events")
        
        # Drop and recreate bin_collections table (clears all data)
        cursor.execute("DROP TABLE IF EXISTS bin_collections")
        print("🗑️  Cleared bin_collections table")
        
        # Recreate empty bin_collections table
        cursor.execute('''
            CREATE TABLE bin_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                time TIME,
                bin_types TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bin_collections_date ON bin_collections(date)')
        print("✅ Recreated empty bin_collections table")
        
        # Delete bin-related settings
        cursor.execute("DELETE FROM settings WHERE key LIKE 'refuse_%_day'")
        deleted_settings = cursor.rowcount
        print(f"🗑️  Deleted {deleted_settings} bin settings")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"\n✅ Database cleanup completed successfully!")
        print(f"   - Calendar events removed: {deleted_events}")
        print(f"   - Bin collections cleared: ALL")
        print(f"   - Settings removed: {deleted_settings}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False

def main():
    """Main execution"""
    print("=" * 60)
    print("BIN DATA CLEANUP SCRIPT")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("Please check the path and try again.")
        sys.exit(1)
    
    # Confirm action
    if not confirm_action():
        print("❌ Operation cancelled by user")
        sys.exit(0)
    
    # Create backup
    print("\n📦 Creating database backup...")
    if not backup_database():
        print("❌ Cannot proceed without backup")
        sys.exit(1)
    
    # Clean bin data
    print("\n🧹 Cleaning bin data...")
    if clean_bin_data():
        print("\n🎉 Cleanup completed successfully!")
        print("\nNext steps:")
        print("1. Update your config.py to remove DEFAULT_BIN_SCHEDULE")
        print("2. Use /bins/schedule to set up your actual collection dates")
        print("3. Delete any remaining bin calendar events via /calendar/recurring")
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
