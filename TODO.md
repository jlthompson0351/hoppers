# TODO

## Current Cross-Project Feature Support
- [ ] Support the next public machine-kiosk enhancement across the linked manufacturing system.
- [ ] Confirm the completed-job webhook payload and downstream storage still expose the manager-facing metrics needed by the frontend kiosk:
  - [ ] average basket weight
  - [ ] set weight
  - [ ] average cycle time
  - [ ] weight drift warning
- [ ] Verify naming/units for the fields mirrored downstream into Supabase `completed_jobs`.
- [ ] Keep the distinction clear between Hopper as the scale/runtime source and Supabase as the broader backend/storage layer.

## Data / Product Alignment
- [ ] Document Hopper's role in the three-project chain: ERP/job context + machine set weight flow + scale completion output → Supabase → Frontend kiosk/dashboard views.
- [ ] Confirm what Hopper emits or derives for:
  - [ ] average basket weight
  - [ ] final set weight
  - [ ] final set weight unit
  - [ ] average cycle time
  - [ ] basket dump count
  - [ ] weight drift warning / severity / drift amount
- [ ] Note any gaps between what Hopper currently emits and what the frontend wants to display.

## Operational Reminder
- [ ] Do not blur pushed code with staged-on-Pi or live runtime state.
- [ ] Preserve current rollout truth while documenting the next frontend-linked feature work.

- [ ] **Feature: Basket Dump Webhook Integration** (Added: 2026-03-24)
  - Context: We are now counting "basket dumps" via the Pi (IN1 signal). At the end of a job, the scale data sent via webhook needs to use these basket dumps instead of (or alongside) "hopper dumps".
  - Goal: Correlate the basket dump signal with the scale weight data to confirm which basket dumps were *actual* parts dumps versus noise.

## Current State (2026-03-26) — Ready for Webhook Rebuild

### What Was Done Today
- **Root cause found:** `basket_dump` was mapped to Input 4 in Settings; physical wire is on Input 1 (which was `TARE`). Every dump was silently firing a tare.
- **Fix applied (no code, no restart):** Settings > Buttons > Input 1 → `Basket Dump Count`. Inputs 2–4 → `None (Disabled)`. Auto-saved.
- **Backend confirmed healthy:** Pi outbox all `sent`, Supabase `scale_completion_data` + `completed_jobs` receiving correctly. "Missing data" on jobs 1705706/1704575 was a FINSP timing gap, not a send failure.
- **No code staged yet.** The next task requires code changes.

### Next Immediate Action — Verify Live Counting (read-only)
After the next basket dump on the line, run via SSH:
```
sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 "SELECT * FROM counted_events ORDER BY id DESC LIMIT 5;"
```
Expect rows with `event_type='basket_dump'`, `source='opto'`, `source_channel=1`.

### Next Code Task — basket_dump Pulse Grouping (ONE small change, then stage to Pi)

> **Context for the next agent:**
> - The webhook field `basket_dump_count` already exists end-to-end: `counted_events` table → `get_job_window_counted_events_summary()` in `repo.py` → `basket_dump_count` in the webhook payload builder (`acquisition.py` line ~414).
> - The Settings fix (2026-03-26) means Input 1 now correctly fires the `basket_dump` action on every rising opto edge.
> - **The only problem:** each physical basket dump produces **2 opto pulses** (~10–15s apart). Without grouping, `basket_dump_count` will be 2× the real dump count.
> - **The fix is 4 lines in `src/services/acquisition.py`.** No schema change. No webhook contract change. No repo.py change.

#### Step 1 — Verify live counting first (SSH, read-only)
```bash
sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 \
  "SELECT * FROM counted_events ORDER BY id DESC LIMIT 10;"
```
Expect rows with `event_type='basket_dump'`, `source='opto_input'`, `source_channel=1`.
If rows are there and count is 2× real dumps → confirmed, proceed to Step 2.
If no rows yet → line may be idle; check `events` table for `BUTTON_BASKET_DUMP_COUNTED` log entries.

#### Step 2 — Add 30-second cooldown in `src/services/acquisition.py`

**In `__init__` (around line 204, after `self._last_blocked_tare_log_s`):**
```python
self._last_basket_dump_s: float = -1e9   # cooldown: group double-pulse into one logical dump
```

