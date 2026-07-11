from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
DATE_RE = re.compile(r"((?:19|20)\d{2}|Present|Current)", re.IGNORECASE)


SECTION_ALIASES = {
    "education": {"education", "schooling"},
    "skills": {"skills", "core skills", "technical skills", "strengths"},
    "certifications": {"certifications", "licenses", "licenses & certifications", "certificates"},
    "experience": {"experience", "work experience", "professional experience", "employment"},
}


def extract_resume(path: Path) -> dict[str, Any]:
    text = extract_text(path)
    return parse_resume_text(text)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError("Unsupported resume file type")


def parse_resume_text(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = split_sections(lines)
    email = first_match(EMAIL_RE, text)
    phone = first_match(PHONE_RE, text)
    name = infer_name(lines, email, phone)
    skills = split_inline_items(sections.get("skills", []))
    certifications = split_inline_items(sections.get("certifications", []))
    education = sections.get("education", [])
    experience_lines = sections.get("experience", [])

    return {
        "template_key": infer_template(skills, certifications, text),
        "full_name": name,
        "city_state": "",
        "phone": phone,
        "email": email,
        "target_role": "",
        "professional_summary": infer_summary(lines),
        "certifications": certifications,
        "skills": skills,
        "work_experience": parse_experience(experience_lines),
        "education": education,
    }


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "summary"
    sections[current] = []
    for line in lines:
        normalized = line.lower().strip(":")
        matched = next((key for key, names in SECTION_ALIASES.items() if normalized in names), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def parse_experience(lines: list[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        if looks_like_job_header(line):
            if current:
                jobs.append(current)
            dates = DATE_RE.findall(line)
            current = {
                "employer": line,
                "job_title": "",
                "start_date": dates[0] if dates else "",
                "end_date": dates[-1] if len(dates) > 1 else "",
                "bullets": [],
            }
        elif current and (line.startswith(("-", "•", "*")) or len(line) > 45):
            current["bullets"].append(line.strip("-•* "))
        elif current and not current["job_title"]:
            current["job_title"] = line
    if current:
        jobs.append(current)
    return jobs[:8]


def looks_like_job_header(line: str) -> bool:
    return bool(DATE_RE.search(line)) or " - " in line or " | " in line


def split_inline_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        chunks = re.split(r"[,;|]", line)
        items.extend(chunk.strip(" -•\t") for chunk in chunks if chunk.strip(" -•\t"))
    return dedupe(items)


def infer_name(lines: list[str], email: str, phone: str) -> str:
    for line in lines[:6]:
        if email and email in line:
            continue
        if phone and phone in line:
            continue
        if len(line.split()) in (2, 3, 4) and not any(char.isdigit() for char in line):
            return line
    return ""


def infer_summary(lines: list[str]) -> str:
    for line in lines:
        if len(line) > 80 and not EMAIL_RE.search(line):
            return line
    return ""


def infer_template(skills: list[str], certifications: list[str], text: str) -> str:
    cdl_terms = " ".join(skills + certifications + [text]).lower()
    return "cdl" if any(term in cdl_terms for term in ("cdl", "dot", "tanker", "hazmat", "otr")) else "general"


def first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0) if match else ""


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
