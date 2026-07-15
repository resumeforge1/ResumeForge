# ResumeForge UI Guide

ResumeForge Phase 5 introduces a shared SaaS-style UI foundation.

## Design Tokens

Core colors and layout values live in `app/static/styles.css` under `:root`.

- `--bg`: page background
- `--surface`: cards and panels
- `--ink`: primary text
- `--muted`: secondary text
- `--line`: borders
- `--blue`: primary action color
- `--green`, `--gold`, `--orange`, `--red`: status colors
- `--radius`: card radius
- `--shadow`: elevated card shadow

Dark-mode-ready variables are defined under `[data-theme="dark"]`.

## Layout

- Use `.panel` for primary cards.
- Use `.grid.two` or `.grid.three` for responsive sections.
- Use `.metric-grid` and `.metric-card` for KPI dashboards.
- Use `.package-workspace` for two-column editor/sidebar layouts.

## Buttons

- `.button.primary`: main action
- `.button.secondary`: supportive navigation/action
- `.button.ghost`: low-emphasis action

Buttons automatically show a loading spinner during form submission through `app/static/ui.js`.

## Icons

Inline SVG symbols are defined in `base.html` and reused with `<use>`. This keeps the UI consistent without adding a heavy dependency.

## Notifications

The shared `.notice` component supports:

- `.success`
- `.info`
- `.warning`
- `.error`

Routes that pass `?message=` automatically show a success notification.

## Accessibility

- All controls keep visible focus states.
- Cards and charts use text summaries.
- Forms use labels.
- Motion is reduced when `prefers-reduced-motion` is enabled.

## Empty States

Use `.empty-state` with `.empty-icon`, a short explanation, and one useful action.
