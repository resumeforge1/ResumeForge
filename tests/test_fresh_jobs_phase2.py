from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.services.fresh_jobs import (
    ProviderFailure,
    USAJobsProvider,
    build_manual_job,
    calculate_next_check_at,
    deduplicate_jobs,
    normalize_usajobs_item,
)
from tests.conftest import create_client


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeUSAJobsClient:
    def get(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse(
            {
                "SearchResult": {
                    "SearchResultItems": [
                        {
                            "MatchedObjectId": "USA-123",
                            "MatchedObjectDescriptor": {
                                "PositionTitle": "Motor Vehicle Operator",
                                "OrganizationName": "Department of Logistics",
                                "PositionLocationDisplay": "Dallas, TX",
                                "QualificationSummary": "Requires CDL Class A, safe driving, and route delivery.",
                                "PublicationStartDate": "2026-07-14T10:00:00+00:00",
                                "ApplicationCloseDate": "2026-08-01T10:00:00+00:00",
                                "PositionURI": "https://www.usajobs.gov/job/123",
                                "PositionRemuneration": [{"MinimumRange": "68000", "MaximumRange": "82000"}],
                                "TeleworkEligible": False,
                                "PositionSchedule": ["Full-time"],
                                "PositionOfferingType": ["Permanent"],
                            },
                        }
                    ]
                }
            }
        )


class TimeoutClient:
    def get(self, *args, **kwargs):
        raise httpx.TimeoutException("timeout")


def test_usajobs_missing_api_key_is_graceful():
    provider = USAJobsProvider(api_key="", user_agent="")
    assert provider.health()["status"] == "not_configured"
    assert provider.fetch_jobs({}, {}) == []


def test_usajobs_provider_normalizes_jobs_without_internet():
    provider = USAJobsProvider(api_key="key", user_agent="qa@example.com", http_client=FakeUSAJobsClient())
    jobs = provider.fetch_jobs({"target_role": "driver", "location": "Dallas"}, {})
    assert len(jobs) == 1
    assert jobs[0]["source"] == "usajobs"
    assert jobs[0]["source_job_id"] == "USA-123"
    assert jobs[0]["company"] == "Department of Logistics"
    assert jobs[0]["salary_max"] == 82000


def test_usajobs_provider_failure_is_explicit_and_safe():
    provider = USAJobsProvider(api_key="key", user_agent="qa@example.com", http_client=TimeoutClient())
    with pytest.raises(ProviderFailure):
        provider.fetch_jobs({}, {})


def test_normalize_usajobs_item_handles_sparse_payload():
    job = normalize_usajobs_item({"MatchedObjectId": "1", "MatchedObjectDescriptor": {"PositionTitle": "Driver"}}, "2026-07-14T10:00:00+00:00")
    assert job["title"] == "Driver"
    assert job["source"] == "usajobs"
    assert job["normalized_key"]


def test_schedule_interval_and_overlap_prevention(qa_app):
    repo = FreshJobsRepository()
    start = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
    assert calculate_next_check_at("every_3_hours", start) == "2026-07-14T11:00:00+00:00"
    assert repo.begin_scheduled_run() is True
    assert repo.begin_scheduled_run() is False
    repo.finish_scheduled_run(start.isoformat(), calculate_next_check_at("daily", start))
    assert repo.begin_scheduled_run() is True


def test_new_seen_updated_job_detection(qa_app):
    repo = FreshJobsRepository()
    job = build_manual_job(
        {
            "title": "CDL Driver",
            "company": "Example Carrier",
            "location": "Dallas, TX",
            "apply_url": "https://jobs.example.com/driver",
            "description": "CDL Class A route delivery with safe driving.",
        }
    )
    job_id, state = repo.insert_job_with_state(job)
    assert state == "new"
    assert repo.insert_job_with_state(job) == (job_id, "seen")
    changed = dict(job)
    changed["description"] = job["description"] + " Updated schedule."
    assert repo.insert_job_with_state(changed) == (job_id, "updated")


def test_alerts_read_state(qa_app):
    repo = FreshJobsRepository()
    alert_id = repo.create_alert(None, "provider_error", "Provider failed", provider_key="mock")
    assert any(alert["id"] == alert_id for alert in repo.list_alerts())
    repo.mark_alert_read(alert_id)
    assert all(alert["id"] != alert_id for alert in repo.list_alerts())


def test_manual_import_rejects_private_or_local_urls():
    with pytest.raises(ValueError):
        build_manual_job({"title": "Driver", "company": "Local", "description": "Job", "apply_url": "http://127.0.0.1/job"})
    with pytest.raises(ValueError):
        build_manual_job({"title": "Driver", "company": "Local", "description": "Job", "apply_url": "http://localhost/job"})


def test_duplicate_detection_across_providers():
    jobs = [
        build_manual_job({"title": "CDL Driver", "company": "Carrier", "location": "Dallas", "description": "Job", "apply_url": "https://jobs.example.com/1"}),
        {
            **build_manual_job({"title": "CDL Driver", "company": "Carrier", "location": "Dallas", "description": "Job", "apply_url": "https://jobs.example.com/1"}),
            "source": "usajobs",
            "source_job_id": "different",
        },
    ]
    assert len(deduplicate_jobs(jobs)) == 1


def test_provider_settings_manual_import_and_phase1_routes_still_work(qa_app):
    client, _, _, _ = qa_app
    client_id = create_client(client, "Fresh Jobs Phase 2 QA")
    providers = client.get(f"/fresh-jobs/providers?client_id={client_id}")
    assert providers.status_code == 200
    assert "Provider settings" in providers.text

    imported = client.post(
        "/fresh-jobs/manual-import",
        data={
            "client_id": client_id,
            "title": "CDL Class A Driver",
            "company": "Manual Carrier",
            "location": "Dallas, TX",
            "apply_url": "https://jobs.example.com/manual-driver",
            "salary": "70000 - 85000",
            "description": "CDL Class A route delivery with DOT compliance and safe driving.",
        },
        follow_redirects=False,
    )
    assert imported.status_code == 303
    listing = client.get(f"/fresh-jobs?client_id={client_id}")
    assert "Manual Carrier" in listing.text
