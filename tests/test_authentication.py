from __future__ import annotations

from app.database import get_connection
from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.services.auth_service import (
    assign_legacy_data_to_admin,
    get_user_by_email,
    hash_password,
    legacy_migration_state,
    verify_password,
)
from app.services.fresh_jobs import MockJobProvider, extract_candidate_profile, prepare_application_package, score_job
from app.services.interview_coach_service import build_interview_context, generate_questions, start_session
from tests.conftest import client_payload


def register(client, email: str = "owner@example.com", password: str = "StrongPass123"):
    return client.post(
        "/register",
        data={"username": "Owner", "email": email, "password": password, "password_confirm": password, "remember_me": "1"},
        follow_redirects=False,
    )


def login(client, email: str = "owner@example.com", password: str = "StrongPass123"):
    return client.post(
        "/login",
        data={"email": email, "password": password, "next_url": "/"},
        follow_redirects=False,
    )


def csrf(client) -> str:
    return client.cookies.get("rf_csrf") or ""


def post_authed(client, path: str, data: dict | None = None):
    payload = dict(data or {})
    payload["_csrf"] = csrf(client)
    return client.post(path, data=payload, follow_redirects=False)


def test_first_registration_creates_admin_and_session(qa_app):
    client, _, _, _ = qa_app
    response = register(client)
    assert response.status_code == 303
    assert "rf_session" in response.headers.get("set-cookie", "")
    user = get_user_by_email("owner@example.com")
    assert user is not None
    assert user["is_admin"] == 1
    assert user["password_hash"] != "StrongPass123"


def test_password_hashing_and_verification():
    stored = hash_password("StrongPass123")
    assert stored != "StrongPass123"
    assert verify_password("StrongPass123", stored)
    assert not verify_password("wrong-password", stored)


