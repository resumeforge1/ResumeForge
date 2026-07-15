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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                absolute_expires_at TEXT,
                remember_me INTEGER DEFAULT 0,
                user_agent TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                display_name TEXT,
                email TEXT,
                preferred_resume_template TEXT DEFAULT 'general',
                default_industry TEXT DEFAULT '',
                location TEXT DEFAULT '',
                theme_preference TEXT DEFAULT 'light',
                notification_preferences TEXT DEFAULT '',
                api_provider_preferences TEXT DEFAULT 'mock',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                user_id INTEGER,
                success INTEGER DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT,
                reason TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_migration_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                legacy_assigned_to_user_id INTEGER,
                legacy_assigned_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(legacy_assigned_to_user_id) REFERENCES users(id)
            )
            """
        )
        ensure_table_columns(conn, "user_sessions", {"absolute_expires_at": "TEXT"})
        ensure_table_columns(conn, "login_audit_log", {"reason": "TEXT DEFAULT ''"})
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token)")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_search_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                target_role TEXT,
                location TEXT,
                commute_radius INTEGER DEFAULT 25,
                remote_preference TEXT DEFAULT 'any',
                minimum_salary INTEGER DEFAULT 0,
                employment_type TEXT DEFAULT 'any',
                preferred_schedule TEXT DEFAULT '',
                excluded_companies TEXT DEFAULT '[]',
                required_licenses_certifications TEXT DEFAULT '[]',
                last_checked_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discovered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_job_id TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                remote_type TEXT DEFAULT 'onsite',
                salary_min INTEGER,
                salary_max INTEGER,
                employment_type TEXT,
                schedule TEXT,
                description TEXT,
                posted_at TEXT,
                discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                apply_url TEXT,
                expires_at TEXT,
                expiration_status TEXT DEFAULT 'unknown',
                raw_payload TEXT DEFAULT '{}',
                normalized_key TEXT,
                discovery_state TEXT DEFAULT 'new',
                provider_confidence INTEGER DEFAULT 80,
                duplicate_confidence INTEGER DEFAULT 100,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_discovered_job_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                breakdown TEXT NOT NULL,
                matched_skills TEXT DEFAULT '[]',
                missing_qualifications TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER NOT NULL,
                status TEXT DEFAULT 'saved',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(client_id, discovered_job_id),
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS application_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER NOT NULL,
                tailored_resume TEXT NOT NULL,
                cover_letter TEXT NOT NULL,
                ats_keywords TEXT DEFAULT '[]',
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                filters TEXT DEFAULT '{}',
                jobs_found INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                enabled INTEGER DEFAULT 0,
                status TEXT DEFAULT 'not_configured',
                last_success_at TEXT,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_provider_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_key TEXT NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider_key, setting_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                related_job_id INTEGER,
                provider_key TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_schedule_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                interval_key TEXT DEFAULT 'daily',
                next_check_at TEXT,
                last_checked_at TEXT,
                running INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO job_schedule_settings (id) VALUES (1)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                provider_key TEXT NOT NULL,
                status TEXT NOT NULL,
                jobs_found INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                updated_jobs INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                message TEXT DEFAULT '',
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS imported_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER,
                source_url TEXT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                salary TEXT,
                posted_at TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_prep_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(client_id, discovered_job_id),
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS application_package_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                discovered_job_id INTEGER NOT NULL,
                package_json TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS application_package_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_version_id INTEGER NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(package_version_id) REFERENCES application_package_versions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS application_package_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_version_id INTEGER NOT NULL,
                export_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(package_version_id) REFERENCES application_package_versions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_coach_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                discovered_job_id INTEGER,
                mode TEXT DEFAULT 'General Interview',
                questions_json TEXT NOT NULL,
                current_index INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id),
                FOREIGN KEY(discovered_job_id) REFERENCES discovered_jobs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_coach_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_index INTEGER NOT NULL,
                answer TEXT DEFAULT '',
                review_json TEXT DEFAULT '{}',
                completed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, question_index),
                FOREIGN KEY(session_id) REFERENCES interview_coach_sessions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_coach_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                export_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES interview_coach_sessions(id)
            )
            """
        )
        for table in (
            "client_versions",
            "client_notes",
            "application_tracker",
            "jd_analyses",
            "job_search_profiles",
            "discovered_jobs",
            "job_matches",
            "saved_jobs",
            "application_packages",
            "job_search_runs",
            "job_alerts",
            "provider_run_logs",
            "imported_jobs",
            "interview_prep_notes",
            "application_package_versions",
            "application_package_notes",
            "application_package_exports",
            "interview_coach_sessions",
            "interview_coach_answers",
            "interview_coach_exports",
        ):
            ensure_table_columns(conn, table, {"user_id": "INTEGER"})
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)")
        conn.commit()


def ensure_client_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(clients)").fetchall()}
    columns = {
        "user_id": "INTEGER",
        "status": "TEXT DEFAULT 'Draft'",
        "notes": "TEXT DEFAULT ''",
        "archived_at": "TEXT",
        "deleted_at": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE clients ADD COLUMN {name} {definition}")


def ensure_discovered_job_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(discovered_jobs)").fetchall()}
    columns = {
        "discovery_state": "TEXT DEFAULT 'new'",
        "provider_confidence": "INTEGER DEFAULT 80",
        "duplicate_confidence": "INTEGER DEFAULT 100",
        "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE discovered_jobs ADD COLUMN {name} {definition}")


def ensure_table_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def save_client(data: dict[str, Any]) -> int:
    fields = {
        "user_id": data.get("user_id"),
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
                user_id, template_key, full_name, city_state, phone, email, target_role,
                professional_summary, certifications, skills, work_experience, education
            ) VALUES (
                :user_id, :template_key, :full_name, :city_state, :phone, :email, :target_role,
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
            SELECT id, user_id, full_name, target_role, template_key, status, archived_at, deleted_at, created_at
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
        "INSERT INTO client_versions (client_id, snapshot, reason, user_id) VALUES (?, ?, ?, ?)",
        (client_id, json.dumps(snapshot), reason, snapshot.get("user_id")),
    )
