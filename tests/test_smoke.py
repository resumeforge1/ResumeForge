from app.services.rewrite_engine import improve_summary
from tests.conftest import create_client


def test_main_pages_return_http_200(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client)
    for path in [
        "/",
        "/dashboard",
        "/copilot",
        "/health",
        "/clients/new",
        f"/clients/{client_id}/preview",
        f"/clients/{client_id}",
        "/fresh-jobs",
        "/applications",
        "/interview-prep",
        "/interview-coach",
        "/marketplace",
        "/settings",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_health_check_reports_release_status(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.16.0-dev"
    assert data["database"]["ok"] is True
    assert data["templates"]["count"] >= 8


def test_sample_alfredo_client_can_be_created_and_previewed(qa_app):
    client, _, _, _ = qa_app
    response = client.post("/clients/sample", follow_redirects=False)
    assert response.status_code == 303
    preview = client.get(response.headers["location"])
    assert preview.status_code == 200
    assert "Alfredo Cruz" in preview.text


def test_mock_ai_provider_runs_without_api_keys():
    improved = improve_summary({"professional_summary": "Reliable CDL driver."})
    assert "Reliable CDL driver" in improved
    assert "reliable execution" in improved