**In `_handle_button`, replace the `basket_dump` branch (starts around line 2396):**
```python
elif action == "basket_dump":
    now = time.monotonic()
    if now - self._last_basket_dump_s < 30.0:
        log.debug("basket_dump suppressed (double-pulse cooldown)")
        return
    self._last_basket_dump_s = now
    line_id, machine_id = self._normalize_scope_ids(None, None)
    event_id = self.repo.record_counted_event(
        event_type="basket_dump",
        source="opto_input",
        source_channel=channel,
        line_id=line_id,
        machine_id=machine_id,
    )
    self.repo.log_event(
        level="INFO",
        code="BUTTON_BASKET_DUMP_COUNTED",
        message="Opto basket dump count recorded.",
        details={
            "event_id": event_id,
            "channel": channel,
            "line_id": line_id,
            "machine_id": machine_id,
        },
    )
```

#### Step 3 — Run tests
```bash
python -m pytest tests/test_counted_events.py tests/test_job_completion_webhook.py -v
```
Add a test to `tests/test_counted_events.py` that fires two `basket_dump` edges < 30s apart and confirms only 1 counted event is written.

#### Step 4 — Stage to Pi (NO restart)
```bash
pscp -pw depor src/services/acquisition.py pi@172.16.190.25:/opt/loadcell-transmitter/src/services/acquisition.py
```
The change becomes live on the next approved-window restart of `loadcell-transmitter`.

#### Step 5 — After restart, verify
```bash
sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 \
  "SELECT * FROM counted_events ORDER BY id DESC LIMIT 10;"
```
Confirm rows appear at ~1 per physical dump (not 2).

---

- [x] ~~Integrate opto CH1 basket dump signal into the main acquisition loop (`counted_events` table)~~ — mapping corrected in Settings 2026-03-26
- [x] ~~Throughput cycle detector threshold fix~~ — NOT NEEDED, already working
- [ ] **VERIFY FIRST:** Confirm `counted_events` rows appear after a live dump (Step 1 above)
- [ ] Add 30-second cooldown to `basket_dump` handler — group double-pulse into 1 logical event (Step 2)
- [ ] Test: new case in `test_counted_events.py` — two edges < 30s = 1 event (Step 3)
- [ ] Stage `acquisition.py` to Pi (Step 4)
- [ ] After restart: verify 1 row per dump in `counted_events` and non-zero `basket_dump_count` on next webhook (Step 5)
- [ ] Future (after above is verified): correlate opto dump with weight-curve drop for confirmed parts-dump vs empty-rotation detection

