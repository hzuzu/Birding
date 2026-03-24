"""
database.py — SQLite sightings log for the Bird Feeder Camera App.
"""
import sqlite3
from datetime import datetime
from config import DB_PATH


class SightingsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sightings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                species     TEXT    NOT NULL,
                common_name TEXT,
                confidence  TEXT,
                photo_path  TEXT,
                description TEXT
            )
        """)
        self.conn.commit()

    def insert_sighting(self, species, common_name, confidence, photo_path, description):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """INSERT INTO sightings
               (timestamp, species, common_name, confidence, photo_path, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, species, common_name, confidence, photo_path, description),
        )
        self.conn.commit()

    def get_recent(self, n=50):
        cursor = self.conn.execute(
            "SELECT * FROM sightings ORDER BY id DESC LIMIT ?", (n,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def count_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM sightings WHERE timestamp LIKE ?", (f"{today}%",)
        )
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()
