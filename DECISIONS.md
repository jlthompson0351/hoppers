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
- Documentation cleanup must preserve that staged history instead of rewriting it as if it were already live.

### Disaster recovery and clone-image prep are related but not identical
- A baseline pull is the preferred app/data/config capture for recovery confidence and state scraping.
- A full image backup is the preferred artifact for building another scale from the same working system.
- Future runbooks should document both layers and the identity cleanup required after cloning to new hardware.

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

### Hopper is the scale/runtime repo in the linked manufacturing system
- Treat Hopper as the source/runtime layer for machine set-weight behavior, basket counting, and completed-job scale metrics.
- Supabase is the broader backend/storage layer; Frontend is the user-facing visualization layer.
- Repo docs should make that cross-project role explicit so future work can be coordinated across all three repos.

### Completed-job webhook metrics are now a cross-project contract
- Hopper-emitted completed-job metrics such as average basket weight, final set weight, average cycle time, basket dump count, and warning/drift fields feed downstream manufacturing visibility.
- Those fields should be considered part of a cross-project contract because the frontend kiosk and future job-performance views depend on them indirectly through Supabase.

### Detailed implementation belongs under `docs/`
- The root README should stay focused on startup and handoff.
- Detailed hardware, calibration, UI, and deployment history belong in `docs/`.
- `docs/OVERVIEW.md` is the front door to the detailed docs set.

## 2026-03-24: Basket Dump Cycle Understanding (CRITICAL CONTEXT)

### Physical Machine Layout
Each machine has a **carousel with TWO baskets** and a **hopper** above it.

### Full Production Cycle
1. Hopper descends → fills Basket A with parts from hopper
2. Hopper ascends
3. Carousel rotates → Basket A enters paint booth
4. Hopper descends → fills Basket B with parts
5. Hopper ascends, waits
6. Basket A exits paint booth onto carousel
7. Carousel spins → Basket A dumps painted parts onto conveyor belt
   - This is when the **opto signal fires** (two rotations = one dump)
8. Basket B enters paint booth
9. Cycle repeats

### Key Facts for Software
- **Dump happens AFTER paint**, not before — dumped parts were filled one cycle ago
- **Hopper fill and basket dump are offset by one cycle** — the basket dumping now was filled during the previous cycle
- **At startup**, baskets dump empty before any parts are loaded (dry dumps — must be ignored)
- **Two baskets per carousel** — so the rhythm is: fill A, paint A while fill B, dump A while paint B, fill A again...
- **Opto signal = basket physically rotating to dump** (two HIGH pulses per dump)
- **Hopper weight drop = parts leaving hopper into basket** (already tracked by scale)

### Correlation Strategy
To determine "this dump had real parts":
- Track hopper fills (weight drops from scale data) with timestamps
- Track opto dumps with timestamps  
- A dump is "real" (has parts) if there was a corresponding hopper fill approximately one cycle ago
- First dumps after job start with no prior fill = dry/empty dumps → don't count
- The hopper fill weight tells us how much went INTO the basket
- The dump is when those parts come OUT painted

### What This Means for basket_dump_count
- `basket_dump_count` in the webhook should only count dumps that had parts (correlated with a prior hopper fill)
- Dry startup dumps should be excluded
- This gives a TRUE production basket count for efficiency calculations
