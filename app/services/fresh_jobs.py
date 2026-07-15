from __future__ import annotations

import copy
import hashlib
import ipaddress
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.services.job_analyzer import analyze_job_description


FRESHNESS_WINDOWS = {
    "past_2_hours": timedelta(hours=2),
    "today": "today",
    "past_24_hours": timedelta(hours=24),
    "past_3_days": timedelta(days=3),
    "past_7_days": timedelta(days=7),
}

SCHEDULE_INTERVALS = {
    "hourly": timedelta(hours=1),
    "every_3_hours": timedelta(hours=3),
    "twice_daily": timedelta(hours=12),
    "daily": timedelta(days=1),
}


class ProviderFailure(RuntimeError):
    """Raised when a configured provider fails without exposing credentials."""


@dataclass(frozen=True)
class JobSearchResult:
    source: str
    source_job_id: str
    company: str
    title: str
    location: str
    remote_type: str
    salary_min: int
    salary_max: int
    employment_type: str
    schedule: str
    description: str
    posted_at: str
    discovered_at: str
    apply_url: str
    expires_at: str = ""
    expiration_status: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["normalized_key"] = normalized_job_key(data)
        return data


class JobSourceProvider(Protocol):
    name: str

    def fetch_jobs(self, preferences: dict[str, Any], candidate_profile: dict[str, Any]) -> list[dict[str, Any]]:
        ...


class MockJobProvider:
    name = "mock"
    label = "Mock Jobs"

    def health(self) -> dict[str, Any]:
        return {
            "provider_key": self.name,
            "label": self.label,
            "status": "ready",
            "message": "Deterministic local provider for tests and demos.",
        }

    def fetch_jobs(self, preferences: dict[str, Any], candidate_profile: dict[str, Any]) -> list[dict[str, Any]]:
        now = current_utc()
        role = preferences.get("target_role") or candidate_profile.get("target_role") or "CDL Class A Driver"
        location = preferences.get("location") or candidate_profile.get("location") or "Dallas, TX"
        jobs = [
            JobSearchResult(
                source=self.name,
                source_job_id="mock-cdl-route-001",
                company="Labatt Food Service",
                title="CDL Class A Route Driver",
                location=location,
                remote_type="onsite",
                salary_min=68000,
                salary_max=82000,
                employment_type="Full-time",
                schedule="Local days",
                description=(
                    "Texas CDL Class A route driver for food service distribution. Requires safe driving, "
                    "DOT compliance, pre-trip inspections, unloading cases, dolly use, and customer delivery service."
                ),
                posted_at=(now - timedelta(hours=1)).isoformat(),
                discovered_at=now.isoformat(),
                apply_url="https://jobs.example.test/labatt-route-driver",
            ),
            JobSearchResult(
                source=self.name,
                source_job_id="mock-intermodal-002",
                company="North Texas Intermodal",
                title="Intermodal CDL Driver",
                location="Dallas, TX",
                remote_type="onsite",
                salary_min=72000,
                salary_max=90000,
                employment_type="Full-time",
                schedule="Day shift",
                description=(
                    "Commercial driving role supporting intermodal freight, local routes, ELD documentation, "
                    "load securement, clean MVR, and DOT safety practices."
                ),
                posted_at=(now - timedelta(hours=8)).isoformat(),
                discovered_at=now.isoformat(),
                apply_url="https://jobs.example.test/intermodal-driver",
            ),
            JobSearchResult(
                source=self.name,
                source_job_id="mock-warehouse-003",
                company="Acme Retail",
                title="Warehouse Associate",
                location="Fort Worth, TX",
                remote_type="onsite",
                salary_min=36000,
                salary_max=42000,
                employment_type="Full-time",
                schedule="Night shift",
                description="Warehouse associate handling inventory, stocking, RF scanners, and team lifting.",
                posted_at=(now - timedelta(days=2)).isoformat(),
                discovered_at=now.isoformat(),
                apply_url="https://jobs.example.test/warehouse-associate",
            ),
            JobSearchResult(
                source=self.name,
                source_job_id="mock-remote-dispatch-004",
                company="FleetDesk",
                title=f"{role} Dispatcher",
                location="Remote",
                remote_type="remote",
                salary_min=52000,
                salary_max=62000,
                employment_type="Full-time",
                schedule="Weekdays",
                description="Remote dispatch coordinator using route planning, customer service, and freight documentation.",
                posted_at=(now - timedelta(days=6)).isoformat(),
                discovered_at=now.isoformat(),
                apply_url="https://jobs.example.test/remote-dispatch",
            ),
        ]
        excluded = {normalize_text(company) for company in preferences.get("excluded_companies", [])}
        return [job.to_dict() for job in jobs if normalize_text(job.company) not in excluded]


