import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
INDUSTRY_TEMPLATE_DIR = BASE_DIR / "templates"


GENERAL_TEMPLATE = {
    "key": "general",
    "label": "General Professional",
    "resume_template": "resumes/general.html",
    "layout": "professional-clean",
    "experience_heading": "Professional Experience",
    "core_strengths": [
        "Client Communication",
        "Operations Support",
        "Process Improvement",
        "Team Collaboration",
        "Documentation",
        "Problem Solving",
    ],
}


DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "cdl": {
        "key": "cdl",
        "label": "CDL Driver",
        "resume_template": "resumes/cdl.html",
        "layout": "two-column-compact",
        "colors": {"accent": "#0f5792", "header": "#0f5792"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "cdl_cover_letter",
        "linkedin": "cdl_linkedin",
        "interview": "cdl_interview",
        "ats_keywords": [
            "CDL Class A",
            "DOT Compliance",
            "OTR",
            "Local Routes",
            "Intermodal",
            "LTL",
            "Refrigerated Freight",
            "Roll-off",
            "Ready-mix",
            "ELD",
        ],
        "experience_heading": "Commercial Driving Experience",
        "core_strengths": [
            "CDL Class A Operations",
            "OTR and Local Routes",
            "Intermodal Freight",
            "Roll-off and Ready-mix",
            "Refrigerated Food Distribution",
            "LTL Delivery",
            "DOT Compliance",
            "ELD Documentation",
            "Load Securement",
        ],
    },
    "general": GENERAL_TEMPLATE,
    "healthcare": {
        "key": "healthcare",
        "label": "Healthcare",
        "resume_template": "resumes/general.html",
        "layout": "clinical-clean",
        "colors": {"accent": "#16756f", "header": "#16756f"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "healthcare_cover_letter",
        "linkedin": "healthcare_linkedin",
        "interview": "healthcare_interview",
        "ats_keywords": ["Patient Care", "HIPAA", "Clinical Documentation", "Care Coordination"],
        "experience_heading": "Healthcare Experience",
        "core_strengths": [
            "Patient Care",
            "HIPAA Compliance",
            "Clinical Documentation",
            "Care Coordination",
            "Scheduling",
            "Quality Standards",
        ],
    },
    "software": {
        "key": "software",
        "label": "Software",
        "resume_template": "resumes/general.html",
        "layout": "technical-clean",
        "colors": {"accent": "#3157a4", "header": "#3157a4"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "software_cover_letter",
        "linkedin": "software_linkedin",
        "interview": "software_interview",
        "ats_keywords": ["Python", "APIs", "SQL", "Cloud", "Testing", "Agile"],
        "experience_heading": "Technical Experience",
        "core_strengths": [
            "Software Development",
            "API Integration",
            "Database Design",
            "Testing",
            "Debugging",
            "Agile Delivery",
        ],
    },
    "finance": {
        "key": "finance",
        "label": "Finance",
        "resume_template": "resumes/general.html",
        "layout": "executive-clean",
        "colors": {"accent": "#244f73", "header": "#244f73"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "finance_cover_letter",
        "linkedin": "finance_linkedin",
        "interview": "finance_interview",
        "ats_keywords": ["Financial Analysis", "Reporting", "Forecasting", "Compliance", "Excel"],
        "experience_heading": "Finance Experience",
        "core_strengths": [
            "Financial Analysis",
            "Reporting",
            "Forecasting",
            "Budgeting",
            "Compliance",
            "Stakeholder Communication",
        ],
    },
    "warehouse": {
        "key": "warehouse",
        "label": "Warehouse",
        "resume_template": "resumes/general.html",
        "layout": "operations-clean",
        "colors": {"accent": "#44613f", "header": "#44613f"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "warehouse_cover_letter",
        "linkedin": "warehouse_linkedin",
        "interview": "warehouse_interview",
        "ats_keywords": ["Inventory", "Forklift", "Shipping", "Receiving", "Safety"],
        "experience_heading": "Warehouse Experience",
        "core_strengths": [
            "Inventory Control",
            "Forklift Operation",
            "Order Picking",
            "Shipping and Receiving",
            "Safety Compliance",
            "Team Collaboration",
        ],
    },
    "sales": {
        "key": "sales",
        "label": "Sales",
        "resume_template": "resumes/general.html",
        "layout": "revenue-clean",
        "colors": {"accent": "#8a4f19", "header": "#8a4f19"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "sales_cover_letter",
        "linkedin": "sales_linkedin",
        "interview": "sales_interview",
        "ats_keywords": ["Pipeline", "CRM", "Prospecting", "Closing", "Account Management"],
        "experience_heading": "Sales Experience",
        "core_strengths": [
            "Prospecting",
            "CRM Management",
            "Pipeline Development",
            "Closing",
            "Account Management",
            "Customer Retention",
        ],
    },
    "executive": {
        "key": "executive",
        "label": "Executive",
        "resume_template": "resumes/general.html",
        "layout": "leadership-clean",
        "colors": {"accent": "#343a46", "header": "#343a46"},
        "fonts": {"primary": "Arial", "heading": "Arial"},
        "cover_letter": "executive_cover_letter",
        "linkedin": "executive_linkedin",
        "interview": "executive_interview",
        "ats_keywords": ["Strategy", "Leadership", "P&L", "Operations", "Transformation"],
        "experience_heading": "Leadership Experience",
        "core_strengths": [
            "Strategic Planning",
            "Team Leadership",
            "Operational Excellence",
            "Change Management",
            "P&L Ownership",
            "Stakeholder Alignment",
        ],
    },
}


def template_search_paths() -> list[Path]:
    candidates = [
        INDUSTRY_TEMPLATE_DIR,
        BASE_DIR / "templates",
        Path.cwd() / "templates",
    ]
    paths: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.exists():
            paths.append(resolved)
            seen.add(resolved)
    return paths


def load_templates() -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {key: dict(config) for key, config in DEFAULT_TEMPLATES.items()}
    for template_dir in template_search_paths():
        paths = list(template_dir.glob("*.json"))
        paths.extend(template_dir.glob("*/template.json"))
        for path in sorted(paths, key=lambda item: str(item)):
            with path.open("r", encoding="utf-8") as handle:
                config = json.load(handle)
            key = config.get("key")
            if key:
                templates[key] = {**GENERAL_TEMPLATE, **templates.get(key, {}), **config}
    return templates


def get_template_config(template_key: str | None) -> dict[str, Any]:
    templates = load_templates()
    return templates.get(template_key or "general", templates["general"])


def list_template_configs() -> list[dict[str, Any]]:
    return list(load_templates().values())
