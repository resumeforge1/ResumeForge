from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import load_ai_config
from app.core.version import get_version
from app.database import DB_PATH, get_connection, init_db, list_clients, save_client
from app.document_generator import OUTPUT_DIR, generate_output, generate_outputs, render_resume_html
from app.repositories.application_repository import ApplicationRepository
from app.repositories.application_package_repository import ApplicationPackageRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.fresh_jobs_repository import FreshJobsRepository
from app.repositories.settings_repository import SettingsRepository
from app.sample_data import SAMPLE_ALFREDO_CRUZ_CDL
from app.services.dashboard_service import (
    PIPELINE_STATUSES,
    career_dashboard,
    client_timeline,
    dashboard_stats,
    generate_interview_prep,
    generated_files_for_client,
    get_interview_notes,
    save_interview_notes,
)
from app.services.application_package_service import (
    PACKAGE_EXPORT_TYPES,
    build_application_package,
    export_application_package,
    package_from_form,
)
from app.services.fresh_jobs import (
    MockJobProvider,
    ProviderFailure,
    USAJobsProvider,
    build_manual_job,
    calculate_next_check_at,
    current_utc,
    deduplicate_jobs,
    extract_candidate_profile,
    filter_by_freshness,
    posting_age,
    prepare_application_package,
    score_job,
)
from app.services.import_engine import extract_resume
from app.services.job_analyzer import analyze_job_description
from app.services.plugin_service import discover_plugins
from app.services.rewrite_engine import improve_experience, improve_skills, improve_summary
from app.services.seed_data import seed_demo_data
from app.template_registry import list_template_configs


BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("resumeforge")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

app = FastAPI(title="ResumeForge")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
client_repo = ClientRepository()
application_repo = ApplicationRepository()
package_repo = ApplicationPackageRepository()
fresh_jobs_repo = FreshJobsRepository()
settings_repo = SettingsRepository()
job_provider = MockJobProvider()
job_providers = [job_provider, USAJobsProvider()]


@app.on_event("startup")
def startup() -> None:
    init_db()
    OUTPUT_DIR.mkdir(exist_ok=True)
    sync_job_providers()
    template_count = len(list_template_configs())
    ai_config = load_ai_config()
    logger.info("ResumeForge version: %s", get_version())
    logger.info("Database path: %s", DB_PATH)
    logger.info("Templates loaded: %s", template_count)
    logger.info("Mock AI provider active: %s", ai_config.get("provider") == "mock")


