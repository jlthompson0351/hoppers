# HANDOFF

## Current Handoff

### Repo State
- Repo path: use the current repo root; do not rely on machine-specific absolute paths
- Active branch in this workspace: `main`
- Current work now includes a Mar 18 staged runtime bundle on top of the cleanup/reconciliation pass over docs, runbooks, and handoff guidance.
- Treat the deployment docs as the source of truth for staged/live runtime state.

### What Exists In Git
- between-jobs re-zero warning work and rollout docs
- configurable floor threshold / legacy floor signal work
- completed-job webhook lifecycle + outbox support
- basket-dump counted events support
- HDMI override and job-target workflow updates
- smaller stable-drift capture for re-zero warning payload/reporting
- tare-source tracing plus HDMI tare removal
- enlarged HDMI bottom controls for `ZERO`, `CLEAR ZERO`, and `OVERRIDE`
- The deployment history for those changes already exists and should be preserved during cleanup.

### What This Cleanup Pass Is Doing
- Reconciling root coordination docs so they match the actual workspace branch and current project reality.
- Consolidating duplicate/stale documentation entry points.
- Cleaning up future agent-operating guidance for Pi access, staged rollout tracking, and image preparation.
- Capturing the latest no-restart Pi staging step so the next operator knows exactly what will become live after restart.
- Preserving the distinction between:
  - code/docs in git
  - anything pushed later
  - files already staged on the Pi
  - what is actually live after restart/validation

### What Was Confirmed Live

#### 2026-04-10 — machine_id Fix Confirmed
- `LCS_MACHINE_ID=PLP6` added to systemd service. Service restarted 2026-04-10 10:37 EDT.
- All new `counted_events` now write `machine_id='PLP6'`, matching the webhook query.
- Basket dump pipeline is end-to-end correct: opto IN1 → `basket_dump` action → `counted_events` → webhook `basket_dump_count`.
- No mapping mismatches remain. Full forensics in `CHANGELOG-PI-FIX-2026-04-10.md`.

#### 2026-03-26 — Button Mapping Fix Confirmed
- Input 1 mapped to `Basket Dump Count`. Inputs 2–4 disabled. Physical wire on IN1 confirmed.
- `counted_events` started writing rows after this fix.

