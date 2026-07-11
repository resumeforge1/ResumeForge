from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

import app.database as database
import app.document_generator as document_generator
import app.main as main
import app.services.plugin_service as plugin_service
import app.template_registry as template_registry


@pytest.fixture()
def qa_app(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "resumeforge.sqlite3"
    output_dir = tmp_path / "outputs"
    upload_dir = tmp_path / "data" / "uploads"
    plugin_dir = tmp_path / "plugins"
    db_path.parent.mkdir(parents=True)
    output_dir.mkdir()
    upload_dir.mkdir(parents=True)
    plugin_dir.mkdir()

    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "DATA_DIR", db_path.parent)
    monkeypatch.setattr(document_generator, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(main, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    monkeypatch.setattr(plugin_service, "PLUGIN_DIR", plugin_dir)
    monkeypatch.setattr(template_registry, "INDUSTRY_TEMPLATE_DIR", Path.cwd() / "templates")

    main.app.router.on_startup.clear()
    database.init_db()
    with TestClient(main.app) as client:
        yield client, tmp_path, output_dir, plugin_dir


def client_payload(name: str = "QA Test Client") -> dict[str, str]:
    return {
        "template_key": "general",
        "full_name": name,
        "city_state": "Dallas, TX",
        "phone": "(214) 555-1111",
        "email": "qa@example.com",
        "target_role": "Operations Coordinator",
        "professional_summary": "Operations professional with service and documentation experience.",
        "certifications": "OSHA 10",
        "skills": "Documentation\nCustomer Service\nScheduling",
        "employer": "QA Company",
        "job_title": "Coordinator",
        "start_date": "2021",
        "end_date": "Present",
        "bullets": "Managed customer documentation.\nCoordinated daily schedules.",
        "education": "H. Grady Spruce High School",
        "status": "Draft",
    }


def create_client(client: TestClient, name: str = "QA Test Client") -> int:
    response = client.post("/clients", data=client_payload(name), follow_redirects=False)
    assert response.status_code == 303
    return int(response.headers["location"].split("/clients/")[1].split("/")[0])


def make_docx_bytes() -> bytes:
    doc = Document()
    for line in [
        "Docx Import Person",
        "docx@example.com",
        "(214) 555-2222",
        "Skills",
        "DOT Compliance, LTL Delivery",
        "Licenses",
        "Texas CDL Class A License",
    ]:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
