from __future__ import annotations

from datetime import timedelta

from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.fresh_jobs import (
    MockJobProvider,
    current_utc,
    deduplicate_jobs,
    extract_candidate_profile,
    filter_by_freshness,
    prepare_application_package,
    rank_jobs,
    score_job,
)
from tests.conftest import create_client


def test_candidate_profile_extraction_uses_resume_facts():
    client = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    client["id"] = 1
    profile = extract_candidate_profile(client)
    assert profile["years_experience"] >= 10
    assert "CDL Class A Operations" in profile["skills"]
    assert any("Driver" in title for title in profile["job_titles"])
    assert "transportation" in profile["industries"]
    assert "H. Grady Spruce High School" in profile["education"]


def test_freshness_filtering_and_duplicate_detection():
    now = current_utc()
    jobs = [
        {
            "source": "mock",
            "source_job_id": "1",
            "company": "A",
            "title": "CDL Driver",
            "location": "Dallas, TX",
            "posted_at": (now - timedelta(hours=1)).isoformat(),
            "apply_url": "https://jobs.example/a",
        },
        {
            "source": "mock",
            "source_job_id": "1",
            "company": "A",
            "title": "CDL Driver",
            "location": "Dallas, TX",
            "posted_at": (now - timedelta(hours=2)).isoformat(),
            "apply_url": "https://jobs.example/a",
        },
        {
            "source": "mock",
            "source_job_id": "2",
            "company": "B",
            "title": "Warehouse",
            "location": "Dallas, TX",
            "posted_at": (now - timedelta(days=4)).isoformat(),
            "apply_url": "https://jobs.example/b",
        },
    ]
    assert len(filter_by_freshness(jobs, "past_2_hours", now=now)) == 1
    assert len(filter_by_freshness(jobs, "past_7_days", now=now)) == 3
    assert len(deduplicate_jobs(jobs)) == 2


def test_match_scoring_and_ranking_prefers_relevant_fresh_cdl_job():
    client = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    client["id"] = 1
    profile = extract_candidate_profile(client)
    preferences = {"target_role": "CDL Class A Driver", "location": "Dallas, TX", "minimum_salary": 60000}
    jobs = MockJobProvider().fetch_jobs(preferences, profile)
    scored = [{**job, **score_job(job, profile, preferences)} for job in jobs]
    ranked = rank_jobs(scored, "best_match")
    assert ranked[0]["score"] >= 70
    assert "CDL" in ranked[0]["title"] or "Intermodal" in ranked[0]["title"]
    assert ranked[0]["breakdown"]["skill_match"] > 0
    newest = rank_jobs(scored, "newest")
    assert newest[0]["posted_at"] >= newest[-1]["posted_at"]


def test_saving_dismissing_and_status_tracking(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Fresh Jobs QA")
    repo = FreshJobsRepository()
    sample_job = MockJobProvider().fetch_jobs({"target_role": "CDL Driver"}, {"skills": []})[0]
    job_id = repo.insert_job(sample_job)
    repo.set_job_status(client_id, job_id, "saved")
    assert repo.get_saved_status(client_id, job_id) == "saved"
    repo.set_job_status(client_id, job_id, "dismissed")
    assert repo.get_saved_status(client_id, job_id) == "dismissed"


def test_application_package_generation_does_not_invent_candidate_facts():
    client = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    client["id"] = 1
    profile = extract_candidate_profile(client)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    match = score_job(job, profile, {"target_role": "CDL Class A Driver"})
    package = prepare_application_package(client, job, match)
    original_employers = {entry["employer"] for entry in client["work_experience"]}
    tailored_employers = {entry["employer"] for entry in package["tailored_resume"]["work_experience"]}
    assert tailored_employers == original_employers
    assert "Labatt Food Service" not in tailored_employers
    assert package["cover_letter"]
    assert package["ats_keywords"]


def test_fresh_jobs_routes_check_save_prepare_package(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Fresh Jobs Route QA")
    page = client.get(f"/fresh-jobs?client_id={client_id}")
    assert page.status_code == 200
    assert "Fresh Job Finder" in page.text

    check = client.post("/fresh-jobs/check", data={"client_id": client_id, "freshness": "past_7_days"}, follow_redirects=False)
    assert check.status_code == 303
    listing = client.get(f"/fresh-jobs?client_id={client_id}")
    assert "Prepare Application" in listing.text

    repo = FreshJobsRepository()
    jobs = repo.list_matches(client_id)
    job_id = int(jobs[0]["id"])
    saved = client.post(f"/fresh-jobs/{job_id}/status", data={"client_id": client_id, "status": "saved"}, follow_redirects=False)
    assert saved.status_code == 303
    prepared = client.post(f"/fresh-jobs/{job_id}/prepare", data={"client_id": client_id}, follow_redirects=False)
    assert prepared.status_code == 303
    package = client.get(prepared.headers["location"])
    assert package.status_code == 200
    assert "Review Required" in package.text
