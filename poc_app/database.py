import sqlite3
from datetime import datetime
import json

DB_FILE = "shadow_audit_log.db"

def init_db():
    """Creates the audit table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            result_id TEXT,
            test_type TEXT,
            decision TEXT,
            reasoning TEXT,
            raw_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_decision(result: dict, decision: str, reasoning: list):
    """Writes a single decision to the auditable SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    raw_data_json = json.dumps(result)
    reasoning_str = " | ".join(reasoning) if reasoning else "All checks passed"

    cursor.execute('''
        INSERT INTO audit_log (timestamp, result_id, test_type, decision, reasoning, raw_data)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, result['id'], result['test_type'], decision, reasoning_str, raw_data_json))
    
    conn.commit()
    conn.close()

# Initialize the database when this module is imported
init_db()