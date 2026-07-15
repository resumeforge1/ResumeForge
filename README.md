# ResumeForge

ResumeForge is a full-stack resume workflow app for generating client resume packages from intake data and preparing user-reviewed job applications.

Current version: **0.16.0-dev**

It creates:

- ATS-friendly resume DOCX
- Premium styled resume PDF
- Cover letter DOCX
- Fresh job matches for review

## Tech Stack

- Python FastAPI
- Jinja2 templates
- SQLite
- python-docx for DOCX generation
- Playwright for HTML-to-PDF
- pypdf and python-docx for resume import extraction
- Simple HTML/CSS frontend

## Setup

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On first PDF generation, ResumeForge will install Playwright's Chromium browser automatically if it is not already present. To install it ahead of time, run:

```powershell
python -m playwright install chromium
```

Open the app at:

```text
http://127.0.0.1:8000
```

## Included Sample

The app includes sample intake data for Alfredo Cruz, a CDL Class A driver.

Use either:

- `Use Alfredo Sample` to prefill the intake form
- `Create Sample Client` to save the sample directly and open its preview

The source sample file is stored at:

```text
data/sample_alfredo_cruz_cdl.json
```

## Project Structure

```text
app/
  main.py                 FastAPI routes
  database.py             SQLite setup and client persistence
  document_generator.py   DOCX and PDF generation
  template_registry.py    Industry template discovery
  core/config.py          AI provider configuration
  repositories/           Repository layer for clients, settings, applications
  services/               Import, analysis, rewrite, plugin, and AI services
  sample_data.py          Built-in Alfredo Cruz sample
  templates/              App pages and resume templates
  static/                 Frontend CSS and JavaScript
data/
  resumeforge.sqlite3     Created automatically on first run
  ai_config.json          Created automatically for provider selection
  sample_alfredo_cruz_cdl.json
outputs/
  generated files
templates/
  cdl/template.json
  healthcare/template.json
  software/template.json
  finance/template.json
  warehouse/template.json
  sales/template.json
  executive/template.json
plugins/
  optional plugin folders with plugin.json manifests
tests/
  service tests
```

## Workflow

1. Open the home page.
2. Start a new intake or load the Alfredo Cruz sample.
3. Save the intake.
4. Review the resume preview.
5. Generate and download the DOCX/PDF package.

No authentication or paid APIs are required for this MVP.

## Production-Ready Modules

ResumeForge now includes modular foundations for:

- AI import from PDF and DOCX resumes
- Job description analysis with ATS score, missing keywords, match percentage, and recommendations
- Guardrailed rewrite buttons that preserve employers, dates, and job titles
- CRM dashboard, search, duplicate, archive, delete, restore, notes, statuses, and version history
- Application tracker with company, position, salary, status, date applied, and notes
- Settings for accent color, fonts, header style, spacing, margins, section order, and branding
- Plugin discovery from `plugins/*/plugin.json`
- Provider abstraction for OpenAI, Anthropic, Gemini, Ollama, and mock provider
- Fresh Job Finder with deterministic mock provider, optional official API provider settings, manual imports, freshness filters, transparent match scoring, alerts, schedule settings, and review-only application drafts
- Career Dashboard with resume readiness scoring, job summaries, application pipeline, interview prep, listing-based salary insights, and local analytics
- AI Application Package Builder with review-only tailored resume drafts, cover letters, recruiter email, LinkedIn message, interview summary, ATS checklist, and package exports
- Phase 5 SaaS UI polish with modern navigation, responsive cards, notification banners, loading states, empty states, and an upgraded dashboard/application workspace
- AI Job Copilot with daily brief, opportunity feed, local resume/application coaching, follow-up tracker, momentum score, salary alerts, and activity timeline
- AI Interview Coach with deterministic question generation, STAR coaching, answer scoring, mock interview sessions, readiness scoring, cheat sheets, follow-up templates, and exports

## Fresh Job Finder

The Fresh Job Finder page at `/fresh-jobs` lets users:

- Store job preferences
- Extract a candidate profile from saved resume data
- Manually check deterministic mock jobs and enabled permitted providers
- Import a job posting manually with public URL validation
- Filter jobs by posting freshness
- Review transparent 0-100 match score breakdowns
- Save or dismiss jobs
- Prepare application drafts for review
- Manage providers, alerts, and scheduled-check settings at `/fresh-jobs/providers`

It does not scrape third-party job sites, bypass CAPTCHA, store external job-site credentials, submit applications, or auto-apply. USAJOBS support uses the official public API and remains disabled until `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` are configured.

