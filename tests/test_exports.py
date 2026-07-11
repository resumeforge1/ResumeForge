import io
import zipfile

import pytest

from tests.conftest import create_client


@pytest.mark.parametrize(
    "export_type, extension",
    [
        ("ats_docx", ".docx"),
        ("premium_docx", ".docx"),
        ("premium_pdf", ".pdf"),
        ("cover_letter_docx", ".docx"),
        ("zip_package", ".zip"),
    ],
)
def test_export_generator_handles_valid_export_types(qa_app, export_type: str, extension: str):
    client, _, _, _ = qa_app
    client_id = create_client(client, f"Export {export_type}")
    response = client.get(f"/clients/{client_id}/export/{export_type}")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith(f'{extension}"')
    if export_type == "zip_package":
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            assert any(name.endswith("ats-resume.docx") for name in package.namelist())


def test_export_generator_handles_invalid_export_type(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client)
    response = client.get(f"/clients/{client_id}/export/not_real")
    assert response.status_code == 404
    assert "Export failed" in response.text
