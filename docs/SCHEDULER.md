# Fresh Job Scheduler

ResumeForge `0.11.0-dev` stores schedule settings for recurring Fresh Job Finder checks.

## Current Behavior

- Users can save schedule settings at `/fresh-jobs/providers`.
- Supported intervals are hourly, every 3 hours, twice daily, and daily.
- Repository hooks prevent overlapping scheduled runs with a single `running` flag.
- Manual "Check for New Jobs" remains the primary execution path.

## Not Included Yet

- No background worker is required in Phase 2.
- No operating-system scheduled task is created automatically.
- No external job site credentials are stored.

## Future Worker Contract

A future worker can:

1. Read `job_schedule_settings`.
2. Skip when disabled or `running = 1`.
3. Call `begin_scheduled_run()`.
4. Execute enabled providers.
5. Save run logs and alerts.
6. Call `finish_scheduled_run()` with the next check time.

This keeps scheduled checks additive and avoids duplicate runs.
