from __future__ import annotations

from pathlib import Path

from app.repositories.application_package_repository import ApplicationPackageRepository
from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.application_package_service import build_application_package, export_application_package
from app.services.dashboard_service import career_dashboard
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, score_job
from tests.conftest import create_client


def create_scored_job(client_id: int) -> tuple[dict, dict, int, dict]:
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    candidate["id"] = client_id
    profile = extract_candidate_profile(candidate)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    repo = FreshJobsRepository()
    job_id = repo.insert_job(job)
    match = score_job(job, profile, {"target_role": "CDL Class A Driver", "location": "Dallas, TX"})
    repo.save_match(client_id, job_id, match)
    return candidate, job, job_id, match


def test_application_package_creation_with_mock_provider(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Package QA")
    candidate, job, _, match = create_scored_job(client_id)
    package = build_application_package(candidate, job, match)
    assert package["review_required"] is True
    assert package["cover_letter"]
    assert package["recruiter_email"]
    assert package["linkedin_message"]
    assert package["match_analysis"]["match_score"] >= 0


def test_missing_keyword_detection_and_strong_matches(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Keyword QA")
    candidate, job, _, match = create_scored_job(client_id)
    job["description"] += " Requires pallet jack certification and liftgate routing."
    package = build_application_package(candidate, job, match)
    analysis = package["match_analysis"]
    assert "strong_matching_skills" in analysis
    assert isinstance(analysis["missing_keywords"], list)
    assert analysis["score_explanation"]


def test_package_persistence_and_notes(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Persistence QA")
    candidate, job, job_id, match = create_scored_job(client_id)
    repo = ApplicationPackageRepository()
    package_id = repo.create_version(client_id, job_id, build_application_package(candidate, job, match))
    saved = repo.get_version(package_id)
    assert saved is not None
    assert saved["package"]["job_summary"]["title"] == job["title"]
    repo.add_note(package_id, "Reviewed cover letter.")
    assert repo.notes(package_id)[0]["note"] == "Reviewed cover letter."


def test_package_exports_are_generated_and_logged(qa_app):
    client, _, output_dir, _ = qa_app
    client_id = create_client(client, "Export Package QA")
    candidate, job, job_id, match = create_scored_job(client_id)
    repo = ApplicationPackageRepository()
    package_id = repo.create_version(client_id, job_id, build_application_package(candidate, job, match))
    package_version = repo.get_version(package_id)
    filenames = [
        export_application_package(package_version, "resume_docx"),
        export_application_package(package_version, "cover_letter_docx"),
        export_application_package(package_version, "recruiter_email_txt"),
        export_application_package(package_version, "linkedin_message_txt"),
        export_application_package(package_version, "interview_questions_docx"),
        export_application_package(package_version, "zip_package"),
    ]
    for filename in filenames:
        path = Path(output_dir) / filename
        assert path.exists()
        assert path.stat().st_size > 0
        repo.record_export(package_id, filename.split(".")[-1], filename)
    assert repo.export_stats()["total"] >= 6


def test_application_package_page_and_save_route(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Package Route QA")
    _, _, job_id, _ = create_scored_job(client_id)
    page = client.get(f"/application-package/{client_id}/{job_id}")
    assert page.status_code == 200
    assert "Application Package" in page.text
    repo = ApplicationPackageRepository()
    package_version = repo.latest_for_job(client_id, job_id)
    response = client.post(
        f"/application-package/{package_version['id']}/save",
        data={
            "status": "ready to send",
            "cover_letter": package_version["package"]["cover_letter"],
            "recruiter_email": package_version["package"]["recruiter_email"],
            "linkedin_message": package_version["package"]["linkedin_message"],
            "interview_summary": package_version["package"]["interview_summary"],
            "tailored_resume_text": package_version["package"]["tailored_resume_text"],
            "ats_keywords": "\n".join(package_version["package"]["ats_keywords"]),
            "resume_improvements": "\n".join(package_version["package"]["resume_improvements"]),
            "missing_skills_analysis": "\n".join(package_version["package"]["missing_skills_analysis"]),
            "interview_questions": "\n".join(package_version["package"]["interview_questions"]),
            "note": "Ready after review.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert repo.get_version(package_version["id"])["status"] == "ready to send"


def test_no_candidate_fact_invention_in_tailored_resume(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "No Invention QA")
    candidate, job, _, match = create_scored_job(client_id)
    package = build_application_package(candidate, job, match)
    original_jobs = [(entry["employer"], entry["job_title"], entry["start_date"], entry["end_date"]) for entry in candidate["work_experience"]]
    tailored_jobs = [
        (entry["employer"], entry["job_title"], entry["start_date"], entry["end_date"])
        for entry in package["tailored_resume"]["work_experience"]
    ]
    assert tailored_jobs == original_jobs
    assert job["company"] not in {entry["employer"] for entry in package["tailored_resume"]["work_experience"]}


def test_dashboard_package_statistics(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Dashboard Package QA")
    candidate, job, job_id, match = create_scored_job(client_id)
    repo = ApplicationPackageRepository()
    repo.create_version(client_id, job_id, build_application_package(candidate, job, match), "ready to send")
    dashboard = career_dashboard(candidate)
    assert dashboard["packages"]["prepared_applications"] >= 1
    assert dashboard["packages"]["applications_ready_to_send"] >= 1
    assert dashboard["packages"]["average_match_score"] >= 0
