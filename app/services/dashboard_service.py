from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.database import get_connection
from app.document_generator import OUTPUT_DIR
from app.repositories.fresh_jobs_repository import JOB_STATUSES
from app.repositories.application_package_repository import ApplicationPackageRepository
from app.services.fresh_jobs import parse_salary_range


APPLICATION_STATUSES = ("Interview Scheduled", "Offer")
PIPELINE_STATUSES = (
    "discovered",
    "saved",
    "preparing",
    "ready to apply",
    "applied",
    "interview",
    "offer",
    "rejected",
    "accepted",
    "dismissed",
)


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


def career_dashboard(client: dict[str, Any] | None = None) -> dict[str, Any]:
    package_repo = ApplicationPackageRepository()
    package_counts = package_repo.dashboard_counts()
    export_stats = package_repo.export_stats()
    return {
        "client": client,
        "welcome_name": (client or {}).get("full_name") or "ResumeForge user",
        "resume_score": resume_readiness_score(client or {}),
        "jobs": job_count_summary((client or {}).get("id")),
        "pipeline": application_pipeline((client or {}).get("id")),
        "salary": salary_insights((client or {}).get("id")),
        "analytics": career_analytics((client or {}).get("id")),
        "providers": provider_health_summary(),
        "alerts": unread_alerts((client or {}).get("id")),
        "recent_matches": recent_match_cards((client or {}).get("id")),
        "packages": {
            **package_counts,
            "recent": package_repo.recent_packages(),
            "export_statistics": export_stats,
            "top_improving_resume": top_improving_resume((client or {}).get("id")),
            "average_match_score": average_match_score((client or {}).get("id")),
        },
    }


def resume_readiness_score(client: dict[str, Any]) -> dict[str, Any]:
    if not client:
        return {
            "score": 0,
            "label": "ResumeForge internal readiness score",
            "breakdown": {},
            "improvements": ["Create or import a resume to calculate readiness."],
        }
    work = client.get("work_experience", []) or []
    skills = client.get("skills", []) or []
    certifications = client.get("certifications", []) or []
    education = client.get("education", []) or []
    components = {
        "contact_information": 100 if all(client.get(field) for field in ("full_name", "phone", "email", "city_state")) else 50,
        "summary": 100 if len(str(client.get("professional_summary", "")).split()) >= 20 else (60 if client.get("professional_summary") else 0),
        "work_history": work_history_score(work),
        "education": 100 if education else 0,
        "skills": min(100, len(skills) * 12),
        "certifications": min(100, len(certifications) * 25),
        "measurable_achievements": measurable_achievement_score(work),
        "formatting_readiness": 100 if client.get("template_key") and client.get("target_role") else 70,
    }
    weights = {
        "contact_information": 0.14,
        "summary": 0.14,
        "work_history": 0.22,
        "education": 0.10,
        "skills": 0.16,
        "certifications": 0.10,
        "measurable_achievements": 0.08,
        "formatting_readiness": 0.06,
    }
    score = round(sum(components[key] * weights[key] for key in components))
    improvements = readiness_improvements(client, components)
    return {
        "score": max(0, min(100, score)),
        "label": "ResumeForge internal readiness score",
        "breakdown": components,
        "improvements": improvements,
    }


def work_history_score(work: list[dict[str, Any]]) -> int:
    if not work:
        return 0
    complete = 0
    for entry in work:
        fields = [entry.get("employer"), entry.get("job_title"), entry.get("start_date"), entry.get("end_date")]
        bullets = entry.get("bullets", []) or []
        if all(fields) and bullets:
            complete += 1
    return round((complete / max(1, len(work))) * 100)


def measurable_achievement_score(work: list[dict[str, Any]]) -> int:
    bullets = " ".join(" ".join(entry.get("bullets", []) or []) for entry in work)
    measures = len(re.findall(r"\b\d+[%+]?\b|\b\d{1,3},\d{3}\b", bullets))
    return min(100, measures * 20)


