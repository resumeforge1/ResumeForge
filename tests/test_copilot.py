from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database import get_connection
from app.repositories.application_package_repository import ApplicationPackageRepository
from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.application_package_service import build_application_package
from app.services.copilot_service import build_copilot, career_momentum_score, opportunity_feed
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, score_job
from tests.conftest import create_client


def create_copilot_job(client_id: int) -> tuple[dict, dict, int, dict]:
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    candidate["id"] = client_id
    profile = extract_candidate_profile(candidate)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    repo = FreshJobsRepository()
    job_id = repo.insert_job(job)
    match = score_job(job, profile, {"target_role": "CDL Class A Driver", "location": "Dallas, TX"})
    repo.save_match(client_id, job_id, match)
    repo.set_job_status(client_id, job_id, "saved")
    return candidate, job, job_id, match


def test_copilot_page_loads_empty_database(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/copilot")
    assert response.status_code == 200
    assert "AI Job Copilot" in response.text
    assert "No opportunities yet" in response.text


def test_copilot_page_and_dashboard_section_with_data(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Copilot QA")
    create_copilot_job(client_id)
    page = client.get(f"/copilot?client_id={client_id}")
    assert page.status_code == 200
    for text in ["Today’s Summary", "Opportunity Feed", "Resume Coach", "Application Coach", "Career Momentum"]:
        assert text in page.text
    dashboard = client.get("/")
    assert "AI Job Copilot" in dashboard.text
    assert "Open Copilot" in dashboard.text


def test_opportunity_feed_ranks_and_labels_opportunities(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Opportunity QA")
    create_copilot_job(client_id)
    opportunities = opportunity_feed(client_id)
    assert opportunities
    assert opportunities[0]["opportunity_level"] in {"High Opportunity", "Medium Opportunity", "Low Opportunity"}
    assert "Match score" in opportunities[0]["ranking_explanation"][0]


def test_resume_coach_does_not_invent_facts(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Resume Coach QA")
    candidate, _, _, _ = create_copilot_job(client_id)
    copilot = build_copilot(candidate)
    suggestions = " ".join(copilot["resume_coach"]["suggestions"])
    assert "only if already earned" in suggestions or "where real numbers are available" in suggestions
    assert "invent" not in suggestions.lower()


def test_application_coach_followups_and_momentum(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Followup QA")
    old_date = (datetime.now(UTC) - timedelta(days=10)).date().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO application_tracker (client_id, company, position, status, date_applied, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, "ABC Trucking", "Driver", "Applied", old_date, ""),
        )
        conn.commit()
    candidate, _, _, _ = create_copilot_job(client_id)
    copilot = build_copilot(candidate)
    assert copilot["application_coach"]["applications_needing_followup"]
    assert copilot["followups"][0]["follow_up_due"] != "Unavailable"
    assert 0 <= copilot["momentum"]["score"] <= 100
    assert "35% resume readiness" in copilot["momentum"]["explanation"]


def test_copilot_activity_timeline_includes_local_events(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Timeline QA")
    candidate, job, job_id, match = create_copilot_job(client_id)
    package_id = ApplicationPackageRepository().create_version(client_id, job_id, build_application_package(candidate, job, match))
    assert package_id
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO provider_run_logs (client_id, provider_key, status, jobs_found, finished_at) VALUES (?, ?, ?, ?, ?)",
            (client_id, "mock", "ok", 1, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    copilot = build_copilot(candidate)
    kinds = {event["kind"] for event in copilot["timeline"]}
    assert "Application prepared" in kinds
    assert "Provider check completed" in kinds


def test_salary_alerts_are_listing_based(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Salary Alert QA")
    candidate, _, _, _ = create_copilot_job(client_id)
    copilot = build_copilot(candidate)
    assert copilot["salary_alerts"]
    assert "salary" in " ".join(copilot["salary_alerts"]).lower()


def test_copilot_route_has_no_auto_apply_language(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/copilot")
    assert response.status_code == 200
    assert "No applications are submitted automatically" in response.text
