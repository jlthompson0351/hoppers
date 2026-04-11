# Project Daily Log

<!-- 
  AI INSTRUCTIONS:
  1. "Current Context" is your source of truth for the project state. 
  2. When starting a session, read this section first.
  3. When ending a session, UPDATE this section and APPEND a new entry to "Log History".
-->

## 🟢 Current Context
<!-- AI_CONTEXT_START -->
<status>
Live Production - deployed on Pi 2026-04-11 02:28 UTC. Fill time detection fixed, zero artifact suppression active, fill outlier filtering live.
</status>

<current_goals>
- [ ] Monitor first real production cycles tomorrow — verify fill times are now 30–90+ seconds
- [ ] Audit Supabase efficiency calculations using clean post-fix data
- [ ] Rebuild job_efficiency report with accurate fill time + basket cycle data
- [ ] Fix re-zero always skipping (zero_target_lb = 0 but empty hopper weighs ~70 lbs) — needs Justin approval
- [ ] Create fresh full OS image backup after tonight's changes confirmed good
- [ ] Rotate webhook token after go-live validation window
- [x] Fix fill time detection: full_stability_s 0.4→5.0, empty_confirm_s 0.3→2.0 (2026-04-11)
- [x] Add dynamic fill threshold: full_pct_of_target=0.80 (80% of ERP set weight = full)
- [x] Fix zero operation inflating production totals: zero_artifact suppression (2026-04-11)
- [x] Add fill time outlier filtering: <30sec excluded from avg_hopper_load_time_ms (2026-04-11)
- [x] Add valid_fill_count + excluded_fill_count to webhook payload (2026-04-11)
- [x] Forensic audit of Pi SQLite DB — all tables, configs, event codes documented
- [x] Delete 7.2GB stale backup (app.sqlite3.backup-20260410-213849) — all data already in Supabase
- [x] Logged zero-offset-inflates-production-totals bug to TODO.md
- [x] Monitor first live production cycles (set weight -> fill -> trigger -> PLC stop -> dump)
- [x] Update HDMI UI layout (move Job Target to left, Zero/Tare data to right, add Settings button)
- [x] Persist job target set weight across restart/power cycle
- [x] Implement Job Target Signal Mode (webhook-driven PLC output)
- [x] Add dedicated Settings tab for Job Target Mode
- [x] Replace raw trigger signal input with PLC profile dropdown
- [x] Add webhook endpoints with token auth (POST /api/job/webhook, GET /api/job/status, POST /api/job/clear)
- [x] Add dashboard mode toggle and job status bar
- [x] Update webhook contract to external backend format (`event`, `jobId`, `machineKey`, `loadSize`, `idempotencyKey`, `timestamp`)
- [x] Add in-memory idempotency dedupe on `idempotencyKey`
- [x] Add HDMI "Job Target" display (Set Weight + Scale Weight)
- [x] Deploy updated code/templates to Pi and reboot
- [x] Configure Tailscale Funnel public endpoint (`https://hoppers.tail840434.ts.net/api/job/webhook`)
- [x] Validate external webhook test path end-to-end (public POST -> set_weight update)
- [x] Write unit + integration tests (test_target_signal_mode.py, test_api_job_webhook.py)
- [x] Verify mode isolation: toggling does not affect calibration, filter, zero, throughput settings
</current_goals>

<recent_decisions>
- 2026-04-11: full_stability_s raised to 5.0s (was 0.4s). Conveyor belt fill minimum is 30 sec in real world; 0.4s was triggering on first belt trickle.
- 2026-04-11: empty_confirm_s raised to 2.0s (was 0.3s). Physical dump cycle needs time to complete.
- 2026-04-11: Added full_pct_of_target=0.80 — hopper declared full when weight reaches 80% of ERP set weight. Handles variable job sizes correctly.
- 2026-04-11: Zero artifact suppression — manual zero now arms a 30-second window during which any completed cycle is tagged dump_type=zero_artifact and excluded from production_totals.
- 2026-04-11: Fill time outlier filtering — fill times <30sec excluded from avg_hopper_load_time_ms. valid_fill_count + excluded_fill_count now in webhook payload.
- 2026-04-11: Forensic Pi DB audit complete. 13 tables confirmed. DB path: /var/lib/loadcell-transmitter/data/app.sqlite3. Schema v8.
- 2026-04-11: Deleted 7.2GB stale backup (created by Talos during accidental DB wipe). All 239 webhooks were already sent to Supabase before wipe.
- Job Target Signal Mode: output is binary (0V or trigger voltage), not proportional. Scale tells PLC when to stop filling.
- Trigger signal value selected from PLC profile points dropdown (not a raw number input). Operator picks a known voltage/weight pair.
- Webhook contract switched to external backend format: `{event, jobId, machineKey, loadSize, idempotencyKey, timestamp}`.
- Webhook auth supports `X-API-Key` (primary), `Authorization` bearer/basic, and legacy `X-Scale-Token`.
- Target state is now persisted (`job_control.set_weight/active/meta/state_seq/updated_utc`) and restored after restart/power cycle.
- Mode toggle only writes job_control.mode and job_control.enabled -- no other config sections touched.
- Pretrigger offset for falling-weight compensation adjustable per-site in Settings.
- PLC behavior confirmed: above trigger voltage = stop upfeed, below = keep filling. Overshoot from in-flight material is acceptable.
- Keep `409` response when mode is legacy (intentional safety gate; backend retries handled upstream).
</recent_decisions>

