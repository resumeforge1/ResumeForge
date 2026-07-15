from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from app.database import get_connection


SESSION_COOKIE = "rf_session"
CSRF_COOKIE = "rf_csrf"
SESSION_IDLE_HOURS = 8
REMEMBER_ME_DAYS = 30
ABSOLUTE_SESSION_DAYS = 30
MAX_PASSWORD_LENGTH = 128
LOCKOUT_FAILURES = 5
LOCKOUT_MINUTES = 15

USER_OWNED_TABLES = (
    "clients",
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
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    if not valid_password_length(password):
        raise ValueError("Password must be between 8 and 128 characters.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    if not valid_password_length(password) or not stored_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def valid_password_length(password: str) -> bool:
    return 8 <= len(password or "") <= MAX_PASSWORD_LENGTH


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def normalize_username(username: str, email: str) -> str:
    clean = " ".join(str(username or "").strip().split())
    return clean or normalize_email(email).split("@")[0]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def users_exist() -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return bool(row and row["count"])


def user_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return int(row["count"] or 0)


def create_user(email: str, username: str, password: str, is_admin: bool = False) -> int:
    clean_email = normalize_email(email)
    clean_username = normalize_username(username, clean_email)
    if not clean_email or "@" not in clean_email:
        raise ValueError("A valid email is required.")
    if not valid_password_length(password):
        raise ValueError("Password must be between 8 and 128 characters.")
    with get_connection() as conn:
        clean_username = unique_username(conn, clean_username)
        cursor = conn.execute(
            """
            INSERT INTO users (email, username, password_hash, is_admin)
            VALUES (?, ?, ?, ?)
            """,
            (clean_email, clean_username, hash_password(password), int(is_admin)),
        )
        user_id = int(cursor.lastrowid)
        conn.execute("INSERT OR IGNORE INTO user_preferences (user_id, display_name, email) VALUES (?, ?, ?)", (user_id, clean_username, clean_email))
        conn.commit()
    return user_id


def assign_legacy_data_to_admin(user_id: int) -> bool:
    """Claim pre-auth single-user records exactly once after first admin setup."""
    with get_connection() as conn:
        marker = conn.execute("SELECT legacy_assigned_to_user_id FROM auth_migration_state WHERE id = 1").fetchone()
        if marker and marker["legacy_assigned_to_user_id"]:
            return False
        for table in USER_OWNED_TABLES:
            conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (user_id,))
        conn.execute(
            """
            INSERT INTO auth_migration_state (id, legacy_assigned_to_user_id, legacy_assigned_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                legacy_assigned_to_user_id = COALESCE(auth_migration_state.legacy_assigned_to_user_id, excluded.legacy_assigned_to_user_id),
                legacy_assigned_at = COALESCE(auth_migration_state.legacy_assigned_at, excluded.legacy_assigned_at)
            """,
            (user_id,),
        )
        conn.commit()
    return True


def legacy_migration_state() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM auth_migration_state WHERE id = 1").fetchone()
    return dict(row) if row else {}


def unique_username(conn: Any, username: str) -> str:
    base = username[:80] or "user"
    candidate = base
    suffix = 2
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (candidate,)).fetchone():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    return dict(row) if row else None


