from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.database import get_connection
from app.services.dashboard_service import resume_readiness_score, salary_insights
from app.services.fresh_jobs import parse_datetime


FINAL_APPLICATION_STATES = {"rejected", "accepted", "offer", "dismissed"}


def build_copilot(client: dict[str, Any] | None = None) -> dict[str, Any]:
    client_id = int(client["id"]) if client and client.get("id") else None
    summary = todays_summary(client_id)
    opportunities = opportunity_feed(client_id)
    resume = resume_coach(client or {})
    applications = application_coach(client_id)
    followups = follow_up_tracker(client_id)
    momentum = career_momentum_score(client or {}, summary, applications)
    return {
        "client": client,
        "summary": summary,
        "opportunities": opportunities,
        "recommended_actions": recommended_actions(summary, opportunities, resume, applications, followups),
        "resume_coach": resume,
        "application_coach": applications,
        "followups": followups,
        "salary_alerts": salary_opportunity_alerts(client_id),
        "widgets": copilot_widgets(client_id, opportunities, followups, resume, momentum),
        "momentum": momentum,
        "timeline": activity_timeline(client_id),
    }


def todays_summary(client_id: int | None = None) -> dict[str, Any]:
    today = datetime.now(UTC).date().isoformat()
    params = (client_id, client_id)
    with get_connection() as conn:
        jobs_found_today = conn.execute(
            "SELECT COUNT(*) AS count FROM discovered_jobs WHERE date(discovered_at) = ?",
            (today,),
        ).fetchone()["count"]
        high_match_jobs = conn.execute(
            "SELECT COUNT(*) AS count FROM job_matches WHERE score >= 75 AND (? IS NULL OR client_id = ?)",
            params,
        ).fetchone()["count"]
        saved_jobs = conn.execute(
            "SELECT COUNT(*) AS count FROM saved_jobs WHERE status = 'saved' AND (? IS NULL OR client_id = ?)",
            params,
        ).fetchone()["count"]
        applications_waiting = conn.execute(
            """
            SELECT COUNT(*) AS count FROM application_tracker
            WHERE lower(status) IN ('applied', 'ready to apply') AND (? IS NULL OR client_id = ?)
            """,
            params,
        ).fetchone()["count"]
        interviews = conn.execute(
            """
            SELECT COUNT(*) AS count FROM application_tracker
            WHERE lower(status) IN ('interview', 'interview scheduled') AND (? IS NULL OR client_id = ?)
            """,
            params,
        ).fetchone()["count"]
    return {
        "jobs_found_today": jobs_found_today,
        "high_match_jobs": high_match_jobs,
        "saved_jobs": saved_jobs,
        "applications_waiting": applications_waiting,
        "interviews_scheduled": interviews,
    }


