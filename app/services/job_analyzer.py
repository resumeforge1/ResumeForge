from __future__ import annotations

import re
from typing import Any

from app.template_registry import get_template_config


STOPWORDS = {
    "and", "the", "with", "for", "you", "are", "will", "this", "that", "from", "have",
    "our", "your", "job", "role", "work", "team", "must", "able", "into", "about",
}


def analyze_job_description(job_description: str, client: dict[str, Any]) -> dict[str, Any]:
    jd_terms = extract_keywords(job_description)
    template_terms = get_template_config(client.get("template_key")).get("core_strengths", [])
    required_skills = [term for term in jd_terms if looks_like_skill(term)]
    required_certifications = [
        term for term in jd_terms if any(token in term.lower() for token in ("license", "cert", "cdl", "hazmat", "degree"))
    ]
    client_terms = set(extract_keywords(client_text(client)))
    matched = sorted({term for term in jd_terms if term.lower() in client_terms})
    missing = sorted({term for term in jd_terms if term.lower() not in client_terms})[:25]
    keyword_count = max(len(jd_terms), 1)
    match_percentage = round((len(matched) / keyword_count) * 100)
    ats_score = min(100, round(match_percentage * 0.75 + coverage_bonus(client, template_terms)))

    return {
        "required_skills": required_skills[:20],
        "required_certifications": required_certifications[:12],
        "keywords": jd_terms[:40],
        "experience_requirements": extract_experience_requirements(job_description),
        "ats_score": ats_score,
        "missing_keywords": missing,
        "match_percentage": match_percentage,
        "recommendations": recommendations(missing, required_certifications, client),
    }


def extract_keywords(text: str) -> list[str]:
    phrases = re.findall(r"[A-Za-z][A-Za-z0-9+/#.-]*(?:\s+[A-Za-z][A-Za-z0-9+/#.-]*){0,2}", text)
    cleaned = []
    for phrase in phrases:
        phrase = phrase.strip(" .,:;()").lower()
        if len(phrase) < 3 or phrase in STOPWORDS:
            continue
        if all(part in STOPWORDS for part in phrase.split()):
            continue
        cleaned.append(phrase)
    return sorted(set(cleaned))


def extract_experience_requirements(text: str) -> list[str]:
    return re.findall(r"(?:\d+\+?\s+years?[^.\n]*|experience with[^.\n]*|background in[^.\n]*)", text, re.IGNORECASE)[:10]


def looks_like_skill(term: str) -> bool:
    return len(term.split()) <= 3 and not any(char.isdigit() for char in term)


def client_text(client: dict[str, Any]) -> str:
    jobs = client.get("work_experience", [])
    bullets = " ".join(" ".join(job.get("bullets", [])) for job in jobs)
    return " ".join(
        [
            client.get("professional_summary", ""),
            " ".join(client.get("skills", [])),
            " ".join(client.get("certifications", [])),
            bullets,
            " ".join(client.get("education", [])),
        ]
    ).lower()


def coverage_bonus(client: dict[str, Any], template_terms: list[str]) -> int:
    text = client_text(client)
    return min(25, sum(3 for term in template_terms if term.lower() in text))


def recommendations(missing: list[str], certs: list[str], client: dict[str, Any]) -> list[str]:
    output = []
    if missing:
        output.append("Add truthful missing keywords where they match the client's actual experience.")
    if certs:
        output.append("Confirm required certifications before listing them as active credentials.")
    if not client.get("professional_summary"):
        output.append("Add a concise summary aligned with the target role.")
    output.append("Mirror the job title and core requirements in the resume only when accurate.")
    return output
