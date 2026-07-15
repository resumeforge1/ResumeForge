# Ownership Audit

ResumeForge Phase 8 treats data ownership as a security boundary. User-owned records must be scoped by the authenticated server-side session user, not browser-submitted form fields.

## User-Owned

- `clients`
- `client_versions`
- `client_notes`
- `application_tracker`
- `jd_analyses`
- `job_search_profiles`
- `discovered_jobs`
- `job_matches`
- `saved_jobs`
- `application_packages`
- `job_search_runs`
- `job_alerts`
- `provider_run_logs`
- `imported_jobs`
- `interview_prep_notes`
- `application_package_versions`
- `application_package_notes`
- `application_package_exports`
- `interview_coach_sessions`
- `interview_coach_answers`
- `interview_coach_exports`
- `user_preferences`
- `user_sessions`
- `password_reset_tokens`
- `login_audit_log`

## Global

- `job_providers`: provider catalog and health labels.
- `templates` on disk: shared template marketplace assets.
- `plugins` on disk: shared local plugin discovery assets.

## Configuration-Only

- `settings`: legacy single-row workspace branding/settings record retained for backward compatibility.
- `job_provider_settings`: provider configuration storage retained for future per-user/provider expansion.
- `job_schedule_settings`: scheduler configuration retained for future per-user scheduling expansion.
- `auth_migration_state`: one-time legacy data claim marker.

## Admin-Only

- First administrator creation happens through `/setup` when no users exist.
- Admin-only management screens are not implemented yet.

## Legacy Migration Strategy

1. Existing local records keep their original data and nullable `user_id` columns.
2. The first administrator account is created through first-run setup/registration.
3. `assign_legacy_data_to_admin` assigns unowned legacy records to that first administrator.
4. The claim is recorded in `auth_migration_state`.
5. Later startups and later user creation do not reassign already-claimed legacy records.

## Remaining Design Notes

- Legacy global workspace settings remain configuration-only for compatibility.
- OAuth identity linking is intentionally deferred.
- Email delivery for password resets is intentionally deferred.
