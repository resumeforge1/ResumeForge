# AI Application Package Builder

ResumeForge `0.13.0-dev` adds a review-only Application Package Builder for selected jobs.

## Package Sections

Each package includes:

- Tailored Resume Draft
- Tailored Cover Letter
- ATS Keyword Checklist
- Missing Skills Analysis
- Resume Improvements
- Interview Preparation Summary
- Recruiter Email Draft
- LinkedIn Message Draft

All sections are editable before export.

## Match Analysis

ResumeForge compares the saved candidate resume with the selected job description and shows:

- match score
- score breakdown
- missing keywords
- strong matching skills
- weak areas
- certifications mentioned
- experience alignment
- education alignment

Every score uses existing transparent matching logic or deterministic local analysis.

## Guardrails

ResumeForge never invents candidate qualifications. The package builder does not change:

- employer names
- employment dates
- job titles
- certificates
- licenses
- numbers

Only wording is drafted for user review.

## Exports

Available exports:

- Resume DOCX
- Cover Letter DOCX
- Recruiter Email TXT
- LinkedIn Message TXT
- Interview Questions DOCX
- Complete ZIP Package

Exports are saved under `outputs/` and logged in `application_package_exports`.

## Database

Phase 4 adds additive tables:

- `application_package_versions`
- `application_package_notes`
- `application_package_exports`

No destructive migrations are used.

## Limitations

- No blind auto-apply.
- No third-party submission.
- No fake company research.
- No fabricated salary or resume facts.
- Mock provider output is deterministic unless a future provider adapter is configured.