def readiness_improvements(client: dict[str, Any], components: dict[str, int]) -> list[str]:
    messages = []
    if components["contact_information"] < 100:
        messages.append("Complete name, phone, email, and city/state.")
    if components["summary"] < 100:
        messages.append("Add a concise professional summary with role focus.")
    if components["work_history"] < 100:
        messages.append("Complete employers, titles, dates, and bullet points for each role.")
    if components["education"] == 0:
        messages.append("Add education or training details if available.")
    if components["skills"] < 70:
        messages.append("Add individual skills instead of broad combined text.")
    if components["certifications"] < 50:
        messages.append("Add licenses or certifications already earned.")
    if components["measurable_achievements"] < 40:
        messages.append("Add measurable achievements where facts support them.")
    return messages or ["Resume is ready for review and job-specific tailoring."]


def job_count_summary(client_id: int | None = None) -> dict[str, Any]:
    where = ""
    params: list[Any] = []
    if client_id:
        where = "WHERE jm.client_id = ?"
        params.append(client_id)
    with get_connection() as conn:
        discovered = conn.execute("SELECT COUNT(*) AS count FROM discovered_jobs").fetchone()["count"]
        by_state = {
            row["discovery_state"] or "new": row["count"]
            for row in conn.execute("SELECT discovery_state, COUNT(*) AS count FROM discovered_jobs GROUP BY discovery_state").fetchall()
        }
        saved_counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM saved_jobs WHERE (? IS NULL OR client_id = ?) GROUP BY status",
                (client_id, client_id),
            ).fetchall()
        }
        match_row = conn.execute(
            f"SELECT COUNT(*) AS total, AVG(score) AS average_score, SUM(CASE WHEN score >= 75 THEN 1 ELSE 0 END) AS high_matches FROM job_matches jm {where}",
            params,
        ).fetchone()
        last_run = conn.execute("SELECT last_checked_at FROM job_search_runs ORDER BY id DESC LIMIT 1").fetchone()
        schedule = conn.execute("SELECT * FROM job_schedule_settings WHERE id = 1").fetchone()
        provider_errors = conn.execute("SELECT COUNT(*) AS count FROM job_providers WHERE status = 'error'").fetchone()["count"]
    return {
        "discovered": discovered,
        "new_jobs": by_state.get("new", 0),
        "updated_jobs": by_state.get("updated", 0),
        "saved": saved_counts.get("saved", 0),
        "dismissed": saved_counts.get("dismissed", 0),
        "high_matches": match_row["high_matches"] or 0,
        "average_match_score": round(match_row["average_score"] or 0),
        "last_provider_check": last_run["last_checked_at"] if last_run else "",
        "next_scheduled_check": schedule["next_check_at"] if schedule else "",
        "provider_errors": provider_errors,
    }


