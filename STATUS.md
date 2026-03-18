# STATUS

## Repo
- Branch in this workspace: `main`
- Product/runtime rollout truth still comes from the tracked docs and deployment history, not from branch name alone.
- Workspace path is environment-specific; use the current repo root instead of hardcoded absolute paths.
- Verify sync state before any future push or deploy.

## Current Focus
1. Keep the Mar 18 no-restart hopper bundle documented correctly across local, Pi-staged, and live runtime states.
2. Preserve the distinction between verified live completed-job webhook behavior and the remaining unvalidated hopper runtime behaviors.
3. Prepare for the next approved-window restart where the staged hopper updates will become live together.
4. Record Hopper's role in the next cross-project public machine-kiosk enhancement so Cursor/OpenClaw do not have to rediscover the data flow.

## Cross-Project Product Context
Hopper is the scale/runtime side of a three-project manufacturing system:
1. Hopper (scale runtime / job-target / completed-job webhook source)
2. Supabase backend/data layer
3. Frontend dashboards / kiosks / LUPE

Business direction is increasingly job-centric:
- ERP/job data defines the production context
- downtime overlays onto the run in Supabase
- Hopper contributes basket/set-weight/cycle/output/warning metrics for machine/job performance visibility
- the frontend machine kiosk is the next manager-facing surface being extended with those metrics

## Latest Known Product State
- The repo already contains the between-jobs re-zero warning rollout docs and tests.
- Earlier tracked work already includes:
  - configurable floor threshold
  - completed-job webhook/outbox support
  - basket-dump counted events
  - HDMI override and job-target workflow updates
- Additional 2026-03-18 work is now staged locally and on the Pi, but is not live until restart:
  - smaller stable-drift capture for the between-jobs re-zero warning path
  - tare-source tracing plus HDMI tare removal
  - larger HDMI touch controls (`ZERO`, `CLEAR ZERO`, `OVERRIDE`)

## Current Cleanup Pass
- Root coordination docs are being reconciled so they no longer contradict the actual workspace branch or rollout state.
- Duplicate/stale documentation entry points are being consolidated.
- Remote-ops guidance is being cleaned up so future Cursor/OpenClaw Pi access can follow the Desktop Commander-first rules.
- This cleanup should not overwrite or erase the already-staged hopper runtime updates that still need later rollout validation.

## Deploy Status
- Product/runtime work for the hopper updates is already documented in git and in the deployment log.
- Live Pi observation on 2026-03-17 confirmed completed-job webhook/outbox runtime is active for `PLP6`.
- Live completed-job payload for job `1704584` was marked `sent` and included `basket_dump_count` plus the expanded re-zero diagnostic fields.
- On 2026-03-18, an additional no-restart Pi staging pass copied:
  - the smaller-drift re-zero warning capture update
  - HDMI tare removal and tare-source tracing
  - the enlarged HDMI bottom control row
- Those Mar 18 files are staged on the Pi filesystem only and are not yet running live.
- Remaining live validation is still pending for:
  - a non-zero `basket_dump_count` case with mapped opto pulses
  - configurable floor threshold / legacy floor signal runtime behavior
  - a true between-jobs re-zero warning case where the warning latches and then clears
- After restart, validate that HDMI no longer exposes tare and that event logs clearly distinguish web/API tare triggers from opto-input tare triggers.
- Current cleanup work is documentation/process work; it should not be treated as live Pi activation.
- Current no-restart prep now includes a single approved-window checklist at `docs/APPROVED_WINDOW_CHECKLIST.md`.

## Current Blockers
- Need to document when the production runtime actually became live; current proof comes from Mar 17 observation rather than a logged restart event.
- Need remaining live validation for basket-dump pulses, floor-threshold behavior, and a true re-zero warning case.
- GitHub push is intentionally deferred unless explicitly approved
- Need a clean, consistent image-preparation runbook before the later clone-image workflow

## Next Steps
1. Keep backend and docs aligned while the line remains in use.
2. During the next approved window, restart `loadcell-transmitter` once so the Mar 18 staged runtime bundle becomes active.
3. Use `docs/APPROVED_WINDOW_CHECKLIST.md` to validate floor-threshold, basket-dump, re-zero-warning, and HDMI tare-removal behavior on the real line.
4. Confirm new tare event logs identify whether unexpected tare came from web/API calls or opto input.
5. After that validation, update `DEPLOY.md`, `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md`.
6. Record the eventual production restart/activation timing if it can be recovered from ops history.
7. After rollout truth is confirmed, capture a fresh baseline bundle and a current cloneable image.

## Working Rule
Git is the source of truth for implementation, repo docs are the source of truth for shared project state, and the running Pi is the source of truth for what is actually live.
