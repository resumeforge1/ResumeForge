# Career Dashboard

ResumeForge `0.12.0-dev` adds a Career Dashboard at `/`.

## Widgets

- Welcome header with quick actions
- ResumeForge internal resume readiness score
- Fresh jobs summary
- Saved jobs and alerts summary
- Application pipeline
- Recent match-score cards
- Listing-based salary insights
- Local career analytics
- Provider health summary

## Resume Readiness Methodology

The readiness score is local and transparent. It is not an official ATS score and does not compare the resume against a specific job.

Components:

- Contact information completeness
- Professional summary presence and length
- Work history completeness
- Education presence
- Skill count
- Certification count
- Measurable achievements already present
- Formatting readiness

ResumeForge never invents missing facts. Improvement prompts only ask the user to add facts if they already exist.

## Pipeline Statuses

The dashboard uses:

- Discovered
- Saved
- Preparing
- Ready to Apply
- Applied
- Interview
- Offer
- Rejected
- Dismissed

Invalid statuses are rejected by repository validation.

## Empty States

The dashboard includes empty states for no resume, no jobs, no applications, no salary data, no analytics history, no alerts, and no configured real providers. Each empty state points to a safe next action.

## Limitations

- No blind auto-apply.
- No paid APIs.
- No external salary research.
- No fake company or candidate information.
- Analytics are based only on local ResumeForge records.