def application_pipeline(client_id: int | None = None) -> dict[str, Any]:
    pipeline = {status: {"count": 0, "items": []} for status in PIPELINE_STATUSES}
    params = (client_id, client_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT sj.id, sj.client_id, sj.discovered_job_id, sj.status, sj.updated_at,
                   dj.company, dj.title
            FROM saved_jobs sj
            JOIN discovered_jobs dj ON dj.id = sj.discovered_job_id
            WHERE (? IS NULL OR sj.client_id = ?)
            ORDER BY sj.updated_at DESC, sj.id DESC
            """,
            params,
        ).fetchall()
        apps = conn.execute(
            """
            SELECT id, client_id, company, position, status, updated_at
            FROM application_tracker
            WHERE (? IS NULL OR client_id = ?)
            ORDER BY updated_at DESC, id DESC
            """,
            params,
        ).fetchall()
    for row in rows:
        status = normalize_pipeline_status(row["status"])
        pipeline[status]["count"] += 1
        if len(pipeline[status]["items"]) < 4:
            pipeline[status]["items"].append(dict(row))
    for row in apps:
        status = normalize_pipeline_status(row["status"])
        pipeline[status]["count"] += 1
        if len(pipeline[status]["items"]) < 4:
            item = dict(row)
            item["title"] = item.get("position", "")
            item["discovered_job_id"] = None
            pipeline[status]["items"].append(item)
    return pipeline


def normalize_pipeline_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    mapping = {
        "interview scheduled": "interview",
        "accepted": "accepted",
        "offer": "offer",
        "applied": "applied",
        "ready to apply": "ready to apply",
    }
    return mapping.get(normalized, normalized if normalized in PIPELINE_STATUSES else "discovered")


def recent_match_cards(client_id: int | None = None, limit: int = 4) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if client_id:
        where = "WHERE jm.client_id = ?"
        params.append(client_id)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT dj.*, jm.score, jm.breakdown, jm.matched_skills, jm.missing_qualifications
            FROM job_matches jm
            JOIN discovered_jobs dj ON dj.id = jm.discovered_job_id
            {where}
            ORDER BY jm.created_at DESC, jm.score DESC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
    cards = []
    for row in rows:
        card = dict(row)
        card["breakdown"] = parse_json(card.get("breakdown"), {})
        card["matched_skills"] = parse_json(card.get("matched_skills"), [])
        card["missing_qualifications"] = parse_json(card.get("missing_qualifications"), [])
        card["score_change_reason"] = "Updated posting details changed the score." if card.get("discovery_state") == "updated" else ""
        cards.append(card)
    return cards


def salary_insights(client_id: int | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT dj.salary_min, dj.salary_max, jsp.minimum_salary
            FROM job_matches jm
            JOIN discovered_jobs dj ON dj.id = jm.discovered_job_id
            LEFT JOIN job_search_profiles jsp ON jsp.client_id = jm.client_id
            WHERE (? IS NULL OR jm.client_id = ?)
            """,
            (client_id, client_id),
        ).fetchall()
    ranges = []
    minimum_preference = 0
    for row in rows:
        minimum_preference = max(minimum_preference, int(row["minimum_salary"] or 0))
        salary_min = safe_int(row["salary_min"])
        salary_max = safe_int(row["salary_max"])
        if salary_min or salary_max:
            low = salary_min or salary_max
            high = salary_max or salary_min
            ranges.append((low, high))
    if not ranges:
        return {
            "available": False,
            "count": 0,
            "message": "No salary data is available in discovered listings yet.",
        }
    lows = [item[0] for item in ranges]
    highs = [item[1] for item in ranges]
    midpoint = round((min(lows) + max(highs)) / 2)
    average = round(sum((low + high) / 2 for low, high in ranges) / len(ranges))
    return {
        "available": True,
        "count": len(ranges),
        "minimum": min(lows),
        "maximum": max(highs),
        "midpoint": midpoint,
        "average": average,
        "highest": max(highs),
        "basis": "annual listing data",
        "minimum_preference": minimum_preference,
        "meets_preference": average >= minimum_preference if minimum_preference else None,
    }


def salary_from_text(value: str) -> dict[str, Any]:
    salary_min, salary_max = parse_salary_range(value)
    return {
        "salary_min": salary_min,
        "salary_max": salary_max,
        "available": bool(salary_min or salary_max),
    }


def career_analytics(client_id: int | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        jobs_by_source = [
            dict(row)
            for row in conn.execute("SELECT source AS label, COUNT(*) AS value FROM discovered_jobs GROUP BY source ORDER BY value DESC").fetchall()
        ]
        matches = [
            dict(row)
            for row in conn.execute(
                "SELECT date(created_at) AS label, AVG(score) AS value FROM job_matches WHERE (? IS NULL OR client_id = ?) GROUP BY date(created_at)",
                (client_id, client_id),
            ).fetchall()
        ]
        app_statuses = [
            dict(row)
            for row in conn.execute(
                "SELECT status AS label, COUNT(*) AS value FROM application_tracker WHERE (? IS NULL OR client_id = ?) GROUP BY status",
                (client_id, client_id),
            ).fetchall()
        ]
    applications_total = sum(int(item["value"]) for item in app_statuses)
    interviews = sum(int(item["value"]) for item in app_statuses if normalize_pipeline_status(item["label"]) == "interview")
    offers = sum(int(item["value"]) for item in app_statuses if normalize_pipeline_status(item["label"]) == "offer")
    return {
        "jobs_by_source": jobs_by_source,
        "average_match_score_over_time": matches,
        "applications_by_status": app_statuses,
        "interview_conversion_rate": round((interviews / applications_total) * 100) if applications_total else 0,
        "offer_conversion_rate": round((offers / applications_total) * 100) if applications_total else 0,
        "has_data": bool(jobs_by_source or matches or app_statuses),
    }


def average_match_score(client_id: int | None = None) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT AVG(score) AS average_score FROM job_matches WHERE (? IS NULL OR client_id = ?)",
            (client_id, client_id),
        ).fetchone()
    return round(row["average_score"] or 0)


