# Changelog

## 0.16.0-dev - Unreleased

- Added Phase 7 AI Interview Coach at `/interview-coach`.
- Added deterministic interview modes, question generation, STAR coaching, answer review scoring, live feedback, mock interview sessions, readiness scoring, cheat sheets, body language tips, and follow-up email templates.
- Added exports for interview questions TXT, interview notes DOCX, and interview session summary PDF.
- Added additive interview coach session, answer, and export tables.
- Added dashboard widgets for interview readiness, recent practice sessions, average interview score, and practice streak.

## 0.15.0-dev - Unreleased

- Added Phase 6 AI Job Copilot dashboard section and `/copilot` page.
- Added deterministic Daily Job Brief with jobs found today, high match jobs, saved jobs, applications waiting, and interviews scheduled.
- Added Opportunity Feed ranked by match score, salary signal, posting freshness, and manual priority.
- Added local Resume Coach, Application Coach, Follow-up Tracker, Salary Opportunity Alerts, Career Momentum Score, and Activity Timeline.
- Added dashboard widgets for upcoming interviews, recent follow-ups, high-match jobs, recent resume improvements, career momentum, and application velocity.
- Preserved review-first behavior with no automatic applications, scraping, paid API requirement, or fabricated candidate/company data.

## 0.14.0-dev - Unreleased

- Added Phase 5 SaaS UI/UX polish across the shared layout, dashboard, Fresh Jobs, Application Package, Interview Prep, and Settings pages.
- Added CSS design tokens, rounded cards, soft shadows, modern buttons, accessible focus states, responsive grids, light theme foundation, and future dark-mode variables.
- Added inline SVG icon system, sticky sidebar navigation, notification banners, loading button states, skeleton utility styles, improved empty states, and color-coded match score badges.
- Redesigned dashboard KPI cards, recent activity, package statistics, application pipeline, and local analytics chart cards.
- Redesigned Application Package Builder as a collapsible multi-section workspace with sticky export sidebar.
- Modernized Settings into grouped cards for Appearance, AI Provider, Job Providers, Export Settings, and Future Features.

## 0.13.0-dev - Unreleased

- Added Phase 4 AI Application Package Builder for selected fresh jobs.
- Added editable review-only package sections for tailored resume, cover letter, ATS keywords, missing skills, resume improvements, interview prep, recruiter email, and LinkedIn message.
- Added transparent match analysis with missing keywords, strong matching skills, weak areas, certifications, experience alignment, and education alignment.
- Added package exports for resume DOCX, cover letter DOCX, recruiter email TXT, LinkedIn message TXT, interview questions DOCX, and ZIP package.
- Added additive package version, note, and export tracking tables.
- Extended Career Dashboard with prepared applications, ready-to-send packages, average match score, recent packages, top improving resume, and export statistics.

## 0.12.0-dev - Unreleased

- Added Phase 3 AI Career Dashboard with SaaS-style homepage widgets and quick actions.
- Added internal resume readiness scoring with transparent component breakdown and improvement prompts.
- Added fresh-job summary, provider health, unread alerts, salary listing insights, and local analytics widgets.
- Added application pipeline page with safe status controls for saved jobs and manual application entry.
- Added deterministic Interview Prep page with questions, STAR prompts, focus areas, checklists, and saved notes.
- Added additive `interview_prep_notes` table for interview preparation notes.
- Added documentation for Career Dashboard, Interview Prep, and Career Analytics.

## 0.11.0-dev - Unreleased

- Added Phase 2 Fresh Job Finder provider settings with deterministic mock provider retained as the default.
- Added optional USAJOBS provider adapter using the official API and graceful missing-credential handling.
- Added manual job imports with public URL validation and SSRF protections for local/private addresses.
- Added schedule settings, overlap-prevention repository hooks, provider run logs, provider alerts, and read/unread alert state.
- Added new/seen/updated discovery state handling for fresh and changed postings.
- Added additive SQLite tables for job providers, provider settings, alerts, schedule settings, run logs, and imported jobs.
- Added documentation for permitted provider setup and scheduler behavior.

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
