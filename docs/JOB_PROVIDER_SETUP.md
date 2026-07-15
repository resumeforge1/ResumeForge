# Job Provider Setup

ResumeForge Fresh Job Finder supports modular job providers. Providers discover jobs only; they do not submit applications.

## Included Providers

- `mock`: deterministic local provider for demos and tests. Enabled by default.
- `usajobs`: optional official USAJOBS API provider. Disabled until credentials are configured.
- `manual`: user-entered job postings through the provider settings page.

## USAJOBS

Set these environment variables before starting the server:

```powershell
$env:USAJOBS_API_KEY="your-api-key"
$env:USAJOBS_USER_AGENT="your-email@example.com"
py -3.12 -m uvicorn app.main:app --reload
```

If either variable is missing, ResumeForge marks the provider as `not_configured` and continues running with the mock provider.

## Safety Rules

- Do not scrape LinkedIn, Indeed, or other job boards in violation of their terms.
- Do not store third-party job-site credentials.
- Do not bypass CAPTCHA or access controls.
- Do not auto-apply or submit applications without the user.
- Manual import URLs must be public `http` or `https` URLs. Localhost, private IP, link-local, reserved, and `.local` hosts are rejected.

## Adding a Provider

Create a class with:

```python
name = "provider_key"
label = "Provider Label"

def health(self) -> dict:
    ...

def fetch_jobs(self, preferences: dict, candidate_profile: dict) -> list[dict]:
    ...
```

Normalize each job into the shared discovered-job fields: source, source job ID, company, title, location, description, posted date, discovered date, apply URL, salary range, employment type, schedule, and expiration status.