class USAJobsProvider:
    name = "usajobs"
    label = "USAJOBS"
    endpoint = "https://data.usajobs.gov/api/search"

    def __init__(
        self,
        api_key: str | None = None,
        user_agent: str | None = None,
        http_client: Any | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("USAJOBS_API_KEY", "")
        self.user_agent = user_agent if user_agent is not None else os.getenv("USAJOBS_USER_AGENT", "")
        self.http_client = http_client or httpx.Client()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.user_agent)

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "provider_key": self.name,
                "label": self.label,
                "status": "not_configured",
                "message": "Set USAJOBS_API_KEY and USAJOBS_USER_AGENT to enable this provider.",
            }
        return {
            "provider_key": self.name,
            "label": self.label,
            "status": "ready",
            "message": "Configured with official USAJOBS API credentials.",
        }

    def fetch_jobs(self, preferences: dict[str, Any], candidate_profile: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        params = {
            "Keyword": preferences.get("target_role") or candidate_profile.get("target_role") or "",
            "LocationName": preferences.get("location") or candidate_profile.get("location") or "",
            "ResultsPerPage": 25,
        }
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": self.user_agent,
            "Authorization-Key": self.api_key,
        }
        try:
            response = self.http_client.get(self.endpoint, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderFailure("USAJOBS request timed out.") from exc
        except Exception as exc:
            raise ProviderFailure("USAJOBS provider failed.") from exc
        items = payload.get("SearchResult", {}).get("SearchResultItems", [])
        return [normalize_usajobs_item(item, current_utc().isoformat()) for item in items]


def normalize_usajobs_item(item: dict[str, Any], discovered_at: str) -> dict[str, Any]:
    descriptor = item.get("MatchedObjectDescriptor", {}) or {}
    locations = descriptor.get("PositionLocation", []) or []
    location = descriptor.get("PositionLocationDisplay") or ""
    if not location and locations:
        first_location = locations[0] or {}
        city = first_location.get("CityName", "")
        state = first_location.get("CountrySubDivisionCode", "")
        location = ", ".join(part for part in (city, state) if part)
    remuneration = (descriptor.get("PositionRemuneration", []) or [{}])[0] or {}
    user_area = descriptor.get("UserArea", {}) or {}
    details = user_area.get("Details", {}) or {}
    job = {
        "source": "usajobs",
        "source_job_id": str(item.get("MatchedObjectId") or descriptor.get("PositionID") or ""),
        "company": descriptor.get("OrganizationName", "USAJOBS"),
        "title": descriptor.get("PositionTitle", ""),
        "location": location or "Not listed",
        "remote_type": "remote" if descriptor.get("TeleworkEligible") else "onsite",
        "salary_min": parse_int(remuneration.get("MinimumRange")),
        "salary_max": parse_int(remuneration.get("MaximumRange")),
        "employment_type": ", ".join(descriptor.get("PositionSchedule", []) or []),
        "schedule": ", ".join(descriptor.get("PositionOfferingType", []) or []),
        "description": " ".join(
            part
            for part in (
                descriptor.get("QualificationSummary", ""),
                details.get("JobSummary", ""),
            )
            if part
        ).strip(),
        "posted_at": descriptor.get("PublicationStartDate", ""),
        "discovered_at": discovered_at,
        "apply_url": descriptor.get("PositionURI", ""),
        "expires_at": descriptor.get("ApplicationCloseDate", ""),
        "expiration_status": "active",
        "provider_confidence": 95,
    }
    job["normalized_key"] = normalized_job_key(job)
    return job


def build_manual_job(data: dict[str, Any], discovered_at: str | None = None) -> dict[str, Any]:
    title = str(data.get("title", "")).strip()
    company = str(data.get("company", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title or not company or not description:
        raise ValueError("Manual job imports require title, company, and description.")
    apply_url = validate_public_job_url(str(data.get("apply_url", "")).strip())
    salary_min, salary_max = parse_salary_range(str(data.get("salary", "")))
    posted_at = str(data.get("posted_at", "")).strip() or current_utc().isoformat()
    source_job_id = hashlib.sha256("|".join([company, title, apply_url, description[:80]]).encode("utf-8")).hexdigest()[:16]
    job = {
        "source": "manual",
        "source_job_id": f"manual-{source_job_id}",
        "company": company,
        "title": title,
        "location": str(data.get("location", "")).strip(),
        "remote_type": str(data.get("remote_type", "onsite")).strip() or "onsite",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "employment_type": str(data.get("employment_type", "")).strip(),
        "schedule": str(data.get("schedule", "")).strip(),
        "description": description,
        "posted_at": posted_at,
        "discovered_at": discovered_at or current_utc().isoformat(),
        "apply_url": apply_url,
        "expires_at": "",
        "expiration_status": "unknown",
        "provider_confidence": 70,
    }
    job["normalized_key"] = normalized_job_key(job)
    return job


def validate_public_job_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Apply URL must be an http or https URL.")
    host = (parsed.hostname or "").strip().lower()
    if not host or host == "localhost" or host.endswith(".local"):
        raise ValueError("Apply URL must use a public host.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast):
        raise ValueError("Apply URL cannot point to a private or local address.")
    return url


def calculate_next_check_at(interval_key: str, from_time: datetime | None = None) -> str:
    start = from_time or current_utc()
    return (start + SCHEDULE_INTERVALS.get(interval_key, SCHEDULE_INTERVALS["daily"])).isoformat()


def extract_candidate_profile(client: dict[str, Any]) -> dict[str, Any]:
    work = client.get("work_experience", []) or []
    text_parts = [
        client.get("target_role", ""),
        client.get("professional_summary", ""),
        " ".join(client.get("skills", []) or []),
        " ".join(client.get("certifications", []) or []),
        " ".join(client.get("education", []) or []),
    ]
    for entry in work:
        text_parts.extend(
            [
                str(entry.get("job_title", "")),
                str(entry.get("employer", "")),
                str(entry.get("start_date", "")),
                str(entry.get("end_date", "")),
                " ".join(entry.get("bullets", []) or []),
            ]
        )
    resume_text = " ".join(text_parts)
    return {
        "client_id": client.get("id"),
        "target_role": client.get("target_role", ""),
        "location": client.get("city_state", ""),
        "skills": normalize_skills(client.get("skills", []) or [], resume_text),
        "job_titles": dedupe_preserve_order([str(entry.get("job_title", "")).strip() for entry in work if str(entry.get("job_title", "")).strip()]),
        "years_experience": estimate_years_experience(client),
        "certifications": normalize_skills(client.get("certifications", []) or [], resume_text),
        "education": normalize_education(client.get("education", []) or []),
        "industries": infer_industries(resume_text),
        "resume_text": resume_text,
    }


def normalize_skills(items: list[str], text: str = "") -> list[str]:
    known = [
        "CDL Class A Operations",
        "OTR and Local Routes",
        "Intermodal Freight",
        "Roll-off and Ready-mix",
        "Refrigerated Food Distribution",
        "LTL Delivery",
        "DOT Compliance",
        "ELD Documentation",
        "Load Securement",
        "Pre-trip and Post-trip Inspections",
        "Customer Delivery Service",
        "Defensive Driving",
        "Route Planning",
        "Warehouse Operations",
    ]
    values = list(items)
    normalized_text = normalize_text(" ".join(items) + " " + text)
    for skill in known:
        tokens = [token for token in normalize_text(skill).split() if len(token) > 3]
        if any(token in normalized_text for token in tokens):
            values.append(skill)
    return dedupe_preserve_order([chunk for item in values for chunk in split_skill_item(item)])


def split_skill_item(item: str) -> list[str]:
    return [part.strip(" -\t") for part in re.split(r"[,;|]\s*", str(item)) if part.strip(" -\t")]


def normalize_education(education: list[str]) -> list[str]:
    values: list[str] = []
    for item in education:
        text = str(item).strip()
        if not text:
            continue
        values.append(text)
        if " - " in text:
            values.append(text.split(" - ", 1)[0].strip())
    return dedupe_preserve_order(values)


def estimate_years_experience(client: dict[str, Any]) -> int:
    parts = [
        client.get("professional_summary", ""),
        " ".join(client.get("skills", []) or []),
        " ".join(client.get("certifications", []) or []),
    ]
    for entry in client.get("work_experience", []) or []:
        parts.extend([str(entry.get(key, "")) for key in ("job_title", "employer", "start_date", "end_date")])
        parts.append(" ".join(entry.get("bullets", []) or []))
    text = normalize_text(" ".join(parts))
    matches = [int(value) for value in re.findall(r"(\d{1,2})\+?\s+years?", text)]
    if matches:
        return max(matches)
    since_matches = [int(value) for value in re.findall(r"since\s+(20\d{2}|19\d{2})", text)]
    if since_matches:
        return max(1, current_utc().year - min(since_matches))
    years = {int(year) for year in re.findall(r"\b(20\d{2}|19\d{2})\b", text)}
    if len(years) >= 2:
        return max(1, max(years) - min(years))
    return max(1, len(client.get("work_experience", []) or []))


def infer_industries(text: str) -> list[str]:
    normalized = normalize_text(text)
    mapping = {
        "transportation": ["cdl", "commercial driving", "route", "ltl", "intermodal", "freight"],
        "food distribution": ["food distribution", "refrigerated", "food service"],
        "construction materials": ["ready-mix", "roll-off", "materials"],
        "warehouse": ["warehouse", "pallet", "dock"],
    }
    return [industry for industry, terms in mapping.items() if any(term in normalized for term in terms)]


def filter_by_freshness(jobs: list[dict[str, Any]], freshness: str, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or current_utc()
    window = FRESHNESS_WINDOWS.get(freshness, FRESHNESS_WINDOWS["past_7_days"])
    filtered = []
    for job in jobs:
        posted = parse_datetime(job.get("posted_at", ""))
        if posted is None:
            continue
        if window == "today":
            if posted.date() == now.date():
                filtered.append(job)
        elif posted > now - window:
            filtered.append(job)
    return filtered


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    seen_ids: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    for job in jobs:
        job = dict(job)
        job["normalized_key"] = job.get("normalized_key") or normalized_job_key(job)
        identity = (normalize_text(job.get("source", "")), normalize_text(job.get("source_job_id", "")))
        url = normalize_text(job.get("apply_url", ""))
        key = job["normalized_key"]
        if identity in seen_ids or (url and url in seen_urls) or key in seen_keys:
            continue
        if any(similar_jobs(job, existing) for existing in accepted):
            continue
        accepted.append(job)
        seen_ids.add(identity)
        if url:
            seen_urls.add(url)
        seen_keys.add(key)
    return accepted


def score_job(job: dict[str, Any], candidate_profile: dict[str, Any], preferences: dict[str, Any]) -> dict[str, Any]:
    profile_skills = candidate_profile.get("skills", []) or []
    profile_certs = candidate_profile.get("certifications", []) or []
    job_terms = extract_job_terms(job)
    matched_skills = [skill for skill in profile_skills if any(term_overlap(skill, term) for term in job_terms)]
    required_certs = preferences.get("required_licenses_certifications", []) or []
    cert_matches = [cert for cert in required_certs if any(term_overlap(cert, existing) for existing in profile_certs)]
    missing_qualifications = [
        term for term in job_terms[:12] if not any(term_overlap(term, skill) for skill in profile_skills + profile_certs)
    ][:6]
    breakdown = {
        "skill_match": percent(len(matched_skills), max(1, min(len(job_terms), 8))),
        "title_similarity": title_similarity(job.get("title", ""), candidate_profile),
        "experience_fit": experience_fit(job, candidate_profile),
        "certification_fit": percent(len(cert_matches), len(required_certs)) if required_certs else certification_signal(job, profile_certs),
        "location_remote_fit": location_remote_fit(job, candidate_profile, preferences),
        "salary_fit": salary_fit(job, preferences),
        "freshness": freshness_score(job),
    }
    weights = {
        "skill_match": 0.24,
        "title_similarity": 0.16,
        "experience_fit": 0.14,
        "certification_fit": 0.14,
        "location_remote_fit": 0.12,
        "salary_fit": 0.10,
        "freshness": 0.10,
    }
    score = round(sum(breakdown[key] * weight for key, weight in weights.items()))
    return {
        "score": max(0, min(100, score)),
        "breakdown": breakdown,
        "matched_skills": dedupe_preserve_order(matched_skills)[:8],
        "missing_qualifications": missing_qualifications,
        "qualification_coverage": breakdown["skill_match"],
    }


def rank_jobs(matches: list[dict[str, Any]], sort: str = "best_match") -> list[dict[str, Any]]:
    if sort == "newest":
        return sorted(matches, key=lambda item: parse_datetime(item.get("posted_at", "")) or datetime.min.replace(tzinfo=UTC), reverse=True)
    if sort == "highest_salary":
        return sorted(matches, key=lambda item: (item.get("salary_max") or item.get("salary_min") or 0, item.get("score", 0)), reverse=True)
    return sorted(matches, key=lambda item: (item.get("score", 0), freshness_score(item), item.get("salary_max") or 0), reverse=True)


def prepare_application_package(client: dict[str, Any], job: dict[str, Any], match: dict[str, Any] | None = None) -> dict[str, Any]:
    tailored = copy.deepcopy(client)
    analysis = analyze_job_description(job.get("description", ""), client)
    keywords = dedupe_preserve_order(
        analysis.get("keywords", []) + analysis.get("required_skills", []) + (match or {}).get("matched_skills", [])
    )[:12]
    if keywords:
        existing = tailored.get("skills", []) or []
        for keyword in keywords:
            if any(term_overlap(keyword, skill) for skill in existing):
                continue
            if any(term_overlap(keyword, skill) for skill in client.get("skills", []) or []):
                existing.append(keyword)
        tailored["skills"] = dedupe_preserve_order(existing)
    return {
        "tailored_resume": tailored,
        "cover_letter": build_cover_letter_draft(client, job, keywords),
        "ats_keywords": keywords,
        "status": "draft",
    }


def build_cover_letter_draft(client: dict[str, Any], job: dict[str, Any], keywords: list[str]) -> str:
    name = client.get("full_name", "Candidate")
    role = job.get("title", "the role")
    company = job.get("company", "your team")
    summary = client.get("professional_summary", "").strip()
    skills = ", ".join(keywords[:5]) if keywords else ", ".join((client.get("skills", []) or [])[:5])
    return (
        f"{name}\n\nDear Hiring Team,\n\n"
        f"I am interested in the {role} opportunity with {company}. "
        f"My background includes {skills}. {summary}\n\n"
        "I will review this draft and confirm every detail before submitting an application.\n\n"
        f"Sincerely,\n{name}"
    )


def extract_job_terms(job: dict[str, Any]) -> list[str]:
    text = normalize_text(" ".join([job.get("title", ""), job.get("description", ""), job.get("employment_type", ""), job.get("schedule", "")]))
    known = [
        "CDL Class A Operations",
        "Route Delivery",
        "Food Distribution",
        "DOT Compliance",
        "Pre-trip and Post-trip Inspections",
        "Dolly Use",
        "Unloading Cases",
        "Customer Delivery Service",
        "Intermodal Freight",
        "ELD Documentation",
        "Load Securement",
        "Safe Driving",
        "Warehouse Operations",
        "Route Planning",
    ]
    terms = [term for term in known if any(token in text for token in normalize_text(term).split() if len(token) > 5)]
    if "cdl" in text and "class a" in text and "CDL Class A Operations" not in terms:
        terms.insert(0, "CDL Class A Operations")
    return dedupe_preserve_order(terms)


def title_similarity(title: str, profile: dict[str, Any]) -> int:
    candidates = [profile.get("target_role", "")] + (profile.get("job_titles", []) or [])
    if not candidates:
        return 0
    return round(max(SequenceMatcher(None, normalize_text(title), normalize_text(candidate)).ratio() for candidate in candidates) * 100)


def experience_fit(job: dict[str, Any], profile: dict[str, Any]) -> int:
    required = 1
    match = re.search(r"(\d{1,2})\+?\s+years?", normalize_text(job.get("description", "")))
    if match:
        required = int(match.group(1))
    years = int(profile.get("years_experience") or 0)
    return 100 if years >= required else round((years / max(1, required)) * 100)


def certification_signal(job: dict[str, Any], certifications: list[str]) -> int:
    text = normalize_text(job.get("description", ""))
    if "cdl" in text and any("cdl" in normalize_text(cert) for cert in certifications):
        return 100
    return 70 if not certifications else 80


def location_remote_fit(job: dict[str, Any], profile: dict[str, Any], preferences: dict[str, Any]) -> int:
    remote_pref = normalize_text(preferences.get("remote_preference", "any"))
    remote_type = normalize_text(job.get("remote_type", "onsite"))
    if remote_pref in {"remote", "hybrid"} and remote_pref in remote_type:
        return 100
    if remote_pref == "remote" and remote_type == "onsite":
        return 35
    pref_location = normalize_text(preferences.get("location", "") or profile.get("location", ""))
    job_location = normalize_text(job.get("location", ""))
    if not pref_location or "remote" in job_location:
        return 90
    return 100 if any(part.strip() and part.strip() in job_location for part in pref_location.split(",")) else 65


def salary_fit(job: dict[str, Any], preferences: dict[str, Any]) -> int:
    minimum = int(preferences.get("minimum_salary") or 0)
    if not minimum:
        return 85
    salary = job.get("salary_max") or job.get("salary_min") or 0
    return 100 if salary >= minimum else max(0, round((salary / minimum) * 100))


def parse_salary_range(value: str) -> tuple[int | None, int | None]:
    numbers = [int(match.replace(",", "")) for match in re.findall(r"\d[\d,]*", value or "")]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers[:2]), max(numbers[:2])


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def freshness_score(job: dict[str, Any]) -> int:
    posted = parse_datetime(job.get("posted_at", ""))
    if posted is None:
        return 30
    hours = max(0.0, (current_utc() - posted).total_seconds() / 3600)
    if hours <= 2:
        return 100
    if hours <= 24:
        return 88
    if hours <= 72:
        return 72
    if hours <= 168:
        return 55
    return 25


def normalized_job_key(job: dict[str, Any]) -> str:
    return "|".join(normalize_text(str(job.get(field, ""))) for field in ("company", "title", "location"))


def similar_jobs(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return SequenceMatcher(None, normalized_job_key(left), normalized_job_key(right)).ratio() > 0.92


def term_overlap(left: str, right: str) -> bool:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return False
    if left_norm in right_norm or right_norm in left_norm:
        return True
    left_tokens = {token for token in left_norm.split() if len(token) > 2}
    right_tokens = {token for token in right_norm.split() if len(token) > 2}
    return bool(left_tokens and right_tokens and len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens))) >= 0.5)


def percent(part: int, whole: int) -> int:
    if whole <= 0:
        return 100
    return max(0, min(100, round((part / whole) * 100)))


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9+]+", " ", str(value).lower()).strip()


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def current_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def posting_age(posted_at: str) -> str:
    posted = parse_datetime(posted_at)
    if posted is None:
        return "Unknown"
    hours = max(0, math.floor((current_utc() - posted).total_seconds() / 3600))
    if hours < 1:
        return "Just posted"
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        clean = str(item).strip()
        key = normalize_text(clean)
        if clean and key not in seen:
            result.append(clean)
            seen.add(key)
    return result