## Career Dashboard

The dashboard at `/` ties together resume readiness, fresh jobs, saved jobs, applications, alerts, provider health, salary listing data, and local analytics. The ResumeForge readiness score is an internal completeness score based only on saved resume data; it is not an official ATS score.

Related pages:

- `/applications` for pipeline review and manual application entry
- `/interview-prep` for deterministic interview preparation prompts
- `/interview-coach` for mock interview sessions, answer review, and interview readiness scoring
- `/fresh-jobs/providers` for provider settings, schedule settings, and alerts
- `/copilot` for AI Job Copilot daily brief and review-first career actions

## Application Package Builder

The package workflow at `/application-package/{client_id}/{job_id}` creates editable, review-only drafts for a selected job. It uses the existing provider abstraction and defaults to deterministic mock output. ResumeForge does not submit applications and does not invent employers, dates, job titles, certifications, licenses, numbers, salaries, or candidate experience.

## Exports

Client packages can generate:

- ATS DOCX
- Premium DOCX
- Premium PDF
- Cover Letter DOCX
- References Sheet DOCX
- LinkedIn Profile DOCX
- Interview Questions DOCX
- Application Email TXT
- Complete ZIP Package

## AI Provider Config

Provider selection lives in:

```text
data/ai_config.json
```

Default:

```json
{
  "provider": "mock"
}
```

The mock provider is deterministic and does not call paid APIs. Provider adapters can be added behind `app/services/ai_providers.py` without changing routes or templates.

## Adding a New Template

ResumeForge uses modular industry template folders in the top-level `templates/` folder.

To add a new industry:

1. Create a folder, for example `templates/legal/`.
2. Add `templates/legal/template.json`.
2. Give it a unique `key`, display `label`, resume template path, experience heading, and preferred strengths.
3. Add a matching Jinja resume template under `app/templates/resumes/` if the layout should differ from the existing resume.

Example:

```json
{
  "key": "warehouse",
  "label": "Warehouse Associate",
  "resume_template": "resumes/general.html",
  "experience_heading": "Warehouse Experience",
  "core_strengths": [
    "Inventory Control",
    "Forklift Operation",
    "Order Picking",
    "Shipping and Receiving",
    "Safety Compliance",
    "Team Collaboration"
  ]
}
```

Restart the FastAPI server and the new template will appear on the intake page.

## Plugin Manifest Example

Create `plugins/my_plugin/plugin.json`:

```json
{
  "name": "My Industry Plugin",
  "description": "Adds custom keywords and prompt assets.",
  "industry_keywords": ["Keyword A", "Keyword B"],
  "ai_prompts": ["Improve summary using concise industry language."],
  "resume_templates": ["resumes/general.html"],
  "cover_letters": ["cover_letter_template"],
  "linkedin_templates": ["linkedin_template"],
  "interview_questions": ["Tell me about a relevant project."]
}
```

Plugins are discovered on the Template Marketplace page.

## Tests

```powershell
python -m pytest tests -q
```

The smoke suite covers blank intake, sample intake, PDF/DOCX import, preview, exports, ZIP package, CRM duplication/archive/restore, application tracker add/edit/delete, settings, template marketplace, plugin discovery, and mock AI rewrites.

## Troubleshooting

### `python` opens the Microsoft Store

Install Python from python.org or use the Python launcher:

```powershell
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload
```

### Playwright PDF export fails

ResumeForge first tries Playwright's bundled Chromium, then falls back to installed Chrome or Microsoft Edge on Windows. To install Chromium manually:

```powershell
python -m playwright install chromium
```

If a corporate certificate blocks the download, install Microsoft Edge or Chrome and rerun the export.

### Export returns an error page

The export route now returns a clear `Export failed` page for invalid export types or generation failures. Re-run the export after checking that the client exists and the output folder is writable.

### PDF/DOCX import extracts incomplete data

The import engine is deterministic and conservative. It extracts common resume structures but does not invent missing facts. Review the populated intake form before saving.

### Plugin does not appear

Each plugin needs a valid JSON manifest at:

```text
plugins/<plugin-name>/plugin.json
```

Invalid plugin JSON is skipped so the marketplace keeps loading.

### Database looks stale

The SQLite database lives at:

```text
data/resumeforge.sqlite3
```

The app runs additive migrations on startup. Restart `uvicorn` after pulling structural changes.

### Seed demo data

Use the dashboard `Seed Demo Data` button or POST:

```powershell
Invoke-WebRequest -Method Post http://127.0.0.1:8000/seed/demo
```