def opportunity_feed(client_id: int | None = None, limit: int = 12) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT dj.*, jm.score, jm.matched_skills, jm.missing_qualifications, sj.status AS saved_status
            FROM job_matches jm
            JOIN discovered_jobs dj ON dj.id = jm.discovered_job_id
            LEFT JOIN saved_jobs sj ON sj.discovered_job_id = dj.id AND sj.client_id = jm.client_id
            WHERE (? IS NULL OR jm.client_id = ?)
            ORDER BY jm.score DESC, COALESCE(dj.salary_max, dj.salary_min, 0) DESC, dj.posted_at DESC
            LIMIT ?
            """,
            (client_id, client_id, limit),
        ).fetchall()
    opportunities = []
    for row in rows:
        item = dict(row)
        rank_score = opportunity_rank_score(item)
        item["opportunity_score"] = rank_score
        item["opportunity_level"] = opportunity_level(rank_score)
        item["ranking_explanation"] = [
            f"Match score: {item.get('score') or 0}",
            f"Salary signal: {item.get('salary_max') or item.get('salary_min') or 'unavailable'}",
            f"Freshness: {freshness_label(item.get('posted_at', ''))}",
            "Distance: unavailable unless location data is configured.",
            f"Manual priority: {item.get('saved_status') or 'not set'}",
        ]
        opportunities.append(item)
    return sorted(opportunities, key=lambda item: item["opportunity_score"], reverse=True)


def opportunity_rank_score(job: dict[str, Any]) -> int:
    score = int(job.get("score") or 0)
    salary = job.get("salary_max") or job.get("salary_min") or 0
    salary_points = min(15, int(salary / 10000)) if salary else 0
    freshness_points = freshness_points_for(job.get("posted_at", ""))
    manual_priority = 8 if job.get("saved_status") in {"saved", "preparing", "ready to apply"} else 0
    return min(100, score + salary_points + freshness_points + manual_priority)


def opportunity_level(score: int) -> str:
    if score >= 85:
        return "High Opportunity"
    if score >= 65:
        return "Medium Opportunity"
    return "Low Opportunity"


def resume_coach(client: dict[str, Any]) -> dict[str, Any]:
    readiness = resume_readiness_score(client)
    suggestions = list(readiness.get("improvements", []))
    work = client.get("work_experience", []) or []
    skills = client.get("skills", []) or []
    certifications = client.get("certifications", []) or []
    if work and not any(any(char.isdigit() for char in bullet) for entry in work for bullet in entry.get("bullets", [])):
        suggestions.append("Add measurable achievements where real numbers are available.")
    if len(skills) < 8:
        suggestions.append("Expand skills with individual competencies already supported by experience.")
    if not certifications:
        suggestions.append("Add certifications or licenses only if already earned.")
    return {
        "readiness": readiness,
        "suggestions": dedupe(suggestions),
        "recent_improvements": readiness.get("improvements", [])[:4],
    }


def application_coach(client_id: int | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        applications = [
            dict(row)
            for row in conn.execute(
                """
                SELECT * FROM application_tracker
                WHERE (? IS NULL OR client_id = ?)
                ORDER BY updated_at DESC, id DESC
                """,
                (client_id, client_id),
            ).fetchall()
        ]
        saved_jobs = [
            dict(row)
            for row in conn.execute(
                """
                SELECT sj.*, dj.company, dj.title, dj.posted_at
                FROM saved_jobs sj
                JOIN discovered_jobs dj ON dj.id = sj.discovered_job_id
                WHERE (? IS NULL OR sj.client_id = ?)
                ORDER BY sj.updated_at DESC, sj.id DESC
                """,
                (client_id, client_id),
            ).fetchall()
        ]
    return {
        "applications_needing_followup": [app for app in applications if needs_followup(app)],
        "applications_ready_to_submit": [job for job in saved_jobs if job.get("status") == "ready to apply"],
        "old_saved_jobs": [job for job in saved_jobs if job.get("status") == "saved" and older_than(job.get("updated_at"), 7)],
        "dismissed_jobs": [job for job in saved_jobs if job.get("status") == "dismissed"],
    }


def follow_up_tracker(client_id: int | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, company, position, status, date_applied, updated_at
                FROM application_tracker
                WHERE (? IS NULL OR client_id = ?)
                ORDER BY updated_at DESC, id DESC
                """,
                (client_id, client_id),
            ).fetchall()
        ]
    followups = []
    for row in rows:
        applied = parse_flexible_date(row.get("date_applied") or row.get("updated_at"))
        due = applied + timedelta(days=7) if applied else None
        followups.append(
            {
                "company": row.get("company") or "Company unavailable",
                "position": row.get("position") or "Position unavailable",
                "status": row.get("status") or "Applied",
                "applied_date": row.get("date_applied") or row.get("updated_at"),
                "follow_up_due": due.date().isoformat() if due else "Unavailable",
                "interview_date": row.get("date_applied") if str(row.get("status", "")).lower() in {"interview", "interview scheduled"} else "",
                "offer_deadline": "",
            }
        )
    return followups


def salary_opportunity_alerts(client_id: int | None = None) -> list[str]:
    salary = salary_insights(client_id)
    if not salary.get("available"):
        return ["No salary alerts yet because matching listings do not include salary data."]
    alerts = [f"Highest listed salary in current matches: ${salary['highest']:,}."]
    if salary.get("minimum_preference") and salary.get("meets_preference") is False:
        alerts.append("Average listed salary is below the saved minimum preference.")
    elif salary.get("minimum_preference"):
        alerts.append("Average listed salary meets or exceeds the saved minimum preference.")
    return alerts


def copilot_widgets(
    client_id: int | None,
    opportunities: list[dict[str, Any]],
    followups: list[dict[str, Any]],
    resume: dict[str, Any],
    momentum: dict[str, Any],
) -> dict[str, Any]:
    with get_connection() as conn:
        interviews = [
            dict(row)
            for row in conn.execute(
                """
                SELECT company, position, status, date_applied
                FROM application_tracker
                WHERE lower(status) IN ('interview', 'interview scheduled') AND (? IS NULL OR client_id = ?)
                ORDER BY date_applied DESC, id DESC
                LIMIT 5
                """,
                (client_id, client_id),
            ).fetchall()
        ]
    return {
        "upcoming_interviews": interviews,
        "recent_followups": followups[:5],
        "high_match_jobs": [job for job in opportunities if int(job.get("score") or 0) >= 75][:5],
        "recent_resume_improvements": resume.get("recent_improvements", [])[:5],
        "career_momentum_score": momentum,
        "application_velocity": momentum.get("applications_this_month", 0),
    }


def career_momentum_score(client: dict[str, Any], summary: dict[str, Any], applications: dict[str, Any]) -> dict[str, Any]:
    readiness = resume_readiness_score(client).get("score", 0) if client else 0
    apps_this_month = applications_this_month((client or {}).get("id"))
    interview_rate = rate_for_status((client or {}).get("id"), {"interview", "interview scheduled"})
    offer_rate = rate_for_status((client or {}).get("id"), {"offer", "accepted"})
    components = {
        "resume_readiness": readiness,
        "applications_this_month": min(100, apps_this_month * 20),
        "high_match_jobs": min(100, int(summary.get("high_match_jobs") or 0) * 20),
        "interview_rate": interview_rate,
        "offer_rate": offer_rate,
    }
    score = round(
        components["resume_readiness"] * 0.35
        + components["applications_this_month"] * 0.20
        + components["high_match_jobs"] * 0.20
        + components["interview_rate"] * 0.15
        + components["offer_rate"] * 0.10
    )
    return {
        "score": max(0, min(100, score)),
        "components": components,
        "applications_this_month": apps_this_month,
        "explanation": [
            "35% resume readiness",
            "20% applications this month",
            "20% high-match jobs",
            "15% interview rate",
            "10% offer rate",
        ],
    }