<next_steps>
1. Run sustained real-time backend dispatch test with fresh idempotency keys
2. Verify PLC stop timing against set weight across multiple loads
3. Investigate/resolve mode auto-switch and startup persistence bug (tracked in `docs/TODO_BACKLOG.md`)
4. Tune pretrigger offset by material/fill speed profile
5. Rotate webhook token and confirm backend credential update
6. Create and verify a new full OS image backup with latest add-ons/fixes
</next_steps>
<!-- AI_CONTEXT_END -->

---

## 📜 Log History

### 2026-02-27
**Focus:** Job Target Set-Weight Persistence + Documentation Sync
- **Completed:**
  - Identified root cause for "waiting..." after restart: `_job_set_weight` lived in-memory only.
  - Implemented persistence in `src/services/acquisition.py`:
    - persist `job_control.set_weight`, `active`, `meta`, `state_seq`, `updated_utc` on webhook updates and clear;
    - restore persisted state during service startup before first loop tick.
  - Updated `src/app/routes.py` `/api/snapshot` to fall back to persisted `job_control` values when runtime snapshot keys are not yet populated.
  - Added regression tests:
    - `tests/test_target_signal_mode.py` restart restore + clear persistence checks
    - `tests/test_snapshot_job_control.py` persisted fallback check
  - Updated documentation: `README.md`, `docs/CURRENT_IMPLEMENTATION.md`, `docs/Architecture.md`, `docs/CURRENT_UI_REFERENCE.md`, `docs/TODO_BACKLOG.md`, `DAILY_LOG.md`.
- **Operational Constraint Honored:** No Pi/server restart performed while line is live.
- **Follow-up Added:** New TODO item to create a complete fresh OS image backup with all latest add-ons/fixes.

### 2026-02-27
**Focus:** v3.4 Live Deployment + External Webhook Go-Live
- **Completed:**
  - Deployed latest `src` files to Pi (`routes.py`, `acquisition.py`, `repo.py`, core modules, and templates) and rebooted device.
  - Brought up Tailscale on Pi and enabled Funnel (`https://hoppers.tail840434.ts.net`) for off-network webhook access.
  - Updated webhook contract implementation to accept:
    `{event, jobId, machineKey, loadSize, idempotencyKey, timestamp}`.
  - Added auth compatibility for `X-API-Key`, `Authorization` bearer/basic, and legacy `X-Scale-Token`.
  - Added in-memory idempotency dedupe using `idempotencyKey`.
  - Added HDMI Job Target visibility (Set Weight + current Scale Weight).
  - Validated external/public webhook path with live 200 responses and verified set weight updates in status/snapshot.
- **Known Follow-up:**
  - Legacy mode occasionally flips back to target mode after manual switch (investigate).
  - Persist mode selection across startup/reboot reliably (tracked in `docs/TODO_BACKLOG.md`).

### 2026-02-27
**Focus:** Job Target Signal Mode - Implementation, Review, and Documentation
- **Completed:**
  - **Job Target Signal Mode:** Implemented webhook-driven PLC output mode. Scale receives target weight via `POST /api/job/webhook`, outputs 0V while below target, fires fixed trigger voltage when weight reaches threshold. PLC stops upfeed on trigger signal.
  - **Dedicated Settings Tab:** Added "Job Target Mode" tab in Settings with trigger timing (exact/early), pretrigger offset, trigger signal dropdown (populated from PLC profile points), low signal value, and webhook token.
  - **Dashboard Mode Toggle:** Added toggle strip (Legacy Weight Mapping / Job Target Mode) and job status bar showing set weight, scale weight, and signal on/off indicator.
  - **Trigger Signal Dropdown:** Replaced raw number input with dropdown populated from PLC profile points. Each option shows "X.XX V = PLC reads YYY lbs". If no points exist, directs operator to Calibration Hub.
  - **Webhook API:** 5 new endpoints (`/api/job/mode`, `/api/job/webhook`, `/api/job/status`, `/api/job/clear`, `/api/job/trigger/from-nudge`) with `X-Scale-Token` header auth.
  - **Tests:** 15 tests across `test_target_signal_mode.py` and `test_api_job_webhook.py` covering validation, auth, mode gating, threshold logic, and nudge capture.
  - **Isolation Verified:** Mode toggle only writes `job_control.mode` and `job_control.enabled`. No other config sections (calibration, filter, zero, throughput, deadband, ramp) are touched.
  - **Documentation Updated:** Architecture.md, CURRENT_IMPLEMENTATION.md, CURRENT_UI_REFERENCE.md, SRS.md, README.md, DAILY_LOG.md, deploy files.
