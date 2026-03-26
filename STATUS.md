# STATUS

## Repo
- Branch in this workspace: `main`
- Product/runtime rollout truth still comes from the tracked docs and deployment history, not from branch name alone.
- Workspace path is environment-specific; use the current repo root instead of hardcoded absolute paths.
- Verify sync state before any future push or deploy.

## Latest Activity (2026-03-26)

### Basket Dump Mapping Root Cause — FOUND AND FIXED
- SSH + DB inspection confirmed `basket_dump_count = 0` root cause: Input 1 (physical wire) was mapped to `TARE`; `basket_dump` action was on Input 4 with nothing wired there.
- **Fix applied (no code change, no restart):** Settings > Buttons > Input 1 changed from `TARE (Net = 0)` → `Basket Dump Count`. Inputs 2–4 set to `None (Disabled)`. Auto-saved via web UI.
- `counted_events` table had 0 rows before fix. Next basket dump should write rows with `event_type='basket_dump'`, `source='opto'`, `source_channel=1`.

### Backend / Webhook Investigation — CLEAR
- Pi `job_completion_outbox` confirmed all webhooks are `status=sent`, `attempt_count=0`, `last_error=null`.
- Supabase `scale_completion_data` and `completed_jobs` both have data for all recent jobs.
- The "missing data" observed for jobs 1705706 and 1704575 was a **timing issue**: scale data arrives at `receive-scale-webhook` immediately; `completed_jobs` record isn't created/updated until the downstream FINSP scan occurs (can be hours later). The data was always there — just not yet linked.
- No code changes required on the backend for this issue.

### No Code Staged Yet
- The basket dump fix was a Settings UI change only. No Pi source files were modified.
- The next work (webhook payload update + debounce logic) will require code changes and staging.

## Previous Activity (2026-03-24)
- Opto input CH1 wired and verified for basket dump detection on PLP6
- Monitoring script live, capturing transition timestamps and durations
- See `docs/OPTO_INPUT_MONITORING.md` for full hardware/software details
- Two signal pulses per dump cycle confirmed

## Current Focus

### Next agent task — basket_dump pulse grouping (4-line fix in acquisition.py)
- `basket_dump_count` is already in the webhook payload end-to-end. The only problem: 2 physical opto pulses per dump → count is 2× reality without grouping.
- **Fix:** Add `self._last_basket_dump_s: float = -1e9` to `__init__`; add 30-second cooldown check at top of `basket_dump` branch in `_handle_button`. Suppress second pulse. No schema change. No webhook contract change.
- **File to edit:** `src/services/acquisition.py` — `__init__` (~line 204) and `_handle_button` (~line 2396)
- **Test:** Add case to `tests/test_counted_events.py` — two edges < 30s = 1 event
- **Stage:** `pscp -pw depor src/services/acquisition.py pi@172.16.190.25:/opt/loadcell-transmitter/src/services/acquisition.py`
- **Goes live:** Next approved-window restart of `loadcell-transmitter` (same restart activates the Mar 18 bundle)
- See TODO.md → "Next Code Task" for the exact code to write.

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

## Database Health — URGENT
- **Live DB: 4.9 GB** on Pi SD card. WAL file: 36 MB uncheckpointed.
- Root cause: `events` table (~420k rows, no retention policy) + `config_versions` (~16,937 rows, every auto-save appends full JSON)
- **Risk:** disk-full crash if left unaddressed
- **Fix:** Add pruning methods to `repo.py` + periodic maintenance call in acquisition loop. See TODO.md → "Database Maintenance" section.
- Do NOT `VACUUM` or mass-delete while service is running.

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
