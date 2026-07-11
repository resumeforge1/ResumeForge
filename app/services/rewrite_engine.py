from __future__ import annotations

from typing import Any

from app.services.ai_providers import get_ai_provider


def improve_summary(client: dict[str, Any]) -> str:
    provider = get_ai_provider()
    return provider.rewrite(client.get("professional_summary", ""), "summary")


def improve_skills(client: dict[str, Any]) -> list[str]:
    provider = get_ai_provider()
    skills = client.get("skills", [])
    improved = provider.rewrite("\n".join(skills), "skills")
    return [line.strip(" -") for line in improved.splitlines() if line.strip(" -")] or skills


def improve_experience(client: dict[str, Any]) -> list[dict[str, Any]]:
    provider = get_ai_provider()
    improved_jobs = []
    for job in client.get("work_experience", []):
        preserved = dict(job)
        preserved["bullets"] = [
            provider.rewrite(bullet, "experience")
            for bullet in job.get("bullets", [])
        ]
        improved_jobs.append(preserved)
    return improved_jobs


def improve_cover_letter(client: dict[str, Any], draft: str) -> str:
    provider = get_ai_provider()
    return provider.rewrite(draft, "cover_letter")
