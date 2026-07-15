# AI Job Copilot

ResumeForge `0.15.0-dev` adds AI Job Copilot at `/copilot`.

## Purpose

Copilot turns local ResumeForge data into a review-first career assistant. It does not apply to jobs, scrape job boards, fabricate company data, or invent candidate experience.

## Included Sections

- Daily Job Brief
- Opportunity Feed
- Recommended Next Actions
- Resume Improvement Suggestions
- Application Priorities
- Interview Reminders
- Upcoming Follow-ups
- Salary Opportunity Alerts
- Career Momentum Score
- Activity Timeline

## Opportunity Feed

Opportunities are ranked using:

- match score
- salary signal from saved job listings
- posting freshness
- manual priority from saved/preparing/ready statuses
- distance placeholder when location data is unavailable

Labels:

- High Opportunity
- Medium Opportunity
- Low Opportunity

## Resume Coach

Resume Coach uses saved resume data and the internal readiness score. It may suggest:

- add measurable achievements when real numbers are available
- expand skills already supported by experience
- improve summary
- add certifications only if already earned

## Application Coach

Application Coach shows:

- applications needing follow-up
- applications ready to submit
- old saved jobs
- dismissed jobs

## Follow-up Tracker

Follow-ups are derived from saved application dates. ResumeForge suggests a seven-day follow-up window but does not send messages automatically.

## Career Momentum Score

Momentum is a local 0-100 score:

- 35% resume readiness
- 20% applications this month
- 20% high-match jobs
- 15% interview rate
- 10% offer rate

## Activity Timeline

Timeline events are built from local records:

- resume updated
- jobs discovered
- application prepared
- interview notes saved
- provider check completed

## Limitations

- No paid APIs required.
- No automatic applications.
- No third-party job submission.
- No scraping.
- No fabricated salary, company, job, or candidate data.
