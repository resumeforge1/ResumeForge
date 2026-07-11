from __future__ import annotations

from app.repositories.application_repository import ApplicationRepository
from app.repositories.client_repository import ClientRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL


def seed_demo_data() -> int:
    repo = ClientRepository()
    existing = repo.search("Alfredo Cruz")
    if existing:
        return int(existing[0]["id"])
    client_id = repo.create(SAMPLE_ALFREDO_CRUZ_CDL)
    ApplicationRepository().create(
        client_id,
        {
            "company": "Demo Logistics Co.",
            "position": "CDL Class A Driver",
            "salary": "$72,000",
            "status": "Applied",
            "date_applied": "2026-07-08",
            "notes": "Seed demo application.",
        },
    )
    repo.add_note(client_id, "Seed demo client for QA and product demos.")
    return client_id
