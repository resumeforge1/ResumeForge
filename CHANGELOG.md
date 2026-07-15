# Changelog

## 0.10.0-dev - Unreleased

- Added Fresh Job Finder MVP for user-controlled job discovery and ranking.
- Added job preferences for target role, location, commute radius, remote preference, minimum salary, employment type, schedule, excluded companies, and required licenses/certifications.
- Added deterministic mock job provider behind a modular provider interface.
- Added candidate profile extraction from existing resume/intake data.
- Added freshness filters, duplicate detection, transparent 0-100 match scoring, and sorting by best match, newest, and highest salary.
- Added Fresh Jobs UI with ranked job cards, match breakdowns, matched skills, missing qualifications, save/dismiss actions, and prepare-application workflow.
- Added review-only application package drafts with tailored resume data, cover letter draft, and ATS keyword summary.
- Added additive SQLite tables for job search profiles, discovered jobs, job matches, saved jobs, application packages, and job search runs.
- Added deterministic regression tests for extraction, freshness filtering, deduplication, scoring, ranking, status tracking, package generation, and no invented candidate facts.

## 0.2.0 - 2026-07-08

- Added QA checklist and automated smoke test suite.
- Added demo data seeding workflow.
- Added application tracker edit and delete routes.
- Added user-facing export failure messages.
- Added plugin marketplace resilience tests.
- Added screenshots folder placeholder.
- Added troubleshooting documentation.

## 0.1.0

- Initial ResumeForge MVP with intake, preview, SQLite persistence, DOCX/PDF exports, sample CDL data, and modular template foundation.
