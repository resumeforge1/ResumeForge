from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import get_connection
from app.document_generator import OUTPUT_DIR


APPLICATION_STATUSES = ("Interview Scheduled", "Offer")


def dashboard_stats() -> dict[str, Any]:
    with get_connection() as conn:
        total_clients = conn.execute(
            "SELECT COUNT(*) AS count FROM clients WHERE deleted_at IS NULL"
        ).fetchone()["count"]
        applications = conn.execute(
            "SELECT COUNT(*) AS count FROM application_tracker"
        ).fetchone()["count"]
        interviews = conn.execute(
            "SELECT COUNT(*) AS count FROM application_tracker WHERE status = ?",
            ("Interview Scheduled",),
        ).fetchone()["count"]
        offers = conn.execute(
            "SELECT COUNT(*) AS count FROM application_tracker WHERE status = ?",
            ("Offer",),
        ).fetchone()["count"]
        templates_used = conn.execute(
            "SELECT COUNT(DISTINCT template_key) AS count FROM clients WHERE deleted_at IS NULL"
        ).fetchone()["count"]
        recent_clients = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, full_name, target_role, status, updated_at
                FROM clients
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 5
                """
            ).fetchall()
        ]
    return {
        "total_clients": total_clients,
        "resumes_generated": count_generated_files(),
        "applications_tracked": applications,
        "interviews": interviews,
        "offers": offers,
        "templates_used": templates_used,
        "recent_activity": recent_clients,
    }


def count_generated_files() -> int:
    if not OUTPUT_DIR.exists():
        return 0
    return sum(1 for path in OUTPUT_DIR.iterdir() if path.is_file())


def generated_files_for_client(client_id: int) -> list[dict[str, Any]]:
    prefix = f"{client_id:04d}-"
    if not OUTPUT_DIR.exists():
        return []
    files = []
    for path in sorted(OUTPUT_DIR.glob(f"{prefix}*"), key=lambda item: item.stat().st_mtime, reverse=True):
        files.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
                "extension": path.suffix.upper().lstrip("."),
            }
        )
    return files


def client_timeline(client_id: int) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    with get_connection() as conn:
        for row in conn.execute(
            "SELECT reason, created_at FROM client_versions WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall():
            events.append({"label": row["reason"], "kind": "Version", "created_at": row["created_at"]})
        for row in conn.execute(
            "SELECT note, created_at FROM client_notes WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall():
            events.append({"label": row["note"], "kind": "Note", "created_at": row["created_at"]})
        for row in conn.execute(
            """
            SELECT company, position, status, created_at
            FROM application_tracker
            WHERE client_id = ?
            ORDER BY created_at DESC
            """,
            (client_id,),
        ).fetchall():
            label = " - ".join(filter(None, [row["company"], row["position"], row["status"]]))
            events.append({"label": label, "kind": "Application", "created_at": row["created_at"]})
    return sorted(events, key=lambda event: event["created_at"], reverse=True)[:12]