def activity_timeline(client_id: int | None = None) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    with get_connection() as conn:
        events.extend(
            {"kind": "Resume updated", "label": row["reason"] or "Resume version saved", "created_at": row["created_at"]}
            for row in conn.execute(
                "SELECT reason, created_at FROM client_versions WHERE (? IS NULL OR client_id = ?) ORDER BY created_at DESC LIMIT 8",
                (client_id, client_id),
            ).fetchall()
        )
        events.extend(
            {"kind": "Jobs discovered", "label": f"{row['title']} at {row['company']}", "created_at": row["discovered_at"]}
            for row in conn.execute(
                "SELECT title, company, discovered_at FROM discovered_jobs ORDER BY discovered_at DESC LIMIT 8"
            ).fetchall()
        )
        events.extend(
            {"kind": "Application prepared", "label": f"{row['title']} at {row['company']}", "created_at": row["created_at"]}
            for row in conn.execute(
                """
                SELECT dj.title, dj.company, apv.created_at
                FROM application_package_versions apv
                JOIN discovered_jobs dj ON dj.id = apv.discovered_job_id
                WHERE (? IS NULL OR apv.client_id = ?)
                ORDER BY apv.created_at DESC LIMIT 8
                """,
                (client_id, client_id),
            ).fetchall()
        )
        events.extend(
            {"kind": "Interview notes saved", "label": "Interview preparation notes updated", "created_at": row["updated_at"]}
            for row in conn.execute(
                "SELECT updated_at FROM interview_prep_notes WHERE (? IS NULL OR client_id = ?) ORDER BY updated_at DESC LIMIT 8",
                (client_id, client_id),
            ).fetchall()
        )
        events.extend(
            {"kind": "Provider check completed", "label": f"{row['provider_key']} - {row['status']}", "created_at": row["finished_at"] or row["started_at"]}
            for row in conn.execute(
                "SELECT provider_key, status, started_at, finished_at FROM provider_run_logs ORDER BY started_at DESC LIMIT 8"
            ).fetchall()
        )
    return sorted(events, key=lambda item: item.get("created_at") or "", reverse=True)[:12]


def recommended_actions(
    summary: dict[str, Any],
    opportunities: list[dict[str, Any]],
    resume: dict[str, Any],
    applications: dict[str, Any],
    followups: list[dict[str, Any]],
) -> list[str]:
    actions = []
    if opportunities:
        top = opportunities[0]
        actions.append(f"Prepare application for {top.get('company')} - {top.get('title')}")
    if resume.get("suggestions"):
        actions.append(resume["suggestions"][0])
    if followups:
        actions.append(f"Follow up with {followups[0]['company']}")
    if summary.get("jobs_found_today"):
        actions.append(f"Check {summary['jobs_found_today']} new postings")
    if applications.get("applications_ready_to_submit"):
        actions.append("Review applications marked ready to apply before sending.")
    return actions or ["Create or import a resume to activate AI Job Copilot."]


def needs_followup(application: dict[str, Any]) -> bool:
    status = str(application.get("status", "")).lower()
    if status in FINAL_APPLICATION_STATES:
        return False
    return older_than(application.get("date_applied") or application.get("updated_at"), 7)


def older_than(value: Any, days: int) -> bool:
    parsed = parse_flexible_date(value)
    return bool(parsed and datetime.now(UTC) - parsed >= timedelta(days=days))


def freshness_points_for(value: str) -> int:
    parsed = parse_datetime(value)
    if parsed is None:
        return 0
    hours = max(0, (datetime.now(UTC) - parsed).total_seconds() / 3600)
    if hours <= 24:
        return 10
    if hours <= 72:
        return 6
    if hours <= 168:
        return 3
    return 0


def freshness_label(value: str) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return "unavailable"
    days = (datetime.now(UTC) - parsed).days
    if days <= 0:
        return "posted today"
    return f"{days} days old"


def applications_this_month(client_id: int | None = None) -> int:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM application_tracker
            WHERE date(COALESCE(date_applied, created_at)) >= ? AND (? IS NULL OR client_id = ?)
            """,
            (start, client_id, client_id),
        ).fetchone()
    return int(row["count"] or 0)


def rate_for_status(client_id: int | None, statuses: set[str]) -> int:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status FROM application_tracker WHERE (? IS NULL OR client_id = ?)",
            (client_id, client_id),
        ).fetchall()
    total = len(rows)
    if not total:
        return 0
    matched = sum(1 for row in rows if str(row["status"]).lower() in statuses)
    return round((matched / total) * 100)


def parse_flexible_date(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
    except ValueError:
        return None


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            output.append(item)
            seen.add(key)
    return output