> **Mechanical Constraints to keep in mind (future work):**
> 1. **Double-Dump Shake** — handled by the 30s cooldown above
> 2. **Empty Startup Dumps** — baskets dump empty at order start; future: filter if no hopper fill preceded the dump
> 3. **Carousel FIFO Delay** — 2-basket carousel; hopper fill → paint → dump has an offset; future: queue to track which basket has parts
> 4. **Manual/Maintenance Dumps** — outside normal cycle; future: flag if dump occurs outside expected hopper-fill → carousel → dump window
  - **Mechanical Constraints to Handle:**
    1. **Double-Dump Shake**: The basket dumps twice rapidly to shake off stuck painted parts. The code must group these into a single "logical" dump event (debounce).
    2. **Empty Startup Dumps**: At the start of an order, the system dumps the baskets empty before the hopper drops any parts. We must filter these out.
    3. **Carousel FIFO Delay**: The system has a 2-basket carousel. Sequence: Hopper fills Basket 1 -> Carousel rotates Basket 1 into paint booth -> Hopper fills Basket 2 -> Basket 1 comes out and dumps onto conveyor. This means there is an offset between a hopper weight drop and the corresponding basket dump. The code needs a queue to track which basket has parts and which is empty.
    4. **Manual/Maintenance Dumps**: Maintenance may manually trigger a basket dump (empty or full) outside of normal operation. Examples:
       - Dumping an empty basket during troubleshooting.
       - Overfilled basket (hopper dropped too many parts, can't paint them) — maintenance manually dumps excess parts before resuming.
       - These are NOT production dumps and should be flagged or filtered. Possible detection: dump happens outside of the normal hopper-fill → carousel → paint → dump cycle, or the weight doesn't match expected hopper drop.

## Database Maintenance — URGENT (2026-03-26)

> **Live DB is 4.9 GB on the Pi SD card. WAL file is 36 MB uncheckpointed.**
> This will cause a disk-full crash if left unaddressed.

| Table | Rows | Issue |
|---|---|---|
| `events` | ~420,891 | Unbounded append-only log. No retention policy. Primary culprit. |
| `config_versions` | ~16,937 | Every Settings auto-save appends full JSON. Only latest row matters at runtime. |

### What needs to be built (in `src/db/repo.py` + acquisition loop)
- [ ] Add `prune_old_events(keep_days=30)` to `repo.py` — `DELETE FROM events WHERE ts < ?` with a cutoff timestamp
- [ ] Add `prune_config_versions(keep_last=50)` to `repo.py` — delete all but the most recent N rows
- [ ] Call both from acquisition loop on a slow timer (e.g. once per hour, not every tick)
- [ ] After pruning, run `PRAGMA wal_checkpoint(TRUNCATE)` to flush the WAL
- [ ] Add tests covering pruning behavior (correct rows deleted, newest preserved)
- [ ] Stage to Pi, activate at next approved-window restart
- [ ] After restart + pruning runs, schedule a `VACUUM` during an approved window to reclaim disk space

### What NOT to do
- Do NOT run `DELETE` or `VACUUM` manually against the live DB while the service is running
- Do NOT prune `job_completion_outbox`, `throughput_events`, `counted_events`, or `set_weight_history` — these are permanent production records

## Backlog (Consolidated from docs/TODO_BACKLOG.md)

### 2026-03-18 - HDMI tare removal, tare tracing, and touch-target update

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

### 2026-03-17 - Live verification follow-up

- [x] Confirm completed-job webhook runtime is live on production.
  - Observed on production Pi over Tailscale: `job_completion_outbox` row `60` for `PLP6` job `1704584` was marked `sent` at `2026-03-17T23:08:27+00:00`.
  - The live payload included `basket_dump_count` and the expanded re-zero diagnostic fields.
  - Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200` for all requests; 4 stored and 1 duplicate was ignored.

- [ ] Validate remaining live runtime behavior on the real line.
  - Confirm a non-zero `basket_dump_count` case with mapped opto pulses.
  - Confirm configurable floor threshold / legacy floor signal behavior live.
  - Confirm a true between-jobs re-zero warning case where the warning latches and later clears after `ZERO`.

### 2026-03-16 - Between-jobs re-zero warning rollout

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

### 2026-03-06 - Configurable floor threshold handoff

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

### 2026-03-06 - Production staging status for webhook + basket dump changes

- [x] Confirm completed-job webhook/outbox runtime is active on production.
  - Production Pi schema version is `7`; `job_lifecycle_state`, `job_completion_outbox`, and `counted_events` tables exist.
  - Live row `60` for `PLP6` job `1704584` was created and marked `sent` with `attempt_count = 0` and `last_error = null`.
  - Backend replay of the last 5 real Pi payloads succeeded with HTTP `200` responses.

### 2026-03-06 - Basket dump opto counting

- [x] Add basket dump opto input counting path.
  - Added a new opto action value: `basket_dump`.
  - Rising-edge opto pulses are stored as durable counted events instead of being mixed into hopper weight dump tables.
  - Completed-job payload builder now includes `basket_dump_count`.
  - Added regression tests: `tests/test_counted_events.py` and updated `tests/test_job_completion_webhook.py`.

- [ ] Validate live basket dump counting — mapping fix now live.
  - Input 1 is now mapped to `Basket Dump Count`. Physical wire confirmed on IN1.
  - **Watch:** next basket dump should write a row to `counted_events` with `event_type='basket_dump'`, `source='opto'`, `source_channel=1`.
  - **Watch:** next completed-job webhook should contain non-zero `basket_dump_count`.
  - Verify via SSH: `SELECT * FROM counted_events ORDER BY id DESC LIMIT 10;`

### 2026-03-05 - Completed job webhook integration

- [x] Add completed-job lifecycle tracking and durable webhook outbox.
  - Added schema v6 migration for `record_time_set_utc`, `job_lifecycle_state`, and `job_completion_outbox`.
  - Added close-on-next-job behavior for normal job IDs with manual override attribution to active job windows.
  - Added retryable outbox delivery loop (no auth header by default, configurable URL + retry settings).
  - Added tests: `tests/test_job_completion_webhook.py`.

- [ ] Timezone correction window.
  - Pi currently reports timezone as `America/Kentucky/Louisville` (EST); target is `America/Chicago` (CST/CDT).
  - Change timezone during an approved production window if still needed.
  - Completed-job webhook delivery is already active on production; verify any local operational tooling expectations after the timezone change.

### 2026-02-27 - Post-live-test follow-ups

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