def top_improving_resume(client_id: int | None = None) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.full_name, dj.title, dj.company, jm.score
            FROM job_matches jm
            JOIN clients c ON c.id = jm.client_id
            JOIN discovered_jobs dj ON dj.id = jm.discovered_job_id
            WHERE (? IS NULL OR jm.client_id = ?)
            ORDER BY jm.score DESC, jm.created_at DESC
            LIMIT 1
            """,
            (client_id, client_id),
        ).fetchone()
    return dict(row) if row else None


def provider_health_summary() -> dict[str, Any]:
    with get_connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM job_providers ORDER BY provider_key").fetchall()]
    ready = sum(1 for row in rows if row.get("status") == "ready" and row.get("enabled"))
    errors = [row for row in rows if row.get("status") == "error"]
    real_configured = [row for row in rows if row.get("provider_key") != "mock" and row.get("status") == "ready"]
    return {
        "providers": rows,
        "enabled_ready": ready,
        "errors": errors,
        "has_real_provider": bool(real_configured),
    }


def unread_alerts(client_id: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM job_alerts WHERE is_read = 0"
    params: list[Any] = []
    if client_id:
        sql += " AND (client_id = ? OR client_id IS NULL)"
        params.append(client_id)
    sql += " ORDER BY created_at DESC, id DESC LIMIT 10"
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def generate_interview_prep(client: dict[str, Any], job: dict[str, Any] | None, match: dict[str, Any] | None = None) -> dict[str, Any]:
    job = job or {}
    match = match or {}
    title = job.get("title") or client.get("target_role") or "the role"
    company = job.get("company") or "the employer"
    matched = match.get("matched_skills", []) or []
    missing = match.get("missing_qualifications", []) or []
    profile_skills = client.get("skills", []) or []
    skills_to_emphasize = (matched or profile_skills)[:6]
    return {
        "title": title,
        "company": company,
        "questions": [
            f"Walk me through your experience related to {title}.",
            "How do you stay organized and compliant under daily deadlines?",
            "Tell me about a time you solved a work problem safely and professionally.",
            "Which parts of this role match your strongest experience?",
        ],
        "talking_points": [
            f"Use real examples from your saved resume; do not add employers or dates not already listed.",
            f"Connect your experience to {', '.join(skills_to_emphasize[:3]) if skills_to_emphasize else 'the role requirements'}.",
            "Prepare one safety, service, or reliability example from prior work.",
        ],
        "star_prompts": [
            "Situation: What was the work context?",
            "Task: What responsibility did you personally own?",
            "Action: What steps did you take?",
            "Result: What changed, improved, or stayed compliant?",
        ],
        "skills_to_emphasize": skills_to_emphasize,
        "concern_areas": missing[:5],
        "candidate_questions": [
            f"What does success look like in the first 90 days for {title}?",
            "How is performance measured for this position?",
            "What training or onboarding support is provided?",
        ],
        "checklist": [
            "Confirm resume details are accurate.",
            "Review the job description before the interview.",
            "Prepare transportation, timing, and documents.",
            "Bring questions for the employer.",
            "Send a thank-you note after the interview.",
        ],
    }


def get_interview_notes(client_id: int, job_id: int | None) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT notes FROM interview_prep_notes WHERE client_id = ? AND discovered_job_id IS ? ORDER BY id DESC LIMIT 1",
            (client_id, job_id),
        ).fetchone()
    return row["notes"] if row else ""


def save_interview_notes(client_id: int, job_id: int | None, notes: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO interview_prep_notes (client_id, discovered_job_id, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(client_id, discovered_job_id)
            DO UPDATE SET notes = excluded.notes, updated_at = CURRENT_TIMESTAMP
            """,
            (client_id, job_id, notes),
        )
        conn.commit()


def parse_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
