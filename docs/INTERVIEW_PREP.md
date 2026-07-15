# Interview Prep

The Interview Prep page at `/interview-prep` creates deterministic preparation prompts from saved ResumeForge data.

## Inputs

- Selected client resume/intake data
- Saved or matched job title
- Job description when available
- Matched skills
- Missing qualifications
- Company name when available

## Output

- Likely interview questions
- Suggested talking points
- STAR-style planning prompts
- Skills to emphasize
- Possible concern areas
- Questions to ask the employer
- Interview checklist
- Saved notes

## Guardrails

Interview Prep does not invent:

- company facts
- candidate experience
- employers
- dates
- certifications
- education
- salary claims

Suggested answers are framed as prompts so the user supplies truthful examples.

## Notes

Notes are stored in `interview_prep_notes` by client and job. The table is additive and does not modify resume data.
