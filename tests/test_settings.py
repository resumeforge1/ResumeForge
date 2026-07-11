def test_settings_save_load_correctly(qa_app):
    client, _, _, _ = qa_app
    response = client.post(
        "/settings",
        data={
            "accent_color": "#123456",
            "font_family": "Georgia",
            "header_style": "boxed",
            "resume_spacing": "roomy",
            "margins": "wide",
            "section_order": "summary,experience,skills",
            "agency_branding": "QA Agency",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    settings = client.get("/settings")
    assert settings.status_code == 200
    assert "QA Agency" in settings.text
    assert "Georgia" in settings.text
