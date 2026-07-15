# Authentication

ResumeForge Phase 8 adds a multi-user SaaS foundation while preserving the local-first workflows already in the application.

## Architecture

- `app/services/auth_service.py` owns password hashing, login verification, session creation, session validation, password-reset token creation, and profile preference persistence.
- `app/main.py` contains the route middleware that loads the current session, redirects anonymous users after accounts exist, applies security headers, and exposes login/register/logout/profile routes.
- Existing resume, job, package, copilot, and interview workflows remain review-first and deterministic unless a configured provider is added later.

## Password Security

Passwords are never stored in plain text. ResumeForge uses `bcrypt` with a unique random salt per password.

Passwords must be 8 to 128 characters and registration requires confirmation. Login errors are generic so they do not reveal whether an account exists.

## Session Flow

1. A user registers or logs in.
2. ResumeForge creates a cryptographically random session token and CSRF token.
3. Only the SHA-256 hash of the session token is stored in SQLite.
4. The session token is stored in an HTTP-only `rf_session` cookie.
4. The CSRF token is stored in a SameSite cookie for basic POST validation.
5. Normal sessions expire after 8 idle hours.
6. Sessions also have an absolute 30-day expiration.
7. Remember-me sessions expire after 30 days.
8. Logout revokes the session server-side and clears cookies.
9. Successful login rotates sessions by revoking existing active sessions for that user.

## CSRF Protection

State-changing form submissions require:

- The server-side session CSRF token.
- The SameSite CSRF cookie.
- A submitted `_csrf` form field or `X-CSRF-Token` header.

Comparison uses constant-time checks. Browser forms receive the token through lightweight JavaScript in `app/static/ui.js`.

## First Run

If no users exist, `/setup` displays the first-run setup wizard. The first created account is an administrator.

For compatibility with local QA and demo databases, the app remains usable before any user exists. Once a user exists, anonymous users are redirected to `/login`.

Legacy single-user records are not assumed to belong to whichever user logs in. During first administrator setup, ResumeForge assigns existing unowned records to that first administrator once and records the action in `auth_migration_state`. Repeated startups do not reassign legacy data.

## Database

The migration is additive and uses `CREATE TABLE IF NOT EXISTS` plus nullable `user_id` columns.

New tables:

- `users`
- `user_sessions`
- `password_reset_tokens`
- `user_preferences`
- `login_audit_log`
- `auth_migration_state`

User-associated data uses nullable `user_id` columns so existing single-user rows remain valid until first-admin legacy migration claims them. Reset tokens are also stored as hashes.

## Route Protection

After the first account exists, application routes require a valid session. Public routes are limited to static assets, health checks, login, registration, logout, forgot password, and setup.

Client, job, package, application, and interview session lookups are scoped to the active user. Unauthorized object access returns a not-found response.

Failed login attempts are written to `login_audit_log`. Five failures within 15 minutes trigger a temporary lockout.

## Future OAuth Support

OAuth is intentionally not included in Phase 8. Future providers can attach to the same `users` table by adding a linked identities table and provider-specific callback routes.

Planned future options:

- Google login
- Microsoft login
- GitHub login
- Email delivery for password reset
