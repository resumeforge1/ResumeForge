from __future__ import annotations

from typing import Any

from app.database import get_connection


class ApplicationRepository:
    def list_for_client(self, client_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM application_tracker WHERE client_id = ? ORDER BY id DESC",
                    (client_id,),
                ).fetchall()
            ]

    def create(self, client_id: int, data: dict[str, str]) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO application_tracker
                    (client_id, company, position, salary, status, date_applied, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    data.get("company", ""),
                    data.get("position", ""),
                    data.get("salary", ""),
                    data.get("status", "Applied"),
                    data.get("date_applied", ""),
                    data.get("notes", ""),
                ),
            )
            conn.commit()

    def update(self, application_id: int, data: dict[str, str]) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE application_tracker SET
                    company = ?,
                    position = ?,
                    salary = ?,
                    status = ?,
                    date_applied = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data.get("company", ""),
                    data.get("position", ""),
                    data.get("salary", ""),
                    data.get("status", "Applied"),
                    data.get("date_applied", ""),
                    data.get("notes", ""),
                    application_id,
                ),
            )
            conn.commit()

    def delete(self, application_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM application_tracker WHERE id = ?", (application_id,))
            conn.commit()
