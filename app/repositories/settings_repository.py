from __future__ import annotations

from typing import Any

from app.database import get_connection


class SettingsRepository:
    def get(self) -> dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row) if row else {}

    def update(self, data: dict[str, Any]) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE settings SET
                    accent_color = ?,
                    font_family = ?,
                    header_style = ?,
                    resume_spacing = ?,
                    margins = ?,
                    section_order = ?,
                    agency_branding = ?
                WHERE id = 1
                """,
                (
                    data.get("accent_color", "#145a92"),
                    data.get("font_family", "Arial"),
                    data.get("header_style", "solid"),
                    data.get("resume_spacing", "compact"),
                    data.get("margins", "standard"),
                    data.get("section_order", ""),
                    data.get("agency_branding", "ResumeForge"),
                ),
            )
            conn.commit()
