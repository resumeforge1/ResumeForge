from __future__ import annotations

import json
from typing import Any

from app.database import get_connection


JOB_STATUSES = (
    "discovered",
    "saved",
    "preparing",
    "ready to apply",
    "applied",
    "interview",
    "rejected",
    "offer",
    "dismissed",
)


class FreshJobsRepository:
    def get_profile(self, client_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM job_search_profiles WHERE client_id = ? ORDER BY id DESC", (client_id,)).fetchone()
        return parse_profile(dict(row)) if row else None

    def save_profile(self, client_id: int, data: dict[str, Any]) -> int:
        existing = self.get_profile(client_id)
        fields = serialize_profile(client_id, data)
        with get_connection() as conn:
            if existing:
                fields["id"] = existing["id"]
                conn.execute(
                    """
                    UPDATE job_search_profiles SET
                        target_role = :target_role,
                        location = :location,
                        commute_radius = :commute_radius,
                        remote_preference = :remote_preference,
                        minimum_salary = :minimum_salary,
                        employment_type = :employment_type,
                        preferred_schedule = :preferred_schedule,
                        excluded_companies = :excluded_companies,
                        required_licenses_certifications = :required_licenses_certifications,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """,
                    fields,
                )
                profile_id = int(existing["id"])
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO job_search_profiles (
                        client_id, target_role, location, commute_radius, remote_preference,
                        minimum_salary, employment_type, preferred_schedule, excluded_companies,
                        required_licenses_certifications
                    ) VALUES (
                        :client_id, :target_role, :location, :commute_radius, :remote_preference,
                        :minimum_salary, :employment_type, :preferred_schedule, :excluded_companies,
                        :required_licenses_certifications
                    )
                    """,
                    fields,
                )
                profile_id = int(cursor.lastrowid)
            conn.commit()
        return profile_id

    def mark_checked(self, client_id: int, checked_at: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE job_search_profiles SET last_checked_at = ?, updated_at = CURRENT_TIMESTAMP WHERE client_id = ?",
                (checked_at, client_id),
            )
            conn.commit()

    def create_run(self, client_id: int, provider: str, filters: dict[str, Any], jobs_found: int, new_jobs: int, checked_at: str) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO job_search_runs (client_id, provider, filters, jobs_found, new_jobs, last_checked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_id, provider, json.dumps(filters), jobs_found, new_jobs, checked_at),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def insert_job(self, job: dict[str, Any]) -> int:
        fields = serialize_job(job)
        duplicate = self.find_duplicate(fields)
        if duplicate:
            return int(duplicate["id"])
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO discovered_jobs (
                    source, source_job_id, company, title, location, remote_type, salary_min,
                    salary_max, employment_type, schedule, description, posted_at, discovered_at,
                    apply_url, expires_at, expiration_status, raw_payload, normalized_key
                ) VALUES (
                    :source, :source_job_id, :company, :title, :location, :remote_type, :salary_min,
                    :salary_max, :employment_type, :schedule, :description, :posted_at, :discovered_at,
                    :apply_url, :expires_at, :expiration_status, :raw_payload, :normalized_key
                )
                """,
                fields,
            )
            conn.commit()
            return int(cursor.lastrowid)

    def find_duplicate(self, fields: dict[str, Any]) -> dict[str, Any] | None:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM discovered_jobs
                WHERE (source = ? AND source_job_id = ?)
                   OR apply_url = ?
                   OR normalized_key = ?
                ORDER BY id LIMIT 1
                """,
                (fields["source"], fields["source_job_id"], fields["apply_url"], fields["normalized_key"]),
            ).fetchall()
        return dict(rows[0]) if rows else None

    def save_match(self, client_id: int, job_id: int, match: dict[str, Any]) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM job_matches WHERE client_id = ? AND discovered_job_id = ?", (client_id, job_id))
            conn.execute(
                """
                INSERT INTO job_matches (
                    client_id, discovered_job_id, score, breakdown, matched_skills, missing_qualifications
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    job_id,
                    int(match["score"]),
                    json.dumps(match.get("breakdown", {})),
                    json.dumps(match.get("matched_skills", [])),
                    json.dumps(match.get("missing_qualifications", [])),
                ),
            )
            conn.commit()

    def list_matches(self, client_id: int, sort: str = "best_match") -> list[dict[str, Any]]:
        order = {
            "best_match": "jm.score DESC, dj.posted_at DESC",
            "newest": "dj.posted_at DESC, jm.score DESC",
            "highest_salary": "COALESCE(dj.salary_max, dj.salary_min, 0) DESC, jm.score DESC",
        }.get(sort, "jm.score DESC, dj.posted_at DESC")
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT dj.*, jm.score, jm.breakdown, jm.matched_skills, jm.missing_qualifications,
                       sj.status AS saved_status
                FROM job_matches jm
                JOIN discovered_jobs dj ON dj.id = jm.discovered_job_id
                LEFT JOIN saved_jobs sj ON sj.discovered_job_id = dj.id AND sj.client_id = jm.client_id
                WHERE jm.client_id = ?
                ORDER BY {order}
                """,
                (client_id,),
            ).fetchall()
        return [parse_job_match(dict(row)) for row in rows]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM discovered_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def set_job_status(self, client_id: int, job_id: int, status: str, notes: str = "") -> None:
        if status not in JOB_STATUSES:
            raise ValueError("Invalid job status")
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO saved_jobs (client_id, discovered_job_id, status, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id, discovered_job_id)
                DO UPDATE SET status = excluded.status, notes = excluded.notes, updated_at = CURRENT_TIMESTAMP
                """,
                (client_id, job_id, status, notes),
            )
            conn.commit()

    def get_saved_status(self, client_id: int, job_id: int) -> str:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM saved_jobs WHERE client_id = ? AND discovered_job_id = ?",
                (client_id, job_id),
            ).fetchone()
        return str(row["status"]) if row else "discovered"

    def create_application_package(self, client_id: int, job_id: int, package: dict[str, Any]) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO application_packages (
                    client_id, discovered_job_id, tailored_resume, cover_letter, ats_keywords, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    job_id,
                    json.dumps(package.get("tailored_resume", {})),
                    package.get("cover_letter", ""),
                    json.dumps(package.get("ats_keywords", [])),
                    package.get("status", "draft"),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def package_for_job(self, client_id: int, job_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM application_packages
                WHERE client_id = ? AND discovered_job_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (client_id, job_id),
            ).fetchone()
        if row is None:
            return None
        package = dict(row)
        try:
            package["tailored_resume"] = json.loads(package.get("tailored_resume") or "{}")
        except json.JSONDecodeError:
            package["tailored_resume"] = {}
        try:
            package["ats_keywords"] = json.loads(package.get("ats_keywords") or "[]")
        except json.JSONDecodeError:
            package["ats_keywords"] = []
        return package


def serialize_profile(client_id: int, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_id": client_id,
        "target_role": str(data.get("target_role", "")).strip(),
        "location": str(data.get("location", "")).strip(),
        "commute_radius": int(data.get("commute_radius") or 25),
        "remote_preference": str(data.get("remote_preference", "any")).strip() or "any",
        "minimum_salary": int(data.get("minimum_salary") or 0),
        "employment_type": str(data.get("employment_type", "any")).strip() or "any",
        "preferred_schedule": str(data.get("preferred_schedule", "")).strip(),
        "excluded_companies": json.dumps(listify(data.get("excluded_companies", []))),
        "required_licenses_certifications": json.dumps(listify(data.get("required_licenses_certifications", []))),
    }


def parse_profile(profile: dict[str, Any]) -> dict[str, Any]:
    for field in ("excluded_companies", "required_licenses_certifications"):
        try:
            profile[field] = json.loads(profile.get(field) or "[]")
        except json.JSONDecodeError:
            profile[field] = []
    return profile


def serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": job.get("source", "mock"),
        "source_job_id": job.get("source_job_id", ""),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "remote_type": job.get("remote_type", "onsite"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "employment_type": job.get("employment_type", ""),
        "schedule": job.get("schedule", ""),
        "description": job.get("description", ""),
        "posted_at": job.get("posted_at", ""),
        "discovered_at": job.get("discovered_at", ""),
        "apply_url": job.get("apply_url", ""),
        "expires_at": job.get("expires_at", ""),
        "expiration_status": job.get("expiration_status", "unknown"),
        "raw_payload": json.dumps(job),
        "normalized_key": job.get("normalized_key", ""),
    }


def parse_job_match(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["breakdown"] = json.loads(row.get("breakdown") or "{}")
    except json.JSONDecodeError:
        row["breakdown"] = {}
    for field in ("matched_skills", "missing_qualifications"):
        try:
            row[field] = json.loads(row.get(field) or "[]")
        except json.JSONDecodeError:
            row[field] = []
    row["status"] = row.get("saved_status") or "discovered"
    return row


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("|", "\n").replace(",", "\n").splitlines() if item.strip()]