- **Not Yet Deployed:** All changes are local. Needs deployment to Pi when line is down.

### 2026-02-26
**Focus:** Fix Throughput Overcounting (Spike Rejection)
- **Completed:**
  - **Identified Overcounting Issue:** The scale was recording impossible dump weights (e.g., 800+ lbs on a 300 lb machine). Found that zero drift was inflating the `prev_stable_lbs` reading *before* the dump, and the post-dump rezero was applying *after* the cycle was already saved to the database. Additionally, transient mechanical spikes were latching as the `full_lbs` peak.
  - **Code Fix (Local Only):** 
    - Added a hard plausibility guard in `src/services/acquisition.py` that rejects any throughput cycle where `processed_lbs > range.max_lb`.
    - Rejected cycles now emit a structured `THROUGHPUT_CYCLE_REJECTED_MAX_WEIGHT` anomaly event with full mV and offset diagnostic details instead of writing to totals.
    - Wired `range.max_lb` to be editable from the Settings page UI (`src/app/templates/settings.html` and `src/app/routes.py`).
  - **Testing:** Added `tests/test_throughput_guard.py` to verify cycles > max are rejected and anomaly logs are emitted. All tests pass locally.
- **Decisions:**
  - Forward-only fix: We are not retroactively recalculating historical database totals.
  - Use `range.max_lb` as the authoritative physical limit of the machine.
- **Blockers / Pending:**
  - **Code is NOT deployed to the Pi yet.** The machine is currently running a live shift. The next agent needs to deploy `src/services/acquisition.py`, `src/app/routes.py`, and `src/app/templates/settings.html` when the line is down and it's safe to reboot the service.

### 2026-02-23
**Focus:** Fix App Crash & Re-deploy
- **Completed:**
  - **Identified Crash:** Found the `loadcell-transmitter` service looping in a crash due to a `NameError: name 'cal_zero_sig' is not defined` inside `src/app/routes.py` (line 1520).
  - **Code Fix:** Replaced undefined `cal_zero_sig` with `cal_target_sig` which is the correct variable returned by the `compute_zero_offset` function in the `api_zero` endpoint.
  - **Deployed:** Pushed the fix to the Pi via SSH and restarted the service successfully.

### 2026-02-18
**Focus:** v3.2 Deployment + PLC Profile Fix + Filter Tuning
- **Completed:**
  - **Code Deploy:** 13 files updated on Pi (routes, acquisition, repo, zero_tracking, zeroing, filtering, output_writer, schema, 5 templates)
  - **PLC Profile Diagnosis:** Found mid-session PLC zero change on Feb 16 created 5x slope kink between 36-51 lbs. Old 1 lb and 10 lb points had wrong PLC zero bias (~0.1V vs correct ~0.42V).
  - **PLC Profile Fix:** Updated 2 bad points, added 3 real nudge measurements (100/200/250 lbs). Final: 10 clean points, straight 0.00503 V/lb line from 1-250 lbs.
  - **PLC Formula Verified:** voltage = 0.412 + (weight x 0.00503). Tested at 100/200/250 lbs — within 0.007V.
  - **Kalman Filter Tuned:** Q=7/R=100 → Q=25/R=25. Reduces PLC output lag from ~1.7 lb to ~0.3 lb at 10 lbs/sec fill rate. Fixes hopper overfill issue.
  - **Calibration Retrained (partial):** 5 new clean points (1-150 lbs) in 5-min pass. Full retrain scheduled for tomorrow.
  - **Pre-retrain data saved:** `docs/pre_retrain_backup_2026-02-18.md`
- **Decisions:**
  - PLC profile: always start at 1 lb floor, never 0V/0lb
  - Kalman Q=25/R=25 for faster fill tracking
  - Zero tracking + Smart Zero Clear to enable after full calibration retrain
- **Blockers:** Calibration retrain still needed (scheduled Feb 18/19).

### 2026-01-31
**Focus:** System Initialization
- **Completed:**
  - **Logging System:** Initialized `DAILY_LOG.md` and `.cursor/rules/session-manager.mdc`.
- **Decisions:**
  - Adopted standard logging format.
- **Blockers:** None.
