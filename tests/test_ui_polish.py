from __future__ import annotations

from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, score_job
from tests.conftest import create_client


def test_base_navigation_and_notification_render(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/?message=Saved")
    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "Resume Builder" in response.text
    assert "Interview Prep" in response.text
    assert "notice success" in response.text
    assert "#icon-dashboard" in response.text


def test_dashboard_ui_components_render(qa_app):
    client, _, _, _ = qa_app
    create_client(client, "UI Dashboard QA")
    response = client.get("/")
    assert response.status_code == 200
    for text in ["Jobs Found Today", "Prepared Applications", "Applications Ready", "Average Match Score", "Provider Status", "Recent Activity"]:
        assert text in response.text
    assert "metric-card" in response.text
    assert "pipeline-grid" in response.text


def test_empty_states_render_without_data(qa_app):
    client, _, _, _ = qa_app
    dashboard = client.get("/")
    fresh_jobs = client.get("/fresh-jobs")
    assert "empty-state" in dashboard.text
    assert "No client selected" in fresh_jobs.text
    assert "empty-icon" in fresh_jobs.text


def test_settings_grouped_cards_render(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/settings")
    assert response.status_code == 200
    for section in ["Appearance", "AI Provider", "Job Providers", "Export Settings", "Future Features"]:
        assert section in response.text


def test_fresh_jobs_card_polish_render(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Fresh Jobs UI QA")
    checked = client.post("/fresh-jobs/check", data={"client_id": client_id, "freshness": "past_7_days"}, follow_redirects=False)
    assert checked.status_code == 303
    listing = client.get(f"/fresh-jobs?client_id={client_id}")
    assert "fresh-job-meta" in listing.text
    assert "Prepare Application Package" in listing.text
    assert "View Details" in listing.text
    assert "score-badge" in listing.text


def test_application_package_workspace_ui_render(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Package UI QA")
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    candidate["id"] = client_id
    profile = extract_candidate_profile(candidate)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    repo = FreshJobsRepository()
    job_id = repo.insert_job(job)
    repo.save_match(client_id, job_id, score_job(job, profile, {"target_role": "CDL Class A Driver"}))
    response = client.get(f"/application-package/{client_id}/{job_id}")
    assert response.status_code == 200
    assert "package-workspace" in response.text
    assert "export-sidebar" in response.text
    for section in ["Job Summary", "Match Analysis", "Resume Draft", "Cover Letter", "ATS Keywords", "Interview Prep", "Recruiter Email"]:
        assert section in response.text


def test_responsive_routes_still_return_200(qa_app):
    client, _, _, _ = qa_app
    for path in ["/", "/fresh-jobs", "/applications", "/interview-prep", "/settings"]:
        response = client.get(path, headers={"User-Agent": "Mobile Safari"})
        assert response.status_code == 200