#### 2026-03-17 — Webhook / Outbox Confirmed Live
- Pi DB inspection over Tailscale confirmed completed-job webhook/outbox runtime live for `PLP6`.
- Outbox row `60` for job `1704584` was marked `sent` at `2026-03-17T23:08:27+00:00`.
- That live payload included `basket_dump_count` plus the expanded re-zero diagnostic fields.
- Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200`; 4 stored and 1 duplicate ignored correctly.

### What Still Needs Reality Check
- the exact production restart/activation moment that made the Mar 6 + Mar 16 runtime live
- whether floor-threshold behavior and re-zero warning behave correctly on the live line (dump counts are now confirmed)
- whether the Mar 18 HDMI tare removal and larger touch controls behave as expected after restart
- whether the new tare event logging clearly identifies the real source of any unexpected tare trigger
- whether the latest documented backup/baseline state matches what should be used for the next clone-image capture
- whether Hopper's current completed-job payload shape fully matches the next frontend machine-kiosk metrics brief

### Cross-Project Frontend Brief
- The next planned frontend change is on the public per-machine kiosk page.
- Frontend wants to preserve the pinned active job card and add compact recent-completed-job cards below it.
- Hopper's role is to remain the upstream source/runtime for machine/job completion metrics such as:
  - average basket weight
  - final set weight
  - final set weight unit
  - average cycle time
  - basket dump count
  - explicit re-zero warning and post-dump re-zero diagnostics
- Supabase mirrors the relevant fields into `completed_jobs`, and the frontend will consume them from there.
- Keep this contract visible in repo docs so future agents do not treat Hopper as an isolated scale app.

### Current Shared Workflow
- Start with `README.md`, then read the coordination docs it points to
- Use git as source of truth for implementation and project docs
- Keep rollout reality explicit: local vs pushed vs staged vs live vs validated
- Do not lose or blur the already-staged hopper updates while cleaning docs
- Treat the repo itself as the shared project brain for handoff and continuity
- Treat the Mar 18 staged-on-Pi bundle as pending runtime activation until `loadcell-transmitter` is restarted

### 2026-04-10 — machine_id Mismatch Found and Fixed (CLOSED)
- `counted_events` used `machine_id='default_machine'`; webhook queried `machine_id='PLP6'` → returned 0 dumps.
- Fix: `Environment=LCS_MACHINE_ID=PLP6` added to systemd unit. Restarted 2026-04-10 10:37 EDT.
- Confirmed: new `counted_events` rows write `machine_id='PLP6'`. Pipeline is clean.
- Job 1706063 (Apr 9, 81 dumps) is the only job with lost records; not recoverable.

### 2026-03-26 — Basket Dump Root Cause Found and Fixed (CLOSED)
- SSH inspection of live Pi DB revealed: `opto_actions` had `basket_dump` on Input 4, but physical wire is on Input 1.
- Input 1 was mapped to `TARE` — every basket dump was silently firing a tare instead of incrementing the count.
- `counted_events` table had zero rows confirming no dump had ever been counted.
- **Fix applied:** Settings > Buttons > Input 1 → `Basket Dump Count`. Inputs 2–4 → `None (Disabled)`. Saved via web UI. No code change, no restart needed.
- Verified: `counted_events` rows now write correctly after opto pulses.

### 2026-03-26 — Backend / Supabase Webhook Confirmed Healthy
- Pi outbox fully healthy: all sent rows have `attempt_count=0`, `last_error=null`.
- Supabase `scale_completion_data` (168 rows) and `completed_jobs` both receiving and linking data correctly.
- `receive-scale-webhook` and `dispatch-scale-webhook` Edge Functions both returning HTTP 200.
- "Missing scale data" on jobs 1705706 and 1704575 was a **timing gap only**: scale webhook arrives at job end; `completed_jobs` isn't linked until the downstream FINSP scan runs (can be hours later). Data is present once FINSP occurs.
- No backend code changes needed for this issue.

### 2026-03-26 — Throughput Threshold Fix CLOSED (Not Needed)
- Live DB inspection via SSH confirmed `throughput_events` has **4,725 rows** and `job_completion_outbox` has **143 sent webhooks**.
- The cycle detector is working correctly at ~99% confidence. Thresholds (`full_min_lb: 15.0`, `empty_threshold_lb: 2.0`) are fine for real production loads.
- `HANDOFF-THRESHOLD-FIX.md` is now marked RESOLVED. Skip it.
- Real confirmed production weights: full ~240–270 lbs, empty ~0–2 lbs, avg cycle ~110s, typical job ~12 cycles / ~3,050 lbs.

### 2026-03-24 — Opto Input Basket Dump Monitoring (LIVE)
- Wired Sequent MegaInd opto input CH1 to basket rotation dump signal on PLP6
- **Critical wiring note:** VEX1 = positive (+24V), IN1 = negative — REVERSED from schematic
- Signal behavior: two HIGH pulses per dump cycle (rotate down → dump → rotate up → rotate down → dump again), each ~10-15s duration
- Two pulses within a short window = ONE actual basket dump
- Background monitoring script running on Pi at `/home/pi/monitor_in1.py`, logging to `/home/pi/basket_monitor.log`
- Hardware edge detection enabled: `megaind 2 edgewr 1 3` (both rising + falling)
- Full details: `docs/OPTO_INPUT_MONITORING.md`
- Raw pulses now counting in `counted_events` (after 2026-03-26 mapping fix). Debounce/correlation logic not yet built.

### 2026-04-10 — DB Maintenance Staged on Pi (PENDING RESTART)
- `run_maintenance()` added to `repo.py`: prunes 8 append-only tables (events, trends_total, trends_channels, throughput_events, production_dumps, counted_events, set_weight_history, sent outbox) older than `logging.retention_days` (default 7). Keeps last 50 config_versions. Checkpoints WAL.
- `_maybe_run_maintenance()` added to acquisition loop: runs once per hour. Logs `DB_MAINTENANCE` event with per-table row counts.
- 12 tests in `tests/test_db_maintenance.py`, all passing.
- **Staged on Pi** at `/opt/loadcell-transmitter` on 2026-04-10 12:37 EDT. **Not live until service restart.**
- After restart, first prune will remove anything older than 7 days from all target tables.
- **After the first prune runs**, schedule `VACUUM` during a downtime window to reclaim SD card space.

### 2026-04-10 — Full Production Audit Findings
- Audit found 25 issues across 5 areas. DB maintenance (above) addresses the most critical one.
- Other notable findings still open:
  - Blocking `urllib.request.urlopen()` in acquisition thread stalls DAQ during webhook dispatch
  - SSH password `depor` hardcoded in 10+ tracked files
  - No authentication on web UI or most API endpoints (accepted risk on closed LAN)
  - Repo systemd unit (`systemd/loadcell-transmitter.service`) doesn't match production Pi
  - Outbox retries have no max attempts / dead-letter
  - Swallowed `except Exception: pass` in opto polling (`_poll_buttons`)
- basket_dump 30s cooldown IS in the local repo working copy but NOT on the Pi yet. The `basket_cycle_count = raw // 2` in the payload builder is correct for current production (2 DB rows per physical dump). When cooldown is deployed, `// 2` must be removed.