def get_user(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_session(user_id: int, remember_me: bool = False, user_agent: str = "", ip_address: str = "") -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    now = utc_now()
    expires = now + (timedelta(days=REMEMBER_ME_DAYS) if remember_me else timedelta(hours=SESSION_IDLE_HOURS))
    absolute_expires = now + timedelta(days=ABSOLUTE_SESSION_DAYS)
    with get_connection() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL", (user_id,))
        conn.execute(
            """
            INSERT INTO user_sessions (user_id, session_token, csrf_token, expires_at, absolute_expires_at, remember_me, user_agent, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, token_hash(token), csrf_token, expires.isoformat(timespec="seconds"), absolute_expires.isoformat(timespec="seconds"), int(remember_me), user_agent[:255], ip_address[:80]),
        )
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()
    return {"token": token, "csrf_token": csrf_token, "expires_at": expires}


def get_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.*, u.email, u.username, u.is_admin, u.is_active
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.session_token = ? AND s.revoked_at IS NULL
            """,
            (token_hash(token),),
        ).fetchone()
    if not row:
        return None
    session = dict(row)
    expires_at = parse_datetime(session.get("expires_at"))
    absolute_expires_at = parse_datetime(session.get("absolute_expires_at"))
    if not expires_at or expires_at <= utc_now() or not absolute_expires_at or absolute_expires_at <= utc_now() or not session.get("is_active"):
        revoke_session(token)
        return None
    return session


def touch_session(token: str) -> None:
    session = get_session(token)
    if not session:
        return
    if int(session.get("remember_me") or 0):
        expires_at = utc_now() + timedelta(days=REMEMBER_ME_DAYS)
    else:
        expires_at = utc_now() + timedelta(hours=SESSION_IDLE_HOURS)
    with get_connection() as conn:
        conn.execute(
            "UPDATE user_sessions SET last_seen_at = CURRENT_TIMESTAMP, expires_at = ? WHERE session_token = ?",
            (expires_at.isoformat(timespec="seconds"), token_hash(token)),
        )
        conn.commit()


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with get_connection() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE session_token = ?", (token_hash(token),))
        conn.commit()


def authenticate(email: str, password: str, user_agent: str = "", ip_address: str = "") -> dict[str, Any] | None:
    clean_email = normalize_email(email)
    if is_locked_out(clean_email):
        record_login_attempt(clean_email, None, False, ip_address, user_agent, "locked")
        return None
    user = get_user_by_email(clean_email)
    success = bool(user and int(user.get("is_active") or 0) and verify_password(password, user.get("password_hash", "")))
    record_login_attempt(clean_email, user.get("id") if user else None, success, ip_address, user_agent, "")
    if success and user:
        clear_failed_attempts(clean_email)
    return user if success else None


def record_login_attempt(email: str, user_id: int | None, success: bool, ip_address: str = "", user_agent: str = "", reason: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO login_audit_log (email, user_id, success, ip_address, user_agent, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (email, user_id, int(success), ip_address[:80], user_agent[:255], reason[:80]),
        )
        conn.commit()


def clear_failed_attempts(email: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM login_audit_log WHERE email = ? AND success = 0", (email,))
        conn.commit()


def is_locked_out(email: str) -> bool:
    cutoff = (utc_now() - timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM login_audit_log WHERE email = ? AND success = 0 AND created_at >= ?",
            (email, cutoff),
        ).fetchone()
    return int(row["count"] or 0) >= LOCKOUT_FAILURES


def create_password_reset_token(email: str) -> str | None:
    user = get_user_by_email(email)
    if not user:
        return None
    token = secrets.token_urlsafe(24)
    expires = utc_now() + timedelta(hours=1)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user["id"], token_hash(token), expires.isoformat(timespec="seconds")),
        )
        conn.commit()
    return token


def get_user_preferences(user_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    user = get_user(user_id) or {}
    return {
        "display_name": user.get("username", ""),
        "email": user.get("email", ""),
        "preferred_resume_template": "general",
        "default_industry": "",
        "location": "",
        "theme_preference": "light",
        "notification_preferences": "",
        "api_provider_preferences": "mock",
    }


def save_user_preferences(user_id: int, data: dict[str, Any]) -> None:
    fields = {
        "user_id": user_id,
        "display_name": data.get("display_name", "").strip(),
        "email": data.get("email", "").strip().lower(),
        "preferred_resume_template": data.get("preferred_resume_template", "general").strip(),
        "default_industry": data.get("default_industry", "").strip(),
        "location": data.get("location", "").strip(),
        "theme_preference": data.get("theme_preference", "light").strip(),
        "notification_preferences": data.get("notification_preferences", "").strip(),
        "api_provider_preferences": data.get("api_provider_preferences", "mock").strip(),
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, display_name, email, preferred_resume_template, default_industry,
                location, theme_preference, notification_preferences, api_provider_preferences
            ) VALUES (
                :user_id, :display_name, :email, :preferred_resume_template, :default_industry,
                :location, :theme_preference, :notification_preferences, :api_provider_preferences
            )
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                email = excluded.email,
                preferred_resume_template = excluded.preferred_resume_template,
                default_industry = excluded.default_industry,
                location = excluded.location,
                theme_preference = excluded.theme_preference,
                notification_preferences = excluded.notification_preferences,
                api_provider_preferences = excluded.api_provider_preferences,
                updated_at = CURRENT_TIMESTAMP
            """,
            fields,
        )
        if fields["email"]:
            conn.execute("UPDATE users SET email = ?, username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (fields["email"], fields["display_name"] or fields["email"].split("@")[0], user_id))
        conn.commit()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None
