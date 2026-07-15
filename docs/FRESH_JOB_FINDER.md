# Fresh Job Finder MVP

ResumeForge `0.10.0-dev` adds Phase 1 of Fresh Job Finder: a user-controlled job discovery workspace.

## Included

- Job preferences per client
- Candidate profile extraction from resume/intake data
- Modular job source provider interface
- Deterministic mock provider for local testing
- Freshness filtering
- Duplicate detection
- Transparent 0-100 match score breakdown
- Ranked job cards
- Save, dismiss, prepare application, and status tracking
- Review-only application package drafts

## Not Included

- No blind auto-apply
- No third-party submissions
- No CAPTCHA bypass
- No external credential storage
- No scraping of LinkedIn, Indeed, or other sites in ways that may violate terms
- No fabricated resume facts

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

Phase 1 adds additive tables:

- `job_search_profiles`
- `discovered_jobs`
- `job_matches`
- `saved_jobs`
- `application_packages`
- `job_search_runs`

## Recommended Next Phase

Add opt-in real providers with terms-safe integrations, manual import improvements, richer distance/location handling, and scheduled checks through a background worker.
