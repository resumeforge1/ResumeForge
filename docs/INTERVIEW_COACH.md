# AI Interview Coach

ResumeForge `0.16.0-dev` adds a deterministic AI Interview Coach at `/interview-coach`.

## Architecture

The coach is implemented in `app/services/interview_coach_service.py`.

Data sources:

- saved client resume
- selected job description
- job title
- industry template
- skills and certifications
- existing match analysis

No OpenAI key or paid API is required.

## Interview Modes

Supported modes include General, Behavioral, Technical, Leadership, Manager, Customer Service, Sales, Warehouse, Healthcare, CDL Driver, Software Engineer, Finance, and Executive.

## Scoring

Answer Review scores:

- Confidence
- Specificity
- STAR completeness
- Keywords
- Length
- Clarity
- Overall

Each score is deterministic and deductions are shown. The coach checks for missing measurable results, weak action verbs, missing outcome, missing metrics, short/long answers, passive wording, and generic wording.

Interview Readiness formula:

- 30% resume readiness
- 20% application quality
- 35% answer quality
- 15% practice completion

## Exports

- Interview Questions TXT
- Interview Notes DOCX
- Interview Session Summary PDF

## Limitations

- No fabricated company information.
- No invented candidate experience.
- No paid APIs.
- No automatic applications.
- Follow-up emails are templates only and must be reviewed before use.