### Next Recommended Steps

#### Current confirmed-good state (as of 2026-04-10)
- Opto IN1 wired and mapped to `Basket Dump Count`. No mismatch.
- `LCS_MACHINE_ID=PLP6` active in systemd. No mismatch.
- `counted_events` writing correctly. Backend healthy.
- DB maintenance staged, pending restart.

#### Primary task for the next agent — basket_dump pulse grouping
The webhook field `basket_dump_count` is flowing correctly end-to-end:
`counted_events` → `repo.get_job_window_counted_events_summary()` → `basket_dump_count` in `_build_completed_job_payload()` (`acquisition.py` ~line 414).

The only remaining problem: each physical dump fires **2 opto pulses** (~10–15s apart). Without grouping, the count is 2× the real dump count.

**The fix is 4 lines in `src/services/acquisition.py`. No schema change. No webhook contract change.**

1. Add `self._last_basket_dump_s: float = -1e9` to `__init__` (~line 204, after `_last_blocked_tare_log_s`)
2. In `_handle_button` at the `basket_dump` branch (~line 2396): add a 30-second cooldown check — if `time.monotonic() - self._last_basket_dump_s < 30.0`, log debug and `return`; otherwise set `self._last_basket_dump_s = now` then proceed with the existing `record_counted_event` call.

**See TODO.md → "Next Code Task" for the exact code block and full step-by-step.**

**Stage command (no restart needed — takes effect at next approved-window restart):**
```
pscp -pw depor src/services/acquisition.py pi@172.16.190.25:/opt/loadcell-transmitter/src/services/acquisition.py
```

#### After staging
1. During an approved production window, restart `loadcell-transmitter` once — activates the Mar 18 bundle AND the basket_dump cooldown together.
2. Use `docs/APPROVED_WINDOW_CHECKLIST.md` to validate floor-threshold, basket-dump, re-zero-warning, HDMI tare removal, and tare-source tracing.
3. After validation, capture a fresh baseline bundle and cloneable image.
# #   2 0 2 6 - 0 4 - 1 1      T h r o u g h p u t C y c l e D e t e c t o r   F i x   S t a g e d   ( P E N D I N G   R E S T A R T )  
 -   R e d u c e d   f u l l _ s t a b i l i t y _ s   d e f a u l t   f r o m   5 . 0   t o   1 . 5   t o   p r e v e n t   c y c l e   t i m e o u t s .  
 -   A d d e d   B A S K E T _ D U M P _ C Y C L E _ M I S M A T C H   d i a g n o s t i c   l o g   i n   a c q u i s i t i o n . p y .  
 -   S t a g e d   o n   P i   a t   / o p t / l o a d c e l l - t r a n s m i t t e r   o n   2 0 2 6 - 0 4 - 1 1   0 8 : 0 0   E D T .   N o t   l i v e   u n t i l   s e r v i c e   r e s t a r t .  
 