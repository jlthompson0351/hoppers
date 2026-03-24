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

### What Still Needs Reality Check
- the exact production restart/activation moment that made the Mar 6 + Mar 16 runtime live
- whether basket-dump counts, floor-threshold behavior, and re-zero warning all behave correctly on the live line
- whether the Mar 18 HDMI tare removal and larger touch controls behave as expected after restart
- whether the new tare event logging clearly identifies the real source of any unexpected tare trigger
- whether the latest documented backup/baseline state matches what should be used for the next clone-image capture
- whether Hopper's current completed-job payload shape fully matches the next frontend machine-kiosk metrics brief

### What Was Confirmed Live
- On 2026-03-17, Pi DB inspection over Tailscale confirmed completed-job webhook/outbox runtime is live for `PLP6`.
- Outbox row `60` for job `1704584` was marked `sent` at `2026-03-17T23:08:27+00:00`.
- That live payload included `basket_dump_count` plus the expanded re-zero diagnostic fields.
- Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200` for all requests; 4 stored and 1 duplicate was ignored correctly.

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

### 2026-03-24 — Opto Input Basket Dump Monitoring (LIVE)
- Wired Sequent MegaInd opto input CH1 to basket rotation dump signal on PLP6
- **Critical wiring note:** VEX1 = positive (+24V), IN1 = negative — REVERSED from schematic
- Signal behavior: two HIGH pulses per dump cycle (rotate down → dump → rotate up → rotate down → dump again), each ~10-15s duration
- Two pulses within a short window = ONE actual basket dump
- Background monitoring script running on Pi at `/home/pi/monitor_in1.py`, logging to `/home/pi/basket_monitor.log`
- Argus also deployed an enhanced monitor at `/tmp/opto_monitor.py` with CSV logging
- Hardware edge detection enabled: `megaind 2 edgewr 1 3` (both rising + falling)
- Full details: `docs/OPTO_INPUT_MONITORING.md`
- **NOT YET** integrated into the main acquisition loop — standalone monitoring only
- **Next:** Analyze captured timing data, build debounce logic (2 transitions within ~30s = 1 dump), then integrate into acquisition service

### Next Recommended Step
1. Keep rollout truth current as more live observations come in.
2. While the line is in use, continue read-only verification and backend/doc alignment as needed.
3. During an approved production window, restart `loadcell-transmitter` once so the Mar 18 staged bundle becomes active.
4. Use `docs/APPROVED_WINDOW_CHECKLIST.md` to validate floor-threshold, basket-dump, re-zero-warning, HDMI tare removal, and tare-source tracing behavior on the real line.
5. After that validation, update the root coordination docs and deployment log again.
6. After rollout truth is confirmed, capture a fresh baseline bundle and a current cloneable image.
