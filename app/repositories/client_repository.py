from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.database import create_client_version, get_client, get_connection, save_client


JSON_FIELDS = ("certifications", "skills", "work_experience", "education")


def serialize_client_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "status": data.get("status", "Draft"),
        "notes": data.get("notes", ""),
    }


class ClientRepository:
    def create(self, data: dict[str, Any]) -> int:
        return save_client(data)

    def get(self, client_id: int) -> dict[str, Any] | None:
        return get_client(client_id)

    def search(self, query: str = "", include_archived: bool = False) -> list[dict[str, Any]]:
        sql = """
            SELECT id, full_name, target_role, template_key, status, archived_at, deleted_at, created_at
            FROM clients
            WHERE deleted_at IS NULL
        """
        params: list[Any] = []
        if not include_archived:
            sql += " AND archived_at IS NULL"
        if query:
            sql += " AND (full_name LIKE ? OR email LIKE ? OR target_role LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        sql += " ORDER BY updated_at DESC, id DESC LIMIT 100"
        with get_connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def update(self, client_id: int, data: dict[str, Any], reason: str = "Updated client") -> None:
        fields = serialize_client_fields(data)
        fields["id"] = client_id
        with get_connection() as conn:
            create_client_version(conn, client_id, data, reason)
            conn.execute(
                """
                UPDATE clients SET
                    template_key = :template_key,
                    full_name = :full_name,
                    city_state = :city_state,
                    phone = :phone,
                    email = :email,
                    target_role = :target_role,
                    professional_summary = :professional_summary,
                    certifications = :certifications,
                    skills = :skills,
                    work_experience = :work_experience,
                    education = :education,
                    status = :status,
                    notes = :notes,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                fields,
            )
            conn.commit()

    def duplicate(self, client_id: int) -> int:
        client = self.get(client_id)
        if client is None:
            raise ValueError("Client not found")
        client["full_name"] = f"{client['full_name']} Copy"
        return self.create(client)

    def set_archived(self, client_id: int, archived: bool) -> None:
        value = datetime.utcnow().isoformat(timespec="seconds") if archived else None
        with get_connection() as conn:
            conn.execute("UPDATE clients SET archived_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, client_id))
            conn.commit()

    def soft_delete(self, client_id: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE clients SET deleted_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (datetime.utcnow().isoformat(timespec="seconds"), client_id),
            )
            conn.commit()

    def restore(self, client_id: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE clients SET deleted_at = NULL, archived_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (client_id,),
            )
            conn.commit()

    def versions(self, client_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT id, reason, created_at FROM client_versions WHERE client_id = ? ORDER BY id DESC",
                    (client_id,),
                ).fetchall()
            ]

    def add_note(self, client_id: int, note: str) -> None:
        if not note.strip():
            return
        with get_connection() as conn:
            conn.execute("INSERT INTO client_notes (client_id, note) VALUES (?, ?)", (client_id, note.strip()))
            conn.commit()

    def notes(self, client_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT id, note, created_at FROM client_notes WHERE client_id = ? ORDER BY id DESC",
                    (client_id,),
                ).fetchall()
            ]
