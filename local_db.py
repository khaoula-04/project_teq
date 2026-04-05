import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class LocalDatabase:
    """
    Base de données locale SQLite.
    Les données étudiantes ne quittent jamais l'Edge.
    Conforme au principe de souveraineté numérique.
    """

    def __init__(self, db_path: str = "data/students.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT,
                stress_level TEXT,
                source TEXT,
                latency_ms REAL,
                timestamp TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS student_planning (
                student_id TEXT PRIMARY KEY,
                courses TEXT,
                preferences TEXT,
                last_updated TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                full_name TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        self._seed_default_users()

    def _seed_default_users(self):
        """Create default admin and student accounts if they don't exist."""
        defaults = [
            ("admin",   "admin123",   "admin",   "Administrateur"),
            ("student1","student123", "student", "Étudiant Demo"),
        ]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for username, password, role, full_name in defaults:
            c.execute("SELECT id FROM users WHERE username=?", (username,))
            if not c.fetchone():
                c.execute(
                    "INSERT INTO users (username,password_hash,role,full_name,created_at) VALUES (?,?,?,?,?)",
                    (username, generate_password_hash(password), role, full_name, datetime.now().isoformat())
                )
        conn.commit()
        conn.close()

    # ── Auth methods ──────────────────────────────────────────
    def get_user(self, username: str) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash, role, full_name FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "username": row[1], "password_hash": row[2], "role": row[3], "full_name": row[4]}
        return None

    def verify_user(self, username: str, password: str) -> dict | None:
        user = self.get_user(username)
        if user and check_password_hash(user["password_hash"], password):
            return user
        return None

    def create_user(self, username: str, password: str, role: str = "student", full_name: str = "") -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username,password_hash,role,full_name,created_at) VALUES (?,?,?,?,?)",
                (username, generate_password_hash(password), role, full_name, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_user(self, username: str) -> bool:
        if username in ("admin",):
            return False
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_all_users(self) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, username, role, full_name, created_at FROM users ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "username": r[1], "role": r[2], "full_name": r[3], "created_at": r[4]} for r in rows]

    def log_interaction(self, student_id: str, query: str, response: str,
                        stress_level: str, source: str, latency_ms: float):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO interactions
            (student_id, query, response, stress_level, source, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, query, response, stress_level,
              source, latency_ms, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_student_history(self, student_id: str, limit: int = 5) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT query, response, stress_level, source, latency_ms, timestamp
            FROM interactions
            WHERE student_id = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (student_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_stats(self, student_id: str = None) -> dict:
        """Retourne des statistiques globales ou par étudiant."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        where = "WHERE student_id=?" if student_id else ""
        args  = (student_id,) if student_id else ()
        c.execute(f"SELECT COUNT(*) FROM interactions {where}", args)
        total = c.fetchone()[0]
        c.execute(f"SELECT source, COUNT(*) FROM interactions {where} GROUP BY source", args)
        sources = dict(c.fetchall())
        c.execute(f"SELECT stress_level, COUNT(*) FROM interactions {where} GROUP BY stress_level", args)
        stress_counts = dict(c.fetchall())
        c.execute(f"SELECT AVG(latency_ms) FROM interactions {where}", args)
        avg_latency = c.fetchone()[0]
        conn.close()
        return {
            "total_interactions": total,
            "by_source": sources,
            "stress_distribution": stress_counts,
            "avg_latency_ms": round(avg_latency or 0, 2)
        }

    def get_all_interactions(self, limit: int = 50) -> list:
        """Admin only — all interactions across all students."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT student_id, query, stress_level, source, latency_ms, timestamp
            FROM interactions ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"student_id": r[0], "query": r[1], "stress": r[2],
                 "source": r[3], "latency": r[4], "timestamp": r[5]} for r in rows]

    def get_stress_alerts(self, limit: int = 20) -> list:
        """Admin only — recent high_stress interactions."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT student_id, query, timestamp
            FROM interactions
            WHERE stress_level IN ('high_stress','moderate_stress')
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"student_id": r[0], "query": r[1], "timestamp": r[2]} for r in rows]
