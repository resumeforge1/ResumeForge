from app.services.import_engine import parse_resume_text
from app.services.job_analyzer import analyze_job_description
from app.services.rewrite_engine import improve_experience
from app.template_registry import get_template_config, list_template_configs


def test_parse_resume_text_extracts_contact_and_sections():
    text = """
    Alfredo Cruz
    Dallas, TX
    alfredo@example.com
    (214) 555-0198
    Skills
    DOT Compliance, Intermodal Freight, LTL Delivery
    Licenses
    Texas CDL Class A License
    Education
    H. Grady Spruce High School
    Work Experience
    Texas Carrier | 2019 - Present
    CDL Driver
    - Delivered refrigerated freight across regional routes.
    """
    parsed = parse_resume_text(text)
    assert parsed["full_name"] == "Alfredo Cruz"
    assert parsed["email"] == "alfredo@example.com"
    assert parsed["template_key"] == "cdl"
    assert "DOT Compliance" in parsed["skills"]
    assert parsed["work_experience"][0]["start_date"] == "2019"


def test_job_analysis_finds_missing_keywords():
    client = {
        "template_key": "cdl",
        "professional_summary": "CDL driver with DOT compliance experience.",
        "skills": ["DOT Compliance", "LTL Delivery"],
        "certifications": ["Texas CDL Class A License"],
        "work_experience": [],
        "education": [],
    }
    result = analyze_job_description("Requires CDL Class A, hazmat, intermodal freight, and 2 years experience.", client)
    assert result["ats_score"] >= 0
    assert "hazmat" in result["missing_keywords"]


def test_rewrite_preserves_job_identity_fields():
    client = {
        "work_experience": [
            {
                "employer": "Texas Carrier",
                "job_title": "CDL Driver",
                "start_date": "2019",
                "end_date": "Present",
                "bullets": ["Delivered freight."],
            }
        ]
    }
    improved = improve_experience(client)
    assert improved[0]["employer"] == "Texas Carrier"
    assert improved[0]["job_title"] == "CDL Driver"
    assert improved[0]["start_date"] == "2019"


def test_template_marketplace_discovers_industries():
    keys = {template["key"] for template in list_template_configs()}
    assert {"cdl", "general", "healthcare", "software", "finance", "warehouse", "sales", "executive"} <= keys
    assert get_template_config("cdl")["experience_heading"] == "Commercial Driving Experience"
