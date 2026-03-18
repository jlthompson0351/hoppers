# TODO Backlog

## 2026-03-18 - HDMI tare removal, tare tracing, and touch-target update

- [x] Stage the Mar 18 no-restart hopper bundle on the Pi.
  - Copied updated runtime files into `/opt/loadcell-transmitter` over Tailscale without restarting `loadcell-transmitter`.
  - Scope staged:
    - smaller stable-drift capture for the between-jobs re-zero warning path
    - HDMI tare removal from the operator UI
    - tare-source tracing for web/API versus opto-triggered tare
    - enlarged HDMI bottom controls for `ZERO`, `CLEAR ZERO`, and `OVERRIDE`

- [ ] Restart and validate the Mar 18 staged bundle during the next approved window.
  - Restart `loadcell-transmitter` once.
  - Confirm HDMI no longer shows `TARE` / `CLEAR TARE`.
  - Confirm enlarged HDMI controls fit correctly and are easy to hit on the real 800x480 screen.
  - Confirm tare-related events now show enough source detail to distinguish web/API calls from opto input.
  - Re-check between-jobs re-zero warning behavior with the smaller stable-drift capture update active.

## 2026-03-17 - Live verification follow-up

- [x] Confirm completed-job webhook runtime is live on production.
  - Observed on production Pi over Tailscale: `job_completion_outbox` row `60` for `PLP6` job `1704584` was marked `sent` at `2026-03-17T23:08:27+00:00`.
  - The live payload included `basket_dump_count` and the expanded re-zero diagnostic fields.
  - Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200` for all requests; 4 stored and 1 duplicate was ignored.

- [ ] Validate remaining live runtime behavior on the real line.
  - Confirm a non-zero `basket_dump_count` case with mapped opto pulses.
  - Confirm configurable floor threshold / legacy floor signal behavior live.
  - Confirm a true between-jobs re-zero warning case where the warning latches and later clears after `ZERO`.

## 2026-03-16 - Between-jobs re-zero warning rollout

- [x] Implement non-blocking re-zero warning locally and stage it for later activation.
  - Goal: warn the operator to press `ZERO` between jobs only when the scale settles stable and remains outside the configured zero tolerance.
  - Added `scale.rezero_warning_threshold_lb` to Settings with a default of `20.0 lb`.
  - Acquisition now latches a between-jobs re-zero warning after a completed dump/cycle when the scale settles stable and stays outside tolerance.
  - Warning state is exposed in `/api/snapshot` and rendered on both `dashboard.html` and `hdmi.html`.
  - Completed-job webhook payload now includes `rezero_warning_seen`, `rezero_warning_reason`, `rezero_warning_weight_lbs`, `rezero_warning_threshold_lbs`, `post_dump_rezero_applied`, and `post_dump_rezero_last_apply_utc`.
  - No DB migration required for this change.

- [x] Confirm expanded re-zero diagnostic fields are present on the live completed-job payload.
  - Production payload for `PLP6` job `1704584` included:
    - `rezero_warning_seen`
    - `rezero_warning_reason`
    - `rezero_warning_weight_lbs`
    - `rezero_warning_threshold_lbs`
    - `post_dump_rezero_applied`
    - `post_dump_rezero_last_apply_utc`
  - In that observed case the warning-specific values were `false`/`null`, so a true warning-positive line case is still pending validation.

## 2026-03-06 - Configurable floor threshold handoff

- [x] Implement configurable floor threshold locally and stage it for later push.
  - Goal: replace the implicit legacy `3 lb` floor with an operator-editable setting.
  - Added `scale.zero_target_lb` to Settings so operators can set the floor per scale.
  - In Job Target Signal mode, operators can set the floor to `0.0 lb`.
  - Added `job_control.legacy_floor_signal_value` so Legacy Weight Mapping can hold a chosen PLC analog signal at or below the configured floor.
  - Legacy mode now sends the configured floor signal when `net_lbs <= zero_target_lb`, then resumes normal PLC profile mapping above the floor.
  - No DB migration required for this change.

- [ ] Validate floor-threshold behavior on the live line.
  - Runtime now appears active on production because the Mar 6 completed-job code path is live, but explicit floor-threshold behavior still needs direct validation.
  - Use `docs/APPROVED_WINDOW_CHECKLIST.md` during the approved window so floor-threshold, basket-dump, webhook, and re-zero validation stay in one flow.
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

- [x] Confirm completed-job webhook/outbox runtime is active on production.
  - Production Pi schema version is `7`; `job_lifecycle_state`, `job_completion_outbox`, and `counted_events` tables exist.
  - Live row `60` for `PLP6` job `1704584` was created and marked `sent` with `attempt_count = 0` and `last_error = null`.
  - Backend replay of the last 5 real Pi payloads succeeded with HTTP `200` responses.

## 2026-03-06 - Basket dump opto counting

- [x] Add basket dump opto input counting path.
  - Added a new opto action value: `basket_dump`.
  - Rising-edge opto pulses are stored as durable counted events instead of being mixed into hopper weight dump tables.
  - Completed-job payload builder now includes `basket_dump_count`.
  - Added regression tests: `tests/test_counted_events.py` and updated `tests/test_job_completion_webhook.py`.

- [ ] Validate live basket dump counting with mapped pulses.
  - `basket_dump_count` is present on the live payload now, but observed real jobs still showed `0`.
  - Use `docs/APPROVED_WINDOW_CHECKLIST.md` for the live counting and completed-job payload verification steps.
  - In Settings > Buttons, map the desired MegaIND opto input to `Basket Dump Count`.
  - Pulse the PLC signal and verify it counts once per rising edge.
  - Close a job transition and verify the completed-job webhook contains `basket_dump_count`.

## 2026-03-05 - Completed job webhook integration

- [x] Add completed-job lifecycle tracking and durable webhook outbox.
  - Added schema v6 migration for `record_time_set_utc`, `job_lifecycle_state`, and `job_completion_outbox`.
  - Added close-on-next-job behavior for normal job IDs with manual override attribution to active job windows.
  - Added retryable outbox delivery loop (no auth header by default, configurable URL + retry settings).
  - Added tests: `tests/test_job_completion_webhook.py`.

- [ ] Timezone correction window.
  - Pi currently reports timezone as `America/Kentucky/Louisville` (EST); target is `America/Chicago` (CST/CDT).
  - Change timezone during an approved production window if still needed.
  - Completed-job webhook delivery is already active on production; verify any local operational tooling expectations after the timezone change.

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
