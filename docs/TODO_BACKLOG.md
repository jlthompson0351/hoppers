# TODO Backlog

## 2026-03-16 - Between-jobs re-zero warning rollout

- [x] Implement non-blocking re-zero warning locally and stage it for later activation.
  - Goal: warn the operator to press `ZERO` between jobs only when the scale settles stable and remains outside the configured zero tolerance.
  - Added `scale.rezero_warning_threshold_lb` to Settings with a default of `20.0 lb`.
  - Acquisition now latches a between-jobs re-zero warning after a completed dump/cycle when the scale settles stable and stays outside tolerance.
  - Warning state is exposed in `/api/snapshot` and rendered on both `dashboard.html` and `hdmi.html`.
  - Completed-job webhook payload now includes `rezero_warning_seen`, `rezero_warning_reason`, `rezero_warning_weight_lbs`, `rezero_warning_threshold_lbs`, `post_dump_rezero_applied`, and `post_dump_rezero_last_apply_utc`.
  - No DB migration required for this change.

- [ ] Activate staged re-zero warning during an approved restart window.
  - Runtime pieces can be copied to the production Pi while it is in use, but they will remain inactive until `loadcell-transmitter` is manually restarted.
  - Runtime files to stage on Pi:
    - `src/services/acquisition.py`
    - `src/app/routes.py`
    - `src/db/repo.py`
    - `src/app/templates/dashboard.html`
    - `src/app/templates/hdmi.html`
    - `src/app/templates/settings.html`
  - Local validation completed:
    - `python -m pytest tests/test_rezero_warning.py tests/test_job_completion_webhook.py tests/test_snapshot_job_control.py tests/test_api_zero.py`
    - Result: `20 passed`
    - Lint check on touched files: clean
  - After restart, verify:
    - warning only appears between jobs when stable zero-relative weight exceeds the configured threshold
    - warning clears after a successful manual `ZERO`
    - completed-job webhook includes the new re-zero warning diagnostic fields

## 2026-03-06 - Configurable floor threshold handoff

- [x] Implement configurable floor threshold locally and stage it for later push.
  - Goal: replace the implicit legacy `3 lb` floor with an operator-editable setting.
  - Added `scale.zero_target_lb` to Settings so operators can set the floor per scale.
  - In Job Target Signal mode, operators can set the floor to `0.0 lb`.
  - Added `job_control.legacy_floor_signal_value` so Legacy Weight Mapping can hold a chosen PLC analog signal at or below the configured floor.
  - Legacy mode now sends the configured floor signal when `net_lbs <= zero_target_lb`, then resumes normal PLC profile mapping above the floor.
  - No DB migration required for this change.

- [ ] Activate staged floor-threshold change during an approved restart window.
  - Runtime pieces of the floor-threshold work are now copied to the production Pi, but they are still inactive until `loadcell-transmitter` is manually restarted.
  - GitHub push is still optional and blocked unless explicitly approved.
  - Floor-threshold runtime files staged on Pi:
    - `src/app/routes.py`
    - `src/app/templates/settings.html`
    - `src/db/repo.py`
    - `src/services/acquisition.py`
  - Local-only validation/support files:
    - `tests/test_target_signal_mode.py`
    - `tests/test_throughput_guard.py`
    - `docs/CURRENT_IMPLEMENTATION.md`
    - `docs/CURRENT_UI_REFERENCE.md`
  - Important: some of those files also still contain separate unstaged edits in the working tree. Do not blindly `git add .` before commit, or unrelated webhook/basket-dump work may get mixed in.
  - Local verification already completed:
    - `python -m pytest tests/test_throughput_guard.py tests/test_target_signal_mode.py tests/test_api_zero.py`
    - Result: `28 passed`
    - Lint check on touched files: clean
  - Recommended handoff to push/deploy agent:
    - Review `git diff --cached` only, not the full working tree diff.
    - Commit only the staged floor-threshold changes.
    - Push to GitHub only when approved.
  - Restart service during the approved production window so the already-staged Pi files become active.
    - After rollout, verify in Settings that:
      - `Floor Threshold` is visible and persists
      - Job Target Signal mode accepts `0.0 lb`
      - Legacy mode floor signal holds the configured PLC output at/below the floor

## 2026-03-06 - Production staging status for webhook + basket dump changes

- [ ] Activate staged production changes with approved manual restart.
  - Runtime files for completed-job webhook support and basket dump opto counting have been copied to `/opt/loadcell-transmitter` on production Pi.
  - The running `loadcell-transmitter` process has NOT been restarted yet, so it is still using the old in-memory code.
  - The backend only shows prior manual test payloads because automatic completed-job generation will not begin until the updated service is restarted.
  - If deployment uses GitHub pull on the Pi, required steps are: commit changes, push to GitHub, pull/deploy on Pi, then restart service.
  - If deployment uses direct file copy from the local machine, GitHub push is optional, but Pi file sync and service restart are still required.
  - Runtime files already staged on Pi:
    - `src/services/acquisition.py` - job lifecycle tracking, payload build, outbox dispatch
    - `src/db/repo.py` - lifecycle state persistence, outbox queue methods, summary queries
  - `src/db/schema.py` - schema v6/v7 tables and indexes
  - `src/db/migrate.py` - schema v6/v7 migration logic
  - `src/app/templates/settings.html` - completed-job webhook URL setting and basket dump opto action
  - Primary docs for handoff:
    - `docs/JOB_COMPLETION_WEBHOOK_RUNBOOK.md`
    - `docs/SET_WEIGHT_PERSISTENCE_RUNBOOK.md`
    - `docs/DEPLOYMENT_LOG.md`
  - After restart, verify:
    - schema v6 and v7 migrations applied
    - `job_lifecycle_state` and `job_completion_outbox` tables exist
    - `counted_events` table exists
    - completed-job payload is generated on the next normal job transition
    - completed-job payload includes `basket_dump_count` when mapped opto pulses occur during the job window
    - outbound webhook reaches backend successfully

