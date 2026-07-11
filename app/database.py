import json
import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "resumeforge.sqlite3"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_key TEXT NOT NULL,
                full_name TEXT NOT NULL,
                city_state TEXT,
                phone TEXT,
                email TEXT,
                target_role TEXT,
                professional_summary TEXT,
                certifications TEXT,
                skills TEXT,
                work_experience TEXT,
                education TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_client_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS application_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                company TEXT,
                position TEXT,
                salary TEXT,
                status TEXT DEFAULT 'Applied',
                date_applied TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                accent_color TEXT DEFAULT '#145a92',
                font_family TEXT DEFAULT 'Arial',
                header_style TEXT DEFAULT 'solid',
                resume_spacing TEXT DEFAULT 'compact',
                margins TEXT DEFAULT 'standard',
                section_order TEXT DEFAULT 'summary,strengths,experience,certifications,skills,education',
                logo_path TEXT,
                agency_branding TEXT DEFAULT 'ResumeForge'
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO settings (id) VALUES (1)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jd_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                job_description TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.commit()


def ensure_client_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(clients)").fetchall()}
    columns = {
        "status": "TEXT DEFAULT 'Draft'",
        "notes": "TEXT DEFAULT ''",
        "archived_at": "TEXT",
        "deleted_at": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE clients ADD COLUMN {name} {definition}")


def save_client(data: dict[str, Any]) -> int:
    fields = {
        "template_key": data.get("template_key", "general"),
        "full_name": data.get("full_name", "").strip(),
        "city_state": data.get("city_state", "").strip(),
        "phone": data.get("phone", "").strip(),
        "email": data.get("email", "").strip(),
        "target_role": data.get("target_role", "").strip(),
        "professional_summary": data.get("professional_summary", "").strip(),
        "certifications": json.dumps(data.get("certifications", [])),
        "skills": json.dumps(data.get("skills", [])),
        "work_experience": json.dumps(data.get("work_experience", [])),
        "education": json.dumps(data.get("education", [])),
    }
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO clients (
                template_key, full_name, city_state, phone, email, target_role,
                professional_summary, certifications, skills, work_experience, education
            ) VALUES (
                :template_key, :full_name, :city_state, :phone, :email, :target_role,
                :professional_summary, :certifications, :skills, :work_experience, :education
            )
            """,
            fields,
        )
        client_id = int(cursor.lastrowid)
        create_client_version(conn, client_id, data, "Initial intake")
        conn.commit()
        return client_id


def get_client(client_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if row is None:
        return None

    client = dict(row)
    for key in ("certifications", "skills", "work_experience", "education"):
        raw_value = client.get(key) or "[]"
        try:
            client[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            client[key] = []
    return client


def list_clients(limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, full_name, target_role, template_key, status, archived_at, deleted_at, created_at
            FROM clients
            WHERE deleted_at IS NULL
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_client_version(
    conn: sqlite3.Connection, client_id: int, snapshot: dict[str, Any], reason: str
) -> None:
    conn.execute(
        "INSERT INTO client_versions (client_id, snapshot, reason) VALUES (?, ?, ?)",
        (client_id, json.dumps(snapshot), reason),
    )
