from __future__ import annotations

from pathlib import Path

from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, score_job
from app.services.interview_coach_service import (
    build_interview_context,
    coach_dashboard_widgets,
    export_notes_docx,
    export_questions,
    export_summary_pdf,
    generate_questions,
    get_session,
    interview_readiness,
    mark_completed,
    move_session,
    review_answer,
    save_answer,
    start_session,
)
from tests.conftest import create_client


def create_job(client_id: int) -> tuple[dict, dict, int]:
    candidate = dict(SAMPLE_ALFREDO_CRUZ_CDL)
    candidate["id"] = client_id
    profile = extract_candidate_profile(candidate)
    job = MockJobProvider().fetch_jobs({"target_role": "CDL Class A Driver"}, profile)[0]
    repo = FreshJobsRepository()
    job_id = repo.insert_job(job)
    repo.save_match(client_id, job_id, score_job(job, profile, {"target_role": "CDL Class A Driver"}))
    return candidate, job, job_id


def test_question_generation_and_star_guidance():
    context = build_interview_context(dict(SAMPLE_ALFREDO_CRUZ_CDL), {"title": "CDL Driver", "description": "Safety and delivery"}, "CDL Driver")
    questions = generate_questions(context)
    assert 15 <= len(questions) <= 30
    assert any("safety" in question["text"].lower() for question in questions)
    assert {"Situation", "Task", "Action", "Result"} <= set(questions[0]["star"])


def test_answer_review_scores_and_deductions():
    context = build_interview_context(dict(SAMPLE_ALFREDO_CRUZ_CDL), {"title": "CDL Driver"}, "Behavioral Interview")
    review = review_answer("I handled a delivery issue and completed the route safely with 12 stops. Situation Task Action Result.", "Describe a difficult situation.", context)
    assert 0 <= review["overall"] <= 100
    assert "confidence" in review
    assert "suggested_improvements" in review
    short = review_answer("It was fine.", "Describe a difficult situation.", context)
    assert "Too short." in short["deductions"]


def test_session_flow_and_readiness(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Interview Coach QA")
    candidate, job, job_id = create_job(client_id)
    context = build_interview_context(candidate, job, "CDL Driver")
    session_id = start_session(client_id, job_id, "CDL Driver", generate_questions(context))
    session = get_session(session_id)
    assert session["current_index"] == 0
    review = review_answer("Situation Task Action Result. I completed a safe route with 10 deliveries.", session["questions"][0]["text"], context)
    save_answer(session_id, 0, "Situation Task Action Result. I completed a safe route with 10 deliveries.", review)
    move_session(session_id, "next")
    session = get_session(session_id)
    assert session["current_index"] == 1
    mark_completed(session_id)
    session = get_session(session_id)
    assert session["completed"] == 1
    readiness = interview_readiness(candidate, session)
    assert 0 <= readiness["score"] <= 100
    assert "30% resume readiness" in readiness["explanation"]


def test_interview_exports(qa_app):
    client, _, output_dir, _ = qa_app
    client_id = create_client(client, "Interview Export QA")
    candidate, job, job_id = create_job(client_id)
    context = build_interview_context(candidate, job, "General Interview")
    session_id = start_session(client_id, job_id, "General Interview", generate_questions(context))
    session = get_session(session_id)
    for filename in [export_questions(session), export_notes_docx(session), export_summary_pdf(session)]:
        path = Path(output_dir) / filename
        assert path.exists()
        assert path.stat().st_size > 0


def test_interview_coach_routes_and_dashboard_widget(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Interview Route QA")
    page = client.get(f"/interview-coach?client_id={client_id}")
    assert page.status_code == 200
    assert "AI Interview Coach" in page.text
    started = client.post("/interview-coach/start", data={"client_id": client_id, "mode": "Behavioral Interview"}, follow_redirects=False)
    assert started.status_code == 303
    session_id = int(started.headers["location"].split("session_id=")[1].split("&")[0])
    answered = client.post(
        f"/interview-coach/{session_id}/answer",
        data={"question_index": 0, "answer": "Situation Task Action Result. I completed the work safely with 8 stops."},
        follow_redirects=False,
    )
    assert answered.status_code == 303
    widgets = coach_dashboard_widgets(client_id)
    assert widgets["practice_streak"] >= 1
    dashboard = client.get("/")
    assert "AI Interview Coach" in dashboard.text