## 2026-03-06 - Basket dump opto counting

- [x] Add basket dump opto input counting path.
  - Added a new opto action value: `basket_dump`.
  - Rising-edge opto pulses are stored as durable counted events instead of being mixed into hopper weight dump tables.
  - Completed-job payload builder now includes `basket_dump_count`.
  - Added regression tests: `tests/test_counted_events.py` and updated `tests/test_job_completion_webhook.py`.

- [ ] Enable live production counting after manual restart.
  - Restart `loadcell-transmitter` during approved production window.
  - In Settings > Buttons, map the desired MegaIND opto input to `Basket Dump Count`.
  - Pulse the PLC signal and verify it counts once per rising edge.
  - Close a job transition and verify the completed-job webhook contains `basket_dump_count`.

## 2026-03-05 - Completed job webhook integration

- [x] Add completed-job lifecycle tracking and durable webhook outbox.
  - Added schema v6 migration for `record_time_set_utc`, `job_lifecycle_state`, and `job_completion_outbox`.
  - Added close-on-next-job behavior for normal job IDs with manual override attribution to active job windows.
  - Added retryable outbox delivery loop (no auth header by default, configurable URL + retry settings).
  - Added tests: `tests/test_job_completion_webhook.py`.

- [ ] Production rollout window for timezone + service restart.
  - Pi currently reports timezone as `America/Kentucky/Louisville` (EST); target is `America/Chicago` (CST/CDT).
  - Change timezone + restart service only during approved production window.
  - Verify webhook timestamps and delivery after rollout.

## 2026-02-27 - Post-live-test follow-ups

- [x] Persist Job Target set weight across restart/power cycle.
  - Root cause: `_job_set_weight` lived in-memory only, so startup defaulted to waiting/no active job.
  - Fix: persist `job_control.set_weight`/`active`/`meta` on webhook + clear, restore on service startup, and fall back to persisted values in `/api/snapshot`.
  - Added regression tests for restart restore + clear persistence + snapshot persisted fallback.

- [x] Add relational set-weight persistence + webhook audit tables.
  - Added SQLite `set_weight_current` (latest per line/machine) and append-only `set_weight_history`.
  - Persist full authenticated webhook JSON payload into `set_weight_history.metadata_json`.
  - Added runbook: `docs/SET_WEIGHT_PERSISTENCE_RUNBOOK.md`.

- [x] Add manager-only PIN-protected HDMI Override flow for job targets.
  - Replaced `SETTINGS` button with `OVERRIDE` on HDMI UI.
  - Added 4-digit PIN configuration to Settings > Job Target Mode.
  - Added `/api/job/override` endpoint that reuses `record_set_weight_receipt` to log overrides in `set_weight_history` with `manual_override:overridden:hdmi` source.

- [ ] Ensure mode persistence on startup/reboot.
  - Persist and honor selected `job_control.mode` and `job_control.enabled` exactly as last saved.
  - Confirm startup logic does not overwrite mode with defaults.
  - Add/expand regression tests for mode persistence across restart.

- [x] Investigate processing weight and dump counting regression.
  - Reported behavior: processing weight and dump counting are not working anymore.
  - Trace where processing weight is calculated and where dump counts are incremented/reset.
  - Add/expand regression tests to cover processing weight updates and dump counting.

- [x] Audit weight storage and dump detection logic.
  - Root cause: `ThroughputCycleDetector` emitted `full_lbs` from transient peak values, which inflated `prev_stable_lbs` and `processed_lbs` under vibration/spike conditions.
  - Fix: detector now reports the last stable pre-dump full reading (with fallback to prior behavior when no stable sample is available).
  - Fix: post-dump telemetry now continues after one-shot apply until fill resumes, so `time_to_fill_resume_s` is populated and logged.
  - Fix: added `target_set_weight_lbs` persistence on both `throughput_events` and `production_dumps` (schema v4 migration + acquisition/repo plumbing).
  - Added regression coverage for transient full spikes, post-dump fill-resume telemetry, and target-set-weight persistence.

- [ ] Create a new complete OS image backup with latest add-ons.
  - First confirm the repo/docs truth and later validate whether the Mar 5/6/16 staged runtime updates have been activated on the Pi.
  - Run a full post-change image backup from the actual desired production state.
  - Pair it with a fresh structured baseline pull so app/data/config recovery artifacts exist alongside the full image.
  - Label backup with date/version and store checksum + location for restore verification.
