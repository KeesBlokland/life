"""
/home/life/app/utils/util_db.py
Version: 1.1.0
Purpose: Database operations with bin collection table
Created: 2025-06-11
Updated: 2025-06-13 - Added bin_collections table
"""

import sqlite3
import json
import os
from datetime import datetime
from flask import current_app, g
from contextlib import closing

def get_db():
    """Get database connection for current request"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DB_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"DB connection opened: {current_app.config['DB_PATH']}")
    
    return g.db

def close_db(error=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()
        if current_app.config['DEBUG']:
            current_app.logger.debug("DB connection closed")

def init_db():
    """Initialize database with schema"""
    db_path = current_app.config['DB_PATH']
    db_dir = os.path.dirname(db_path)
    
    # Ensure database directory exists
    os.makedirs(db_dir, exist_ok=True)
    
    with closing(sqlite3.connect(db_path)) as db:
        # Read and execute schema
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                db.executescript(f.read())
        else:
            # Create tables if schema.sql doesn't exist
            create_tables(db)
        
        # Insert default data
        insert_defaults(db)
        db.commit()
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Database initialized at: {db_path}")

def create_tables(db):
    """Create database tables"""
    # Files table with soft delete
    db.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filetype TEXT,
            size INTEGER,
            checksum TEXT UNIQUE,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP,
            deleted BOOLEAN DEFAULT 0,
            deleted_date TIMESTAMP,
            is_duplicate_of INTEGER,
            FOREIGN KEY (is_duplicate_of) REFERENCES files(id)
        )
    ''')
    
    # Tags
    db.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # File-tag relationships
    db.execute('''
        CREATE TABLE IF NOT EXISTS file_tags (
            file_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (file_id, tag_id),
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    ''')
    
    # Metadata
    db.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            file_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            date_taken DATE,
            people TEXT,
            location TEXT,
            keywords TEXT,
            ocr_text TEXT,
            auto_category TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    ''')
    
    # Semantic relationships
    db.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL,
            related_terms TEXT NOT NULL
        )
    ''')
    
    # Learned associations
    db.execute('''
        CREATE TABLE IF NOT EXISTS learned_associations (
            file_id_1 INTEGER,
            file_id_2 INTEGER,
            strength REAL DEFAULT 1.0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (file_id_1, file_id_2),
            FOREIGN KEY (file_id_1) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY (file_id_2) REFERENCES files(id) ON DELETE CASCADE
        )
    ''')
    
    # Password storage
    db.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            purpose TEXT NOT NULL,
            username TEXT,
            password TEXT,
            hint TEXT,
            video_guide_path TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP
        )
    ''')
    
    # Calendar events
    db.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date DATE NOT NULL,
            time TIME,
            recurring TEXT,
            category TEXT,
            description TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bin collection schedule
    db.execute('''
        CREATE TABLE IF NOT EXISTS bin_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            time TIME,
            bin_types TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            notes TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Shopping list
    db.execute('''
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            quantity TEXT,
            completed BOOLEAN DEFAULT 0,
            common_item BOOLEAN DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Reminders
    db.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date DATE,
            recurring TEXT,
            completed BOOLEAN DEFAULT 0,
            completed_date TIMESTAMP,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Settings
    db.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for performance
    db.execute('CREATE INDEX IF NOT EXISTS idx_files_checksum ON files(checksum)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(deleted)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_metadata_keywords ON metadata(keywords)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_bin_collections_date ON bin_collections(date)')

def insert_defaults(db):
    """Insert default data"""
    # Default semantic relationships
    relationships = {
        "car": ["insurance", "registration", "maintenance", "fuel", "keys", "purchase", "warranty", "manual"],
        "medical": ["prescriptions", "insurance", "test results", "appointments", "vaccinations", "doctors"],
        "house": ["mortgage", "insurance", "utilities", "repairs", "property tax", "floor plans", "deeds"],
        "travel": ["passport", "visas", "tickets", "itinerary", "insurance", "vaccinations", "hotels"],
        "tax": ["returns", "receipts", "w2", "1099", "deductions", "accountant"],
        "insurance": ["health", "car", "house", "life", "claims", "policies"],
        "bank": ["statements", "checks", "deposits", "loans", "credit cards"],
        "legal": ["will", "power of attorney", "contracts", "deeds", "trusts"]
    }
    
    for term, related in relationships.items():
        db.execute(
            'INSERT OR IGNORE INTO relationships (term, related_terms) VALUES (?, ?)',
            (term, json.dumps(related))
        )
    
    # Default settings (keep for backwards compatibility, but bin schedule now uses bin_collections table)
    default_settings = {
        'backup_enabled': 'true',
        'backup_time': '02:00'
    }
    
    for key, value in default_settings.items():
        db.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
    
    if current_app.config['DEBUG']:
        current_app.logger.debug("Default data inserted")

def query_db(query, args=(), one=False):
    """Execute query and return results"""
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"DB Query: {query}")
        current_app.logger.debug(f"DB Args: {args}")
    
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"DB Result count: {len(rv)}")
    
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Execute query that modifies data"""
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"DB Execute: {query}")
        current_app.logger.debug(f"DB Args: {args}")
    
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"DB Rows affected: {cur.rowcount}")
    
    return cur.lastrowid

def parse_any_timestamp(timestamp_str):
    """Handle ALL timestamp formats created across sessions."""
    if not timestamp_str:
        return None
    
    try:
        ts = str(timestamp_str).strip()
        # Remove microseconds and timezone info
        ts = ts.split('.')[0].split('+')[0].split('Z')[0].replace('T', ' ')
        
        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
        for fmt in formats:
            try:
                return datetime.strptime(ts, fmt).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        return None
    except:
        return None