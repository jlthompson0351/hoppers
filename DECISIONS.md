# DECISIONS

## Workflow / Handoff

### 2026-03-16 — Root-doc handoff workflow is the repo standard
- This repo should use the same startup pattern as the Supabase repo.
- Root coordination files are now the standard entry point:
  - `README.md`
  - `OPENCLAW.md`
  - `TODO.md`
  - `STATUS.md`
  - `DECISIONS.md`
  - `RUNBOOK.md`
  - `DEPLOY.md`
  - `HANDOFF.md`
- Root `README.md` is the only startup README. Folder-level orientation docs should use names like `OVERVIEW.md` or `GUIDE.md`.
- Shared project state should live in git-tracked docs, not only in chat.

### 2026-03-16 — Shared branch should stay clean and simple
- Shared work in this repo should normally land on `main` unless Justin explicitly asks for something else.
- Stray local-only branches should not be left behind as implicit state.
- Agents must check the actual current branch instead of assuming from memory.

## Deployment / Operations

### Production safety is more important than rollout speed
- The hopper line may be in active production use.
- Do not reboot the Pi or restart `loadcell-transmitter` without an approved window.
- A file copy to `/opt/loadcell-transmitter` is only a staged change until the service is restarted and validated.
- Deployment reporting must keep these states separate: local, pushed, staged, live, validated.

### Current production base vs staged updates must stay explicit
- Job-target webhook cutover and HDMI target UI are already part of the known live baseline.
- Later changes from Mar 6 and Mar 16 are staged on disk and require a restart before they count as live.
- Repo docs must record that difference clearly so nobody overclaims rollout status.

## Product / Runtime

### Zero correction is canonical in mV, before calibration
- `zero_offset_mv` is the canonical zero-correction field.
- Zero is applied in the signal domain before calibration.
- `zero_offset_lbs` is derived/display-oriented, not the source of truth.
- This preserves calibration slope integrity and avoids lb/mV unit-mismatch bugs.

### The scale supports two distinct output modes
- `legacy_weight_mapping` and `target_signal_mode` are separate operating modes.
- Webhook-driven set-weight behavior must be treated as persisted, auditable runtime state.
- Changes to mode behavior, floor logic, or completed-job reporting should be documented in both rollout docs and repo handoff docs.

### Detailed implementation belongs under `docs/`
- The root README should stay focused on startup and handoff.
- Detailed hardware, calibration, UI, and deployment history belong in `docs/`.
- `docs/OVERVIEW.md` is the front door to the detailed docs set.