@app.get("/health")
def health() -> dict[str, Any]:
    database_ok = True
    database_error = None
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        database_ok = False
        database_error = str(exc)
    return {
        "status": "ok" if database_ok else "degraded",
        "version": get_version(),
        "database": {
            "ok": database_ok,
            "path": str(DB_PATH),
            "error": database_error,
        },
        "templates": {
            "count": len(list_template_configs()),
        },
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    query = request.query_params.get("q", "")
    clients = client_repo.search(query)
    selected_client = client_repo.get(int(clients[0]["id"])) if clients else None
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "clients": clients,
            "query": query,
            "sample": SAMPLE_ALFREDO_CRUZ_CDL,
            "industry_templates": list_template_configs(),
            "settings": settings_repo.get(),
            "stats": dashboard_stats(),
            "career": career_dashboard(selected_client),
            "pipeline_statuses": PIPELINE_STATUSES,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return home(request)


@app.get("/clients/new", response_class=HTMLResponse)
def new_client(request: Request, sample: bool = False) -> HTMLResponse:
    client = SAMPLE_ALFREDO_CRUZ_CDL if sample else empty_client()
    return templates.TemplateResponse(
        "intake.html",
        {
            "request": request,
            "client": client,
            "resume_html": render_resume_html(client),
            "industry_templates": list_template_configs(),
        },
    )


@app.post("/clients/import", response_class=HTMLResponse)
async def import_client_resume(request: Request, resume_file: UploadFile = File(...)) -> HTMLResponse:
    upload_dir = BASE_DIR / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(resume_file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Upload a PDF or DOCX resume.")
    path = upload_dir / f"import-{resume_file.filename}"
    path.write_bytes(await resume_file.read())
    client = extract_resume(path)
    return templates.TemplateResponse(
        "intake.html",
        {
            "request": request,
            "client": client,
            "resume_html": render_resume_html(client),
            "industry_templates": list_template_configs(),
        },
    )


@app.post("/clients", response_class=HTMLResponse)
async def create_client(request: Request) -> RedirectResponse:
    form = await request.form()
    data = parse_intake_form(form)
    if not data["full_name"]:
        raise HTTPException(status_code=400, detail="Full name is required.")
    client_id = save_client(data)
    return RedirectResponse(url=f"/clients/{client_id}/preview", status_code=303)


@app.post("/preview/live", response_class=HTMLResponse)
async def live_preview(request: Request) -> HTMLResponse:
    form = await request.form()
    client = parse_intake_form(form)
    client["full_name"] = client["full_name"] or "Client Name"
    client["target_role"] = client["target_role"] or "Target Role"
    return HTMLResponse(render_resume_html(client))


@app.post("/clients/sample")
def create_sample_client() -> RedirectResponse:
    client_id = save_client(SAMPLE_ALFREDO_CRUZ_CDL)
    return RedirectResponse(url=f"/clients/{client_id}/preview", status_code=303)


@app.post("/seed/demo")
def seed_demo() -> RedirectResponse:
    client_id = seed_demo_data()
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.get("/fresh-jobs", response_class=HTMLResponse)
def fresh_jobs_page(
    request: Request,
    client_id: int | None = None,
    freshness: str = "past_7_days",
    sort: str = "best_match",
    new_only: bool = False,
) -> HTMLResponse:
    sync_job_providers()
    client = client_repo.get(client_id) if client_id else first_available_client()
    if client is None:
        return templates.TemplateResponse(
            "fresh_jobs.html",
            {
                "request": request,
                "client": None,
                "clients": client_repo.search("", include_archived=True),
                "profile": None,
                "candidate_profile": None,
                "jobs": [],
                "freshness": freshness,
                "sort": sort,
                "new_only": new_only,
                "providers": provider_status_rows(),
                "alerts": fresh_jobs_repo.list_alerts(),
                "schedule": fresh_jobs_repo.get_schedule(),
                "message": "",
            },
        )
    profile = fresh_jobs_repo.get_profile(int(client["id"])) or default_job_search_profile(client)
    jobs = [enrich_fresh_job(job) for job in fresh_jobs_repo.list_matches(int(client["id"]), sort=sort)]
    jobs = filter_by_freshness(jobs, freshness)
    if new_only:
        jobs = [job for job in jobs if job.get("discovery_state") == "new"]
    return templates.TemplateResponse(
        "fresh_jobs.html",
        {
            "request": request,
            "client": client,
            "clients": client_repo.search("", include_archived=True),
            "profile": profile,
            "candidate_profile": extract_candidate_profile(client),
            "jobs": jobs,
            "freshness": freshness,
            "sort": sort,
            "new_only": new_only,
            "providers": provider_status_rows(),
            "alerts": fresh_jobs_repo.list_alerts(int(client["id"])),
            "schedule": fresh_jobs_repo.get_schedule(),
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/fresh-jobs/preferences")
async def save_fresh_job_preferences(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    client = require_client(client_id)
    fresh_jobs_repo.save_profile(client_id, parse_fresh_job_preferences(form, client))
    return RedirectResponse(url=f"/fresh-jobs?client_id={client_id}&message=Preferences saved", status_code=303)


@app.post("/fresh-jobs/check")
async def check_fresh_jobs(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    client = require_client(client_id)
    profile = fresh_jobs_repo.get_profile(client_id) or default_job_search_profile(client)
    candidate_profile = extract_candidate_profile(client)
    freshness = str(form.get("freshness", "past_7_days"))
    raw_jobs: list[dict[str, Any]] = []
    new_jobs = 0
    updated_jobs = 0
    error_count = 0
    sync_job_providers()
    enabled_providers = enabled_job_providers()
    for provider in enabled_providers:
        provider_jobs: list[dict[str, Any]] = []
        try:
            provider_jobs = provider.fetch_jobs(profile, candidate_profile)
            raw_jobs.extend(provider_jobs)
            fresh_jobs_repo.update_provider_status(provider.name, provider.health()["status"], "")
        except ProviderFailure as exc:
            error_count += 1
            fresh_jobs_repo.update_provider_status(provider.name, "error", str(exc))
            fresh_jobs_repo.create_alert(client_id, "provider_error", f"{provider.label} could not complete: {exc}", provider_key=provider.name)
        fresh_jobs_repo.log_provider_run(
            client_id,
            provider.name,
            "ok" if provider_jobs else ("not_configured" if provider.health()["status"] == "not_configured" else "empty"),
            jobs_found=len(provider_jobs),
            message=provider.health()["message"],
            finished_at=current_utc().isoformat(),
        )
    fresh_jobs = filter_by_freshness(deduplicate_jobs(raw_jobs), freshness)
    for job in fresh_jobs:
        job_id, state = fresh_jobs_repo.insert_job_with_state(job)
        if state == "new":
            new_jobs += 1
        elif state == "updated":
            updated_jobs += 1
        match = score_job(job, candidate_profile, profile)
        fresh_jobs_repo.save_match(client_id, job_id, match)
        if state == "new" and int(match.get("score", 0)) >= 75:
            fresh_jobs_repo.create_alert(client_id, "new_match", f"New strong match: {job.get('title')} at {job.get('company')}", job_id, job.get("source", ""))
    checked_at = current_utc().isoformat()
    fresh_jobs_repo.mark_checked(client_id, checked_at)
    fresh_jobs_repo.create_run(client_id, "multi", {"freshness": freshness, "providers": [provider.name for provider in enabled_providers]}, len(fresh_jobs), new_jobs, checked_at)
    return RedirectResponse(
        url=f"/fresh-jobs?client_id={client_id}&freshness={freshness}&message=Fresh jobs checked: {new_jobs} new, {updated_jobs} updated, {error_count} provider errors",
        status_code=303,
    )


@app.get("/fresh-jobs/providers", response_class=HTMLResponse)
def fresh_job_providers_page(request: Request, client_id: int | None = None) -> HTMLResponse:
    sync_job_providers()
    return templates.TemplateResponse(
        "fresh_job_providers.html",
        {
            "request": request,
            "client_id": client_id,
            "providers": provider_status_rows(),
            "alerts": fresh_jobs_repo.list_alerts(client_id, include_read=True),
            "schedule": fresh_jobs_repo.get_schedule(),
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/fresh-jobs/providers/{provider_key}/toggle")
async def toggle_fresh_job_provider(provider_key: str, request: Request) -> RedirectResponse:
    form = await request.form()
    fresh_jobs_repo.set_provider_enabled(provider_key, str(form.get("enabled", "0")) == "1")
    return RedirectResponse(url="/fresh-jobs/providers?message=Provider setting saved", status_code=303)


@app.post("/fresh-jobs/alerts/{alert_id}/read")
def mark_fresh_job_alert_read(alert_id: int) -> RedirectResponse:
    fresh_jobs_repo.mark_alert_read(alert_id)
    return RedirectResponse(url="/fresh-jobs/providers?message=Alert marked read", status_code=303)


@app.post("/fresh-jobs/schedule")
async def save_fresh_job_schedule(request: Request) -> RedirectResponse:
    form = await request.form()
    interval_key = str(form.get("interval_key", "daily"))
    fresh_jobs_repo.save_schedule(str(form.get("enabled", "0")) == "1", interval_key, calculate_next_check_at(interval_key))
    return RedirectResponse(url="/fresh-jobs/providers?message=Schedule saved", status_code=303)


@app.post("/fresh-jobs/manual-import")
async def import_manual_fresh_job(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    client = require_client(client_id)
    try:
        job = build_manual_job({key: str(value) for key, value in form.items()})
    except ValueError as exc:
        fresh_jobs_repo.create_alert(client_id, "manual_import_error", str(exc), provider_key="manual")
        return RedirectResponse(url=f"/fresh-jobs/providers?client_id={client_id}&message={exc}", status_code=303)
    job_id = fresh_jobs_repo.create_imported_job(client_id, job, source_url=job.get("apply_url", ""), salary=str(form.get("salary", "")))
    profile = fresh_jobs_repo.get_profile(client_id) or default_job_search_profile(client)
    fresh_jobs_repo.save_match(client_id, job_id, score_job(job, extract_candidate_profile(client), profile))
    fresh_jobs_repo.create_alert(client_id, "manual_import", f"Manual job imported: {job.get('title')} at {job.get('company')}", job_id, "manual")
    return RedirectResponse(url=f"/fresh-jobs?client_id={client_id}&message=Manual job imported", status_code=303)


@app.post("/fresh-jobs/{job_id}/status")
async def update_fresh_job_status(job_id: int, request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    require_client(client_id)
    status = str(form.get("status", "saved")).strip()
    fresh_jobs_repo.set_job_status(client_id, job_id, status)
    return RedirectResponse(url=f"/fresh-jobs?client_id={client_id}&message=Job {status}", status_code=303)


@app.post("/fresh-jobs/{job_id}/prepare")
async def prepare_fresh_job_application(job_id: int, request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    client = require_client(client_id)
    job = fresh_jobs_repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    match = score_job(job, extract_candidate_profile(client), fresh_jobs_repo.get_profile(client_id) or default_job_search_profile(client))
    package = prepare_application_package(client, job, match)
    fresh_jobs_repo.create_application_package(client_id, job_id, package)
    fresh_jobs_repo.set_job_status(client_id, job_id, "preparing")
    existing = package_repo.latest_for_job(client_id, job_id)
    if existing is None:
        package_repo.create_version(client_id, job_id, build_application_package(client, job, match), "draft")
    return RedirectResponse(url=f"/application-package/{client_id}/{job_id}", status_code=303)


@app.get("/fresh-jobs/{job_id}/package", response_class=HTMLResponse)
def fresh_job_package_page(request: Request, job_id: int, client_id: int) -> HTMLResponse:
    client = require_client(client_id)
    job = fresh_jobs_repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    package = fresh_jobs_repo.package_for_job(client_id, job_id)
    return templates.TemplateResponse(
        "fresh_job_package.html",
        {
            "request": request,
            "client": client,
            "job": job,
            "package": package,
            "status": fresh_jobs_repo.get_saved_status(client_id, job_id),
        },
    )


@app.get("/application-package/{client_id}/{job_id}", response_class=HTMLResponse)
def application_package_page(request: Request, client_id: int, job_id: int) -> HTMLResponse:
    client = require_client(client_id)
    job = fresh_jobs_repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    package_version = package_repo.latest_for_job(client_id, job_id)
    if package_version is None:
        package_id = package_repo.create_version(client_id, job_id, build_application_package(client, job, match_for_job(client_id, job_id)))
        package_version = package_repo.get_version(package_id)
    return templates.TemplateResponse(
        "application_package.html",
        {
            "request": request,
            "client": client,
            "job": job,
            "package_version": package_version,
            "package": package_version["package"] if package_version else {},
            "notes": package_repo.notes(int(package_version["id"])) if package_version else [],
            "export_types": PACKAGE_EXPORT_TYPES,
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/application-package/{client_id}/{job_id}/generate")
def generate_application_package_route(client_id: int, job_id: int) -> RedirectResponse:
    client = require_client(client_id)
    job = fresh_jobs_repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    package_repo.create_version(client_id, job_id, build_application_package(client, job, match_for_job(client_id, job_id)))
    fresh_jobs_repo.set_job_status(client_id, job_id, "preparing")
    return RedirectResponse(url=f"/application-package/{client_id}/{job_id}?message=Package generated", status_code=303)


@app.post("/application-package/{package_id}/save")
async def save_application_package_route(package_id: int, request: Request) -> RedirectResponse:
    package_version = package_repo.get_version(package_id)
    if package_version is None:
        raise HTTPException(status_code=404, detail="Package not found.")
    form = await request.form()
    updated = package_from_form(form, package_version["package"])
    status = str(form.get("status", "draft")).strip() or "draft"
    if status not in {"draft", "ready to send"}:
        raise HTTPException(status_code=400, detail="Invalid package status.")
    package_repo.save_version(package_id, updated, status)
    package_repo.add_note(package_id, str(form.get("note", "")))
    if status == "ready to send":
        fresh_jobs_repo.set_job_status(int(package_version["client_id"]), int(package_version["discovered_job_id"]), "ready to apply")
    return RedirectResponse(
        url=f"/application-package/{package_version['client_id']}/{package_version['discovered_job_id']}?message=Package saved",
        status_code=303,
    )


@app.post("/application-package/{package_id}/export/{export_type}")
def export_application_package_route(package_id: int, export_type: str) -> FileResponse:
    package_version = package_repo.get_version(package_id)
    if package_version is None:
        raise HTTPException(status_code=404, detail="Package not found.")
    try:
        filename = export_application_package(package_version, export_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    package_repo.record_export(package_id, export_type, filename)
    return download_file(filename)


@app.get("/applications", response_class=HTMLResponse)
def applications_page(request: Request, client_id: int | None = None) -> HTMLResponse:
    client = client_repo.get(client_id) if client_id else first_available_client()
    dashboard = career_dashboard(client)
    return templates.TemplateResponse(
        "applications.html",
        {
            "request": request,
            "client": client,
            "clients": client_repo.search("", include_archived=True),
            "pipeline": dashboard["pipeline"],
            "pipeline_statuses": PIPELINE_STATUSES,
        },
    )


@app.get("/interview-prep", response_class=HTMLResponse)
def interview_prep_page(request: Request, client_id: int | None = None, job_id: int | None = None) -> HTMLResponse:
    client = client_repo.get(client_id) if client_id else first_available_client()
    if client is None:
        prep = generate_interview_prep({}, None)
        notes = ""
        job = None
        match = None
    else:
        job = fresh_jobs_repo.get_job(job_id) if job_id else first_preppable_job(int(client["id"]))
        job_id = int(job["id"]) if job else None
        match = match_for_job(int(client["id"]), job_id) if job_id else None
        prep = generate_interview_prep(client, job, match)
        notes = get_interview_notes(int(client["id"]), job_id)
    return templates.TemplateResponse(
        "interview_prep.html",
        {
            "request": request,
            "client": client,
            "clients": client_repo.search("", include_archived=True),
            "job": job,
            "match": match,
            "prep": prep,
            "notes": notes,
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/interview-prep/notes")
async def save_interview_prep_notes(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = int(form.get("client_id", 0))
    require_client(client_id)
    raw_job_id = str(form.get("job_id", "")).strip()
    job_id = int(raw_job_id) if raw_job_id else None
    save_interview_notes(client_id, job_id, str(form.get("notes", "")))
    target = f"/interview-prep?client_id={client_id}"
    if job_id:
        target += f"&job_id={job_id}"
    return RedirectResponse(url=f"{target}&message=Notes saved", status_code=303)


@app.get("/clients/{client_id}", response_class=HTMLResponse)
def client_detail(request: Request, client_id: int) -> HTMLResponse:
    client = require_client(client_id)
    files = generated_files_for_client(client_id)
    return templates.TemplateResponse(
        "client_detail.html",
        {
            "request": request,
            "client": client,
            "notes": client_repo.notes(client_id),
            "versions": client_repo.versions(client_id),
            "applications": application_repo.list_for_client(client_id),
            "files": files,
            "timeline": client_timeline(client_id),
        },
    )


@app.post("/clients/{client_id}/notes")
async def add_client_note(client_id: int, request: Request) -> RedirectResponse:
    form = await request.form()
    client_repo.add_note(client_id, str(form.get("note", "")))
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.post("/clients/{client_id}/applications")
async def add_application(client_id: int, request: Request) -> RedirectResponse:
    form = await request.form()
    try:
        application_repo.create(client_id, {key: str(value) for key, value in form.items()})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.post("/clients/{client_id}/applications/{application_id}/edit")
async def edit_application(client_id: int, application_id: int, request: Request) -> RedirectResponse:
    form = await request.form()
    try:
        application_repo.update(application_id, {key: str(value) for key, value in form.items()})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.post("/clients/{client_id}/applications/{application_id}/delete")
def delete_application(client_id: int, application_id: int) -> RedirectResponse:
    application_repo.delete(application_id)
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.post("/clients/{client_id}/duplicate")
def duplicate_client(client_id: int) -> RedirectResponse:
    new_id = client_repo.duplicate(client_id)
    return RedirectResponse(url=f"/clients/{new_id}/preview", status_code=303)


@app.post("/clients/{client_id}/archive")
def archive_client(client_id: int) -> RedirectResponse:
    client_repo.set_archived(client_id, True)
    return RedirectResponse(url="/", status_code=303)


@app.post("/clients/{client_id}/restore")
def restore_client(client_id: int) -> RedirectResponse:
    client_repo.restore(client_id)
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)


@app.post("/clients/{client_id}/delete")
def delete_client(client_id: int) -> RedirectResponse:
    client_repo.soft_delete(client_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/clients/{client_id}/preview", response_class=HTMLResponse)
def preview_client(request: Request, client_id: int) -> HTMLResponse:
    client = require_client(client_id)
    resume_html = render_resume_html(client)
    template_previews = []
    for template_config in list_template_configs():
        preview_client_data = dict(client)
        preview_client_data["template_key"] = template_config["key"]
        template_previews.append(
            {
                "key": template_config["key"],
                "label": template_config["label"],
                "html": render_resume_html(preview_client_data),
            }
        )
    return templates.TemplateResponse(
        "preview.html",
        {
            "request": request,
            "client": client,
            "resume_html": resume_html,
            "industry_templates": list_template_configs(),
            "template_previews": template_previews,
        },
    )


@app.post("/clients/{client_id}/analyze", response_class=HTMLResponse)
async def analyze_client_job(request: Request, client_id: int) -> HTMLResponse:
    client = require_client(client_id)
    form = await request.form()
    job_description = str(form.get("job_description", ""))
    result = analyze_job_description(job_description, client)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO jd_analyses (client_id, job_description, result) VALUES (?, ?, ?)",
            (client_id, job_description, json.dumps(result)),
        )
        conn.commit()
    return templates.TemplateResponse(
        "analysis.html",
        {"request": request, "client": client, "job_description": job_description, "result": result},
    )


@app.post("/clients/{client_id}/rewrite/{rewrite_type}")
def rewrite_client_section(client_id: int, rewrite_type: str) -> RedirectResponse:
    client = require_client(client_id)
    if rewrite_type == "summary":
        client["professional_summary"] = improve_summary(client)
    elif rewrite_type == "experience":
        client["work_experience"] = improve_experience(client)
    elif rewrite_type == "skills":
        client["skills"] = improve_skills(client)
    elif rewrite_type == "cover_letter":
        pass
    else:
        raise HTTPException(status_code=404, detail="Rewrite type not found.")
    client_repo.update(client_id, client, f"AI rewrite: {rewrite_type}")
    return RedirectResponse(url=f"/clients/{client_id}/preview", status_code=303)


@app.post("/clients/{client_id}/generate")
def generate_client_files(client_id: int) -> RedirectResponse:
    client = require_client(client_id)
    generate_outputs(client)
    return RedirectResponse(url=f"/clients/{client_id}/download", status_code=303)


@app.get("/clients/{client_id}/download", response_class=HTMLResponse)
def download_page(request: Request, client_id: int) -> HTMLResponse:
    client = require_client(client_id)
    files = generate_outputs(client)
    return templates.TemplateResponse(
        "download.html",
        {
            "request": request,
            "client": client,
            "files": files,
            "generated_files": generated_files_for_client(client_id),
        },
    )


@app.get("/clients/{client_id}/export/{export_type}")
def export_client_file(client_id: int, export_type: str) -> Response:
    client = require_client(client_id)
    try:
        filename = generate_output(client, export_type)
    except ValueError:
        return HTMLResponse("<h1>Export failed</h1><p>Export type not found.</p>", status_code=404)
    except Exception as exc:
        return HTMLResponse(
            f"<h1>Export failed</h1><p>{str(exc)}</p><p>Try again or check server logs.</p>",
            status_code=500,
        )
    return download_file(filename)


@app.get("/marketplace", response_class=HTMLResponse)
def marketplace(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "marketplace.html",
        {
            "request": request,
            "industry_templates": list_template_configs(),
            "plugins": discover_plugins(),
        },
    )


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("settings.html", {"request": request, "settings": settings_repo.get()})


@app.post("/settings")
async def update_settings(request: Request) -> RedirectResponse:
    form = await request.form()
    settings_repo.update({key: str(value) for key, value in form.items()})
    return RedirectResponse(url="/settings", status_code=303)


@app.get("/download/{filename}")
def download_file(filename: str) -> FileResponse:
    path = (OUTPUT_DIR / filename).resolve()
    if not path.exists() or path.parent != OUTPUT_DIR.resolve():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path, filename=filename)


def require_client(client_id: int) -> dict[str, Any]:
    client = client_repo.get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


def sync_job_providers() -> None:
    existing = {row["provider_key"]: row for row in fresh_jobs_repo.provider_rows()}
    for provider in job_providers:
        health = provider.health()
        if provider.name not in existing:
            fresh_jobs_repo.upsert_provider(
                provider.name,
                provider.label,
                provider.name == "mock",
                health["status"],
                "" if health["status"] != "error" else health["message"],
            )
        else:
            fresh_jobs_repo.update_provider_status(
                provider.name,
                health["status"],
                "" if health["status"] != "error" else health["message"],
            )


def provider_status_rows() -> list[dict[str, Any]]:
    sync_job_providers()
    provider_map = {provider.name: provider for provider in job_providers}
    rows = []
    for row in fresh_jobs_repo.provider_rows():
        provider = provider_map.get(row["provider_key"])
        health = provider.health() if provider else {"status": row.get("status", "unknown"), "message": ""}
        merged = dict(row)
        merged["label"] = row.get("label") or (provider.label if provider else row["provider_key"])
        merged["health_status"] = health.get("status", row.get("status", "unknown"))
        merged["health_message"] = health.get("message", "")
        rows.append(merged)
    return rows


def enabled_job_providers() -> list[Any]:
    rows = {row["provider_key"]: row for row in fresh_jobs_repo.provider_rows()}
    enabled = []
    for provider in job_providers:
        row = rows.get(provider.name)
        if row and int(row.get("enabled") or 0) == 1:
            enabled.append(provider)
    return enabled


def first_preppable_job(client_id: int) -> dict[str, Any] | None:
    jobs = fresh_jobs_repo.list_matches(client_id, sort="best_match")
    if jobs:
        return fresh_jobs_repo.get_job(int(jobs[0]["id"]))
    return None


def match_for_job(client_id: int, job_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT score, breakdown, matched_skills, missing_qualifications
            FROM job_matches
            WHERE client_id = ? AND discovered_job_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (client_id, job_id),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    for field, fallback in (("breakdown", {}), ("matched_skills", []), ("missing_qualifications", [])):
        try:
            data[field] = json.loads(data.get(field) or "")
        except json.JSONDecodeError:
            data[field] = fallback
    return data


def first_available_client() -> dict[str, Any] | None:
    clients = client_repo.search("", include_archived=True)
    if not clients:
        return None
    return client_repo.get(int(clients[0]["id"]))


def default_job_search_profile(client: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_id": client.get("id"),
        "target_role": client.get("target_role", ""),
        "location": client.get("city_state", ""),
        "commute_radius": 25,
        "remote_preference": "any",
        "minimum_salary": 0,
        "employment_type": "any",
        "preferred_schedule": "",
        "excluded_companies": [],
        "required_licenses_certifications": client.get("certifications", []) or [],
        "last_checked_at": "",
    }


def parse_fresh_job_preferences(form: Any, client: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_role": str(form.get("target_role", client.get("target_role", ""))).strip(),
        "location": str(form.get("location", client.get("city_state", ""))).strip(),
        "commute_radius": int(form.get("commute_radius") or 25),
        "remote_preference": str(form.get("remote_preference", "any")).strip(),
        "minimum_salary": int(form.get("minimum_salary") or 0),
        "employment_type": str(form.get("employment_type", "any")).strip(),
        "preferred_schedule": str(form.get("preferred_schedule", "")).strip(),
        "excluded_companies": split_inline_values(str(form.get("excluded_companies", ""))),
        "required_licenses_certifications": split_inline_values(str(form.get("required_licenses_certifications", ""))),
    }


def split_inline_values(value: str) -> list[str]:
    normalized = value.replace("|", "\n").replace(",", "\n")
    return [line.strip(" -\t") for line in normalized.splitlines() if line.strip(" -\t")]


def enrich_fresh_job(job: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(job)
    enriched["posting_age"] = posting_age(str(job.get("posted_at", "")))
    salary_min = job.get("salary_min") or 0
    salary_max = job.get("salary_max") or 0
    if salary_min and salary_max:
        enriched["salary_label"] = f"${int(salary_min):,} - ${int(salary_max):,}"
    elif salary_max:
        enriched["salary_label"] = f"Up to ${int(salary_max):,}"
    elif salary_min:
        enriched["salary_label"] = f"From ${int(salary_min):,}"
    else:
        enriched["salary_label"] = "Salary not listed"
    return enriched


def empty_client() -> dict[str, Any]:
    return {
        "template_key": "general",
        "full_name": "",
        "city_state": "",
        "phone": "",
        "email": "",
        "target_role": "",
        "professional_summary": "",
        "certifications": [""],
        "skills": [""],
        "work_experience": [
            {
                "employer": "",
                "job_title": "",
                "start_date": "",
                "end_date": "",
                "bullets": [""],
            }
        ],
        "education": [""],
        "status": "Draft",
        "notes": "",
    }


def parse_intake_form(form: Any) -> dict[str, Any]:
    work_experience = []
    employers = form.getlist("employer")
    job_titles = form.getlist("job_title")
    start_dates = form.getlist("start_date")
    end_dates = form.getlist("end_date")
    bullet_groups = form.getlist("bullets")

    for index, employer in enumerate(employers):
        bullets = split_lines(bullet_groups[index] if index < len(bullet_groups) else "")
        job = {
            "employer": employer.strip(),
            "job_title": value_at(job_titles, index),
            "start_date": value_at(start_dates, index),
            "end_date": value_at(end_dates, index),
            "bullets": bullets,
        }
        if any([job["employer"], job["job_title"], job["start_date"], job["end_date"], bullets]):
            work_experience.append(job)

    return {
        "template_key": form.get("template_key", "general"),
        "full_name": form.get("full_name", "").strip(),
        "city_state": form.get("city_state", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "target_role": form.get("target_role", "").strip(),
        "professional_summary": form.get("professional_summary", "").strip(),
        "certifications": split_lines(form.get("certifications", "")),
        "skills": split_lines(form.get("skills", "")),
        "work_experience": work_experience,
        "education": split_lines(form.get("education", "")),
        "status": form.get("status", "Draft"),
        "notes": form.get("notes", ""),
    }


def split_lines(value: str) -> list[str]:
    return [line.strip(" -\t") for line in value.splitlines() if line.strip(" -\t")]


def value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index].strip()
