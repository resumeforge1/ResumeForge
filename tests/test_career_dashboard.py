from __future__ import annotations

import pytest

from app.repositories.application_repository import ApplicationRepository
from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.dashboard_service import (
    application_pipeline,
    career_analytics,
    career_dashboard,
    generate_interview_prep,
    get_interview_notes,
    job_count_summary,
    resume_readiness_score,
    salary_from_text,
    salary_insights,
    save_interview_notes,
)
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, score_job
from tests.conftest import create_client


def test_dashboard_loads_with_empty_database(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/")
    assert response.status_code == 200
    assert "Career Dashboard" in response.text
    assert "No resume yet" in response.text


def test_dashboard_loads_with_sample_data(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Alfredo Career Dashboard")
    response = client.get("/")
    assert response.status_code == 200
    assert "ResumeForge internal readiness score" in response.text
    assert "Applications" in response.text
    assert str(client_id)


def test_resume_readiness_score_and_breakdown_are_transparent():
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    result = resume_readiness_score(candidate)
    assert 0 <= result["score"] <= 100
    assert "contact_information" in result["breakdown"]
    assert "work_history" in result["breakdown"]
    assert result["label"] == "ResumeForge internal readiness score"
    assert result["improvements"]


def test_job_count_and_pipeline_aggregation(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Pipeline QA")
    repo = FreshJobsRepository()
    saved_client = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    saved_client["id"] = client_id
    profile = extract_candidate_profile(saved_client)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    job_id = repo.insert_job(job)
    repo.save_match(client_id, job_id, score_job(job, profile, {"target_role": "CDL Class A Driver"}))
    repo.set_job_status(client_id, job_id, "saved")

    summary = job_count_summary(client_id)
    pipeline = application_pipeline(client_id)
    assert summary["discovered"] >= 1
    assert summary["saved"] == 1
    assert pipeline["saved"]["count"] == 1


def test_invalid_application_status_rejected(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Invalid Status QA")
    response = client.post(
        f"/clients/{client_id}/applications",
        data={"company": "QA", "position": "Driver", "status": "Totally Invalid"},
    )
    assert response.status_code == 400


def test_interview_prep_generation_does_not_invent_candidate_facts():
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    job = {"title": "CDL Route Driver", "company": "Example Carrier", "description": "Route delivery and DOT compliance."}
    prep = generate_interview_prep(candidate, job, {"matched_skills": ["DOT Compliance"], "missing_qualifications": ["Pallet jack"]})
    combined = " ".join(prep["talking_points"] + prep["questions"])
    assert "Example Carrier" not in combined
    assert "Preferred Materials" not in combined
    assert "do not add employers or dates" in combined
    assert "DOT Compliance" in prep["skills_to_emphasize"]


def test_interview_notes_save_and_load(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Interview Notes QA")
    save_interview_notes(client_id, None, "Ask about equipment and schedule.")
    assert get_interview_notes(client_id, None) == "Ask about equipment and schedule."


def test_salary_parsing_and_missing_salary_insights(qa_app):
    assert salary_from_text("$68,000 - $82,000") == {"salary_min": 68000, "salary_max": 82000, "available": True}
    insights = salary_insights()
    assert insights["available"] is False
    assert "No salary data" in insights["message"]


def test_salary_insights_with_listing_data(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Salary QA")
    repo = FreshJobsRepository()
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    candidate["id"] = client_id
    profile = extract_candidate_profile(candidate)
    job = MockJobProvider().fetch_jobs({}, profile)[0]
    job_id = repo.insert_job(job)
    repo.save_match(client_id, job_id, score_job(job, profile, {}))
    insights = salary_insights(client_id)
    assert insights["available"] is True
    assert insights["count"] >= 1
    assert insights["maximum"] >= insights["minimum"]


def test_analytics_and_chart_empty_states(qa_app):
    analytics = career_analytics()
    assert analytics["has_data"] is False
    assert analytics["interview_conversion_rate"] == 0


def test_provider_status_and_unread_alerts_display(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Alerts QA")
    repo = FreshJobsRepository()
    repo.create_alert(client_id, "new_match", "New strong match", provider_key="mock")
    response = client.get("/")
    assert response.status_code == 200
    assert "Unread Alerts" in response.text
    assert "New strong match" in client.get("/fresh-jobs/providers?client_id={client_id}").text or response.text


def test_responsive_pages_return_http_200(qa_app):
    client, _, _, _ = qa_app
    for path in ["/", "/applications", "/interview-prep", "/fresh-jobs/providers"]:
        response = client.get(path, headers={"User-Agent": "Mobile QA"})
        assert response.status_code == 200


def test_career_dashboard_service_handles_empty_database(qa_app):
    dashboard = career_dashboard(None)
    assert dashboard["resume_score"]["score"] == 0
    assert dashboard["salary"]["available"] is False
    assert dashboard["analytics"]["has_data"] is False
