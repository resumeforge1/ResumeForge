# Fresh Job Finder

ResumeForge `0.12.0-dev` includes Fresh Job Finder Phase 1 and Phase 2 plus Career Dashboard integrations: a user-controlled job discovery workspace with deterministic testing, optional permitted providers, manual imports, alerts, scheduled-check settings, dashboard summaries, and interview-prep handoff.

## Included

- Job preferences per client
- Candidate profile extraction from resume/intake data
- Modular job source provider interface
- Deterministic mock provider for local testing
- Optional USAJOBS provider adapter using the official API
- Provider status/settings page
- Manual job imports with public URL validation
- Freshness filtering
- Duplicate detection
- New/seen/updated/expired discovery state support
- Transparent 0-100 match score breakdown
- Ranked job cards
- Save, dismiss, prepare application, and status tracking
- In-app alerts with read state
- Schedule settings and overlap-prevention hooks
- Review-only application package drafts

## Not Included

- No blind auto-apply
- No third-party submissions
- No CAPTCHA bypass
- No external credential storage
- No scraping of LinkedIn, Indeed, or other sites in ways that may violate terms
- No fabricated resume facts
- No internet-dependent tests

## Job Preferences

Stored preferences include target role, location, commute radius, remote preference, minimum salary, employment type, preferred schedule, excluded companies, required licenses/certifications, and last checked timestamp.

## Candidate Profile

The profile is built from existing client data:

- Skills
- Job titles
- Years of experience
- Certifications
- Education
- Industries
- Location

## Freshness Filters

- Past 2 hours
- Today
- Past 24 hours
- Past 3 days
- Past 7 days

## Match Score

The score is based on skill match, title similarity, experience fit, certification fit, location/remote fit, salary fit, and posting freshness.

## Database Tables

Fresh Job Finder adds additive tables:

- `job_search_profiles`
- `discovered_jobs`
- `job_matches`
- `saved_jobs`
- `application_packages`
- `job_search_runs`
- `job_providers`
- `job_provider_settings`
- `job_alerts`
- `job_schedule_settings`
- `provider_run_logs`
- `imported_jobs`

## Provider Setup

See `docs/JOB_PROVIDER_SETUP.md`.

## Scheduler

See `docs/SCHEDULER.md`. Phase 2 stores schedule settings and prevents overlapping checks, but does not require a background worker yet.