def test_login_logout_and_protected_route(qa_app):
    client, _, _, _ = qa_app
    register(client)
    post_authed(client, "/logout")

    protected = client.get("/clients/new", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"].startswith("/login")

    logged_in = login(client)
    assert logged_in.status_code == 303
    page = client.get("/clients/new")
    assert page.status_code == 200

    logged_out = post_authed(client, "/logout")
    assert logged_out.status_code == 303
    assert "rf_session" in logged_out.headers.get("set-cookie", "")


def test_session_expiration_redirects_to_login(qa_app):
    client, _, _, _ = qa_app
    register(client)
    with get_connection() as conn:
        conn.execute("UPDATE user_sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
        conn.commit()

    response = client.get("/clients/new", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_user_isolation_for_clients(qa_app):
    client, _, _, _ = qa_app
    register(client, "one@example.com")
    payload = client_payload("User One Resume")
    created = post_authed(client, "/clients", payload)
    assert created.status_code == 303
    first_client_id = int(created.headers["location"].split("/clients/")[1].split("/")[0])
    post_authed(client, "/logout")

    register(client, "two@example.com")
    own_payload = client_payload("User Two Resume")
    own_created = post_authed(client, "/clients", own_payload)
    assert own_created.status_code == 303

    hidden = client.get(f"/clients/{first_client_id}", follow_redirects=False)
    assert hidden.status_code == 404
    dashboard = client.get("/")
    assert "User Two Resume" in dashboard.text
    assert "User One Resume" not in dashboard.text


def test_non_first_registration_is_not_admin(qa_app):
    client, _, _, _ = qa_app
    register(client, "admin@example.com")
    post_authed(client, "/logout")
    register(client, "member@example.com")
    member = get_user_by_email("member@example.com")
    assert member is not None
    assert member["is_admin"] == 0


def test_profile_save_loads_preferences(qa_app):
    client, _, _, _ = qa_app
    register(client)
    saved = post_authed(
        client,
        "/profile",
        {
            "display_name": "QA Owner",
            "email": "owner@example.com",
            "preferred_resume_template": "cdl",
            "default_industry": "Transportation",
            "location": "Dallas, TX",
            "theme_preference": "dark",
            "notification_preferences": "Weekly",
            "api_provider_preferences": "mock",
        },
    )
    assert saved.status_code == 303
    page = client.get("/profile")
    assert "QA Owner" in page.text
    assert "Transportation" in page.text


def test_submitted_user_id_cannot_alter_client_ownership(qa_app):
    client, _, _, _ = qa_app
    register(client, "owner@example.com")
    payload = client_payload("Owned Resume")
    payload["user_id"] = "999"
    created = post_authed(client, "/clients", payload)
    assert created.status_code == 303
    client_id = int(created.headers["location"].split("/clients/")[1].split("/")[0])
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM clients WHERE id = ?", (client_id,)).fetchone()
    assert row["user_id"] == get_user_by_email("owner@example.com")["id"]


def test_user_cannot_delete_or_edit_another_users_data(qa_app):
    client, _, _, _ = qa_app
    register(client, "one@example.com")
    created = post_authed(client, "/clients", client_payload("User One Resume"))
    client_id = int(created.headers["location"].split("/clients/")[1].split("/")[0])
    post_authed(client, "/logout")

    register(client, "two@example.com")
    delete = post_authed(client, f"/clients/{client_id}/delete")
    assert delete.status_code == 404
    note = post_authed(client, f"/clients/{client_id}/notes", {"note": "bad edit"})
    assert note.status_code == 404
    with get_connection() as conn:
        row = conn.execute("SELECT deleted_at FROM clients WHERE id = ?", (client_id,)).fetchone()
        notes = conn.execute("SELECT COUNT(*) AS count FROM client_notes WHERE client_id = ?", (client_id,)).fetchone()
    assert row["deleted_at"] is None
    assert notes["count"] == 0


def test_user_cannot_access_another_users_jobs_packages_or_exports(qa_app):
    client, _, _, _ = qa_app
    repo = FreshJobsRepository()
    register(client, "one@example.com")
    created = post_authed(client, "/clients", client_payload("User One Resume"))
    client_id = int(created.headers["location"].split("/clients/")[1].split("/")[0])
    resume = client.get(f"/clients/{client_id}/preview")
    assert resume.status_code == 200
    candidate = extract_candidate_profile({"id": client_id, **client_payload("User One Resume")})
    job = MockJobProvider().fetch_jobs({}, candidate)[0]
    job_id, _ = repo.insert_job_with_state(job)
    match = score_job(job, candidate, {})
    repo.save_match(client_id, job_id, match)
    package = prepare_application_package({"id": client_id, **client_payload("User One Resume")}, job, match)
    package_id = repo.create_application_package(client_id, job_id, package)
    from app.repositories.application_package_repository import ApplicationPackageRepository

    version_id = ApplicationPackageRepository().create_version(client_id, job_id, {"cover_letter": "Draft", "interview_questions": []})
    post_authed(client, "/logout")

    register(client, "two@example.com")
    assert client.get(f"/fresh-jobs/{job_id}/package?client_id={client_id}", follow_redirects=False).status_code == 404
    assert client.get(f"/application-package/{client_id}/{job_id}", follow_redirects=False).status_code == 404
    assert post_authed(client, f"/application-package/{version_id}/export/recruiter_email_txt").status_code == 404
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM application_packages WHERE id = ?", (package_id,)).fetchone()["count"] == 1


def test_user_cannot_access_another_users_interview_session(qa_app):
    client, _, _, _ = qa_app
    register(client, "one@example.com")
    created = post_authed(client, "/clients", client_payload("User One Resume"))
    client_id = int(created.headers["location"].split("/clients/")[1].split("/")[0])
    context = build_interview_context({"id": client_id, **client_payload("User One Resume")}, None, "General Interview")
    session_id = start_session(client_id, None, "General Interview", generate_questions(context))
    post_authed(client, "/logout")

    register(client, "two@example.com")
    response = post_authed(client, f"/interview-coach/{session_id}/answer", {"question_index": "0", "answer": "I handled work safely."})
    assert response.status_code == 404


def test_legacy_data_migration_claims_existing_rows_once(qa_app):
    client, _, _, _ = qa_app
    legacy = client.post("/clients", data=client_payload("Legacy Resume"), follow_redirects=False)
    assert legacy.status_code == 303
    legacy_id = int(legacy.headers["location"].split("/clients/")[1].split("/")[0])

    response = register(client, "admin@example.com")
    assert response.status_code == 303
    admin_id = get_user_by_email("admin@example.com")["id"]
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM clients WHERE id = ?", (legacy_id,)).fetchone()
    assert row["user_id"] == admin_id
    assert legacy_migration_state()["legacy_assigned_to_user_id"] == admin_id

    assign_legacy_data_to_admin(999)
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM clients WHERE id = ?", (legacy_id,)).fetchone()
    assert row["user_id"] == admin_id
