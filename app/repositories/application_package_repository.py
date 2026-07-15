from __future__ import annotations

import json
from typing import Any

from app.database import get_connection


class ApplicationPackageRepository:
    def create_version(self, client_id: int, job_id: int, package: dict[str, Any], status: str = "draft") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO application_package_versions (client_id, discovered_job_id, package_json, status)
                VALUES (?, ?, ?, ?)
                """,
                (client_id, job_id, json.dumps(package), status),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def latest_for_job(self, client_id: int, job_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM application_package_versions
                WHERE client_id = ? AND discovered_job_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (client_id, job_id),
            ).fetchone()
        return parse_package_row(dict(row)) if row else None

    def get_version(self, package_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM application_package_versions WHERE id = ?", (package_id,)).fetchone()
        return parse_package_row(dict(row)) if row else None

    def save_version(self, package_id: int, package: dict[str, Any], status: str = "draft") -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE application_package_versions
                SET package_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(package), status, package_id),
            )
            conn.commit()

    def add_note(self, package_id: int, note: str) -> None:
        if not note.strip():
            return
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO application_package_notes (package_version_id, note) VALUES (?, ?)",
                (package_id, note.strip()),
            )
            conn.commit()

    def notes(self, package_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM application_package_notes WHERE package_version_id = ? ORDER BY id DESC",
                (package_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_export(self, package_id: int, export_type: str, filename: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO application_package_exports (package_version_id, export_type, filename)
                VALUES (?, ?, ?)
                """,
                (package_id, export_type, filename),
            )
            conn.commit()

    def export_stats(self) -> dict[str, Any]:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS count FROM application_package_exports").fetchone()["count"]
            rows = conn.execute(
                """
                SELECT export_type, COUNT(*) AS count
                FROM application_package_exports
                GROUP BY export_type
                ORDER BY count DESC
                """
            ).fetchall()
        return {"total": total, "by_type": [dict(row) for row in rows]}

    def recent_packages(self, limit: int = 5) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT apv.id, apv.client_id, apv.discovered_job_id, apv.status, apv.created_at,
                       c.full_name, dj.company, dj.title
                FROM application_package_versions apv
                JOIN clients c ON c.id = apv.client_id
                JOIN discovered_jobs dj ON dj.id = apv.discovered_job_id
                ORDER BY apv.created_at DESC, apv.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def dashboard_counts(self) -> dict[str, Any]:
        with get_connection() as conn:
            prepared = conn.execute("SELECT COUNT(*) AS count FROM application_package_versions").fetchone()["count"]
            ready = conn.execute(
                "SELECT COUNT(*) AS count FROM application_package_versions WHERE status = 'ready to send'"
            ).fetchone()["count"]
        return {"prepared_applications": prepared, "applications_ready_to_send": ready}


def parse_package_row(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["package"] = json.loads(row.get("package_json") or "{}")
    except json.JSONDecodeError:
        row["package"] = {}
    return row
