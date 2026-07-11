import json


DEFAULT_TEMPLATE_LABELS = [
    "CDL Driver",
    "General Professional",
    "Healthcare",
    "Software",
    "Finance",
    "Warehouse",
    "Sales",
    "Executive",
]


def test_template_marketplace_loads_all_default_templates(qa_app):
    client, _, _, _ = qa_app
    response = client.get("/marketplace")
    assert response.status_code == 200
    for label in DEFAULT_TEMPLATE_LABELS:
        assert label in response.text


def test_invalid_plugin_manifests_do_not_crash_app(qa_app):
    client, _, _, plugin_dir = qa_app
    valid = plugin_dir / "valid"
    invalid = plugin_dir / "invalid"
    valid.mkdir()
    invalid.mkdir()
    (valid / "plugin.json").write_text(
        json.dumps({"name": "Valid QA Plugin", "description": "Works"}),
        encoding="utf-8",
    )
    (invalid / "plugin.json").write_text("{bad json", encoding="utf-8")

    response = client.get("/marketplace")
    assert response.status_code == 200
    assert "Valid QA Plugin" in response.text
