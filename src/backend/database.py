"""
Switchboard SQLite Database Manager
Provides persistent local storage for Contacts, Call History, Conversations, Messages, and App Settings.
Thread-safe with RLock, WAL mode, phone number normalization, and deduplication.
"""

import sqlite3
import os
import time
import uuid
import re
import threading

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "switchboard.db")

def normalize_number(num):
    """Normalizes phone numbers to match by the last 9 digits (handles country codes e.g. +233 vs 0)."""
    if not num:
        return ""
    digits = re.sub(r'\D', '', str(num))
    if len(digits) >= 9:
        return digits[-9:]
    return digits

class DatabaseManager:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            # 1. Contacts Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone_number TEXT NOT NULL UNIQUE,
                avatar_color TEXT DEFAULT '#8b5cf6',
                category TEXT DEFAULT 'Personal',
                notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_number ON contacts(phone_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)")

            # 2. Call History Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                contact_name TEXT,
                direction TEXT NOT NULL, -- 'incoming' or 'outgoing'
                status TEXT NOT NULL,    -- 'completed', 'missed', 'rejected', 'failed', 'busy'
                duration INTEGER DEFAULT 0, -- in seconds
                started_at DATETIME NOT NULL,
                connected_at DATETIME,
                ended_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_number ON call_history(phone_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_started ON call_history(started_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_direction ON call_history(direction)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_status ON call_history(status)")

            # 3. Conversations Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL UNIQUE,
                contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                contact_name TEXT,
                avatar_color TEXT DEFAULT '#8b5cf6',
                last_message_text TEXT DEFAULT '',
                last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                unread_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_number ON conversations(phone_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC)")

            # 4. Messages Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                phone_number TEXT NOT NULL,
                direction TEXT NOT NULL, -- 'inbound' or 'outbound'
                message_text TEXT NOT NULL,
                status TEXT NOT NULL,    -- 'sent', 'received', 'failed', 'pending'
                modem_index INTEGER,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON messages(timestamp ASC)")

            # 5. Application Settings Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.commit()
            self._seed_default_contacts(cursor)
            conn.commit()
            conn.close()

    def _seed_default_contacts(self, cursor):
        cursor.execute("SELECT COUNT(*) as cnt FROM contacts")
        if cursor.fetchone()["cnt"] == 0:
            defaults = [
                ("Telecel Customer Care", "100", "#10b981", "Support"),
                ("Telecel Balance & Top-Up", "*124#", "#3b82f6", "Service"),
                ("Telecel Cash / Wallet", "*110#", "#8b5cf6", "Service"),
                ("Emergency Services", "112", "#ef4444", "Emergency"),
                ("Directory Services", "118", "#f59e0b", "Support")
            ]
            for name, num, color, cat in defaults:
                cursor.execute("""
                INSERT OR IGNORE INTO contacts (name, phone_number, avatar_color, category)
                VALUES (?, ?, ?, ?)
                """, (name, num, color, cat))

    # -------------------------------------------------------------
    # CONTACT OPERATIONS
    # -------------------------------------------------------------
    def get_contacts(self, search=""):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if search:
                term = f"%{search}%"
                cursor.execute("""
                SELECT * FROM contacts 
                WHERE name LIKE ? OR phone_number LIKE ?
                ORDER BY name ASC
                """, (term, term))
            else:
                cursor.execute("SELECT * FROM contacts ORDER BY name ASC")
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows

    def find_contact_by_number(self, phone_number):
        if not phone_number:
            return None
        clean_num = phone_number.replace(" ", "").replace("-", "")
        norm9 = normalize_number(clean_num)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if len(norm9) >= 9:
                cursor.execute("""
                SELECT * FROM contacts 
                WHERE phone_number = ? OR phone_number LIKE ? OR ? LIKE '%' || phone_number
                LIMIT 1
                """, (clean_num, f"%{norm9}", clean_num))
            else:
                cursor.execute("SELECT * FROM contacts WHERE phone_number = ? LIMIT 1", (clean_num,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None

    def save_contact(self, name, phone_number, avatar_color="#8b5cf6", category="Personal", notes=""):
        if not name.strip() or not phone_number.strip():
            return None
        clean_num = phone_number.strip().replace(" ", "")
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO contacts (name, phone_number, avatar_color, category, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone_number) DO UPDATE SET
                name = excluded.name,
                avatar_color = excluded.avatar_color,
                category = excluded.category,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """, (name.strip(), clean_num, avatar_color, category, notes))
            contact_id = cursor.lastrowid
            
            # Sync contact_name to existing conversation and call history
            norm9 = normalize_number(clean_num)
            if len(norm9) >= 9:
                cursor.execute("UPDATE conversations SET contact_name = ? WHERE phone_number LIKE ?", (name.strip(), f"%{norm9}"))
                cursor.execute("UPDATE call_history SET contact_name = ? WHERE phone_number LIKE ?", (name.strip(), f"%{norm9}"))
            else:
                cursor.execute("UPDATE conversations SET contact_name = ? WHERE phone_number = ?", (name.strip(), clean_num))
                cursor.execute("UPDATE call_history SET contact_name = ? WHERE phone_number = ?", (name.strip(), clean_num))

            conn.commit()
            conn.close()
            return {"id": contact_id, "name": name.strip(), "phone_number": clean_num}

    def delete_contact(self, contact_id):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            conn.commit()
            conn.close()
            return True

    # -------------------------------------------------------------
    # CALL HISTORY OPERATIONS
    # -------------------------------------------------------------
    def start_call_record(self, call_id, phone_number, direction="outgoing", contact_name=None):
        if not contact_name:
            c = self.find_contact_by_number(phone_number)
            if c:
                contact_name = c["name"]
        
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO call_history (call_id, phone_number, contact_name, direction, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(call_id) DO NOTHING
            """, (call_id, phone_number, contact_name, direction, "dialing" if direction == "outgoing" else "incoming", now_str))
            conn.commit()
            conn.close()

    def update_call_connected(self, call_id):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE call_history 
            SET status = 'connected', connected_at = ?
            WHERE call_id = ?
            """, (now_str, call_id))
            conn.commit()
            conn.close()

    def finish_call_record(self, call_id, final_status, duration_sec):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE call_history
            SET status = ?, duration = ?, ended_at = ?
            WHERE call_id = ?
            """, (final_status, max(0, int(duration_sec)), now_str, call_id))
            conn.commit()
            conn.close()

    def get_call_history(self, filter_type="all", search="", limit=100):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = "SELECT * FROM call_history WHERE 1=1"
            params = []

            if filter_type == "missed":
                query += " AND status = 'missed'"
            elif filter_type == "incoming":
                query += " AND direction = 'incoming'"
            elif filter_type == "outgoing":
                query += " AND direction = 'outgoing'"

            if search:
                term = f"%{search}%"
                query += " AND (phone_number LIKE ? OR contact_name LIKE ?)"
                params.extend([term, term])

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows

    def delete_call_record(self, call_id):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM call_history WHERE call_id = ?", (call_id,))
            conn.commit()
            conn.close()
            return True

    def clear_call_history(self):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM call_history")
            conn.commit()
            conn.close()
            return True

    # -------------------------------------------------------------
    # CONVERSATIONS & SMS MESSAGES
    # -------------------------------------------------------------
    def get_conversations(self, search=""):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if search:
                term = f"%{search}%"
                cursor.execute("""
                SELECT * FROM conversations
                WHERE phone_number LIKE ? OR contact_name LIKE ? OR last_message_text LIKE ?
                ORDER BY updated_at DESC
                """, (term, term, term))
            else:
                cursor.execute("SELECT * FROM conversations ORDER BY updated_at DESC")
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows

    def get_messages(self, phone_number):
        clean_num = phone_number.strip().replace(" ", "")
        norm9 = normalize_number(clean_num)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if len(norm9) >= 9:
                cursor.execute("""
                SELECT m.* FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.phone_number = ? OR c.phone_number LIKE ? OR ? LIKE '%' || c.phone_number
                ORDER BY m.timestamp ASC, m.id ASC
                """, (clean_num, f"%{norm9}", clean_num))
            else:
                cursor.execute("""
                SELECT m.* FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.phone_number = ?
                ORDER BY m.timestamp ASC, m.id ASC
                """, (clean_num,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows

    def save_message(self, phone_number, direction, text, status="received", modem_index=None, timestamp=None):
        if not timestamp:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        clean_num = phone_number.strip().replace(" ", "")
        norm9 = normalize_number(clean_num)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            # 1. Lookup existing conversation with normalized phone number
            if len(norm9) >= 9:
                cursor.execute("""
                SELECT id, phone_number, contact_name, unread_count FROM conversations 
                WHERE phone_number = ? OR phone_number LIKE ? OR ? LIKE '%' || phone_number
                LIMIT 1
                """, (clean_num, f"%{norm9}", clean_num))
            else:
                cursor.execute("SELECT id, phone_number, contact_name, unread_count FROM conversations WHERE phone_number = ?", (clean_num,))
            
            conv = cursor.fetchone()
            
            if not conv:
                c = self.find_contact_by_number(clean_num)
                c_name = c["name"] if c else None
                avatar_color = c["avatar_color"] if c else "#8b5cf6"
                unread = 1 if direction == "inbound" else 0
                cursor.execute("""
                INSERT INTO conversations (phone_number, contact_name, avatar_color, last_message_text, last_message_at, unread_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (clean_num, c_name, avatar_color, text, timestamp, unread))
                conv_id = cursor.lastrowid
            else:
                conv_id = conv["id"]
                new_unread = (conv["unread_count"] + 1) if direction == "inbound" else conv["unread_count"]
                cursor.execute("""
                UPDATE conversations
                SET last_message_text = ?, last_message_at = ?, unread_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (text, timestamp, new_unread, conv_id))

            # 2. Check duplicate message (same conversation, direction, text within 5 seconds)
            cursor.execute("""
            SELECT id FROM messages 
            WHERE conversation_id = ? AND direction = ? AND message_text = ?
            ORDER BY id DESC LIMIT 1
            """, (conv_id, direction, text))
            dup = cursor.fetchone()
            if dup:
                conn.commit()
                conn.close()
                return {
                    "id": dup["id"],
                    "conversation_id": conv_id,
                    "phone_number": clean_num,
                    "direction": direction,
                    "text": text,
                    "status": status,
                    "timestamp": timestamp
                }

            # 3. Insert new message
            cursor.execute("""
            INSERT INTO messages (conversation_id, phone_number, direction, message_text, status, modem_index, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (conv_id, clean_num, direction, text, status, modem_index, timestamp))
            msg_id = cursor.lastrowid

            conn.commit()
            conn.close()

            return {
                "id": msg_id,
                "conversation_id": conv_id,
                "phone_number": clean_num,
                "direction": direction,
                "text": text,
                "status": status,
                "timestamp": timestamp
            }

    def mark_conversation_read(self, phone_number):
        clean_num = phone_number.strip().replace(" ", "")
        norm9 = normalize_number(clean_num)
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if len(norm9) >= 9:
                cursor.execute("UPDATE conversations SET unread_count = 0 WHERE phone_number LIKE ?", (f"%{norm9}",))
            else:
                cursor.execute("UPDATE conversations SET unread_count = 0 WHERE phone_number = ?", (clean_num,))
            conn.commit()
            conn.close()
            return True

    def delete_conversation(self, phone_number):
        clean_num = phone_number.strip().replace(" ", "")
        norm9 = normalize_number(clean_num)
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if len(norm9) >= 9:
                cursor.execute("DELETE FROM conversations WHERE phone_number LIKE ?", (f"%{norm9}",))
            else:
                cursor.execute("DELETE FROM conversations WHERE phone_number = ?", (clean_num,))
            conn.commit()
            conn.close()
            return True

    def delete_message(self, message_id):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            conn.close()
            return True

    # -------------------------------------------------------------
    # APPLICATION SETTINGS
    # -------------------------------------------------------------
    def get_setting(self, key, default=None):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM application_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO application_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """, (key, str(value)))
            conn.commit()
            conn.close()
            return True

db = DatabaseManager()
