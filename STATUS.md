# STATUS

## Repo
- Branch in this workspace: `main`
- Product/runtime rollout truth still comes from tracked docs and deployment history.
- Workspace path is environment-specific; use the current repo root instead of hardcoded absolute paths.

---

## Latest Activity (2026-04-13) — STAGED, PENDING RESTART

### Architecture Decision: Opto-First Cycle Tracking

After deep investigation, the hopper fill/dump weight cycle detector (`throughput_events`) was found to be unreliable due to mechanical vibration causing false dump triggers (`dump_drop_lb = 6` was too sensitive). Rather than chase a noisy weight signal for cycle timing, the architecture was simplified:

**The opto ISO signal is the source of truth for all cycle metrics.**

- `throughput.enabled` → **`False`** (hopper fill tracking OFF, staged in config_versions)
- `dump_drop_lb` → `25.0` (staged in config_versions, ready if re-enabled later)
- `basket_dump_count_raw` → count of opto fires (each = one basket rotation, already deduplicated by 30s cooldown)
- `basket_cycle_count` → **`= basket_dump_count_raw`** (removed incorrect `÷ 2`)
- `avg_cycle_time_ms` → **calculated from opto timestamps**: `(last_dump_utc - first_dump_utc) / (count - 1)`
- `anomaly_detected` → **`False`** (cooldown handles deduplication, odd/even check removed)

### Files Staged on Pi (NOT YET LIVE — awaiting restart)

| File | Change |
|---|---|
| `src/core/throughput_cycle.py` | Complete rewrite — simpler state machine, dump = 25+ lb drop from peak, detailed logging |
| `src/services/acquisition.py` | `basket_cycle_count = raw` (no ÷2), `avg_cycle_time_ms` from opto timestamps, `anomaly_detected = False`, throughput disabled |
| `src/db/repo.py` | `fill_time_ms` / `dump_time_ms` included in SELECT queries |
| `src/app/routes.py` | `fill_time_ms` / `dump_time_ms` in JSON/CSV endpoints |
| `config_versions` (DB) | `throughput.enabled = false`, `dump_drop_lb = 25.0` |

### What the Completed Job Webhook Sends After Restart

```
basket_dump_count_raw  = opto fire count (each = one basket cycle, deduplicated by 30s cooldown)
basket_cycle_count     = same as basket_dump_count_raw (not divided by 2)
avg_cycle_time_ms      = (last_dump - first_dump) / (count - 1) ms — from opto timestamps
first_basket_dump_utc  = timestamp of first opto fire in job window
last_basket_dump_utc   = timestamp of last opto fire in job window
idle_gaps              = gaps >= 2 hours between consecutive dumps (line starvation indicator)
anomaly_detected       = false (always — cooldown handles deduplication)
avg_hopper_load_time_ms = 0 (throughput disabled)
hopper_load_times      = [] (throughput disabled)
dump_events            = [] (throughput disabled)
```

### Root Cause of Throughput Failure (RESOLVED by disabling)
- `dump_drop_lb = 6` triggered false DUMPING transitions on normal ~6 lb machine vibration
- State machine left FULL_STABLE prematurely → real dump hit in FILLING state → aborted
- Result: zero `throughput_events` rows recorded since April 10
- New `throughput_cycle.py` uses `dump_drop_lb = 25` (≥25 lb drop = real dump)
- But since basket timing from opto is simpler and more reliable, throughput is left disabled

---

## Previous Activity (2026-04-12)

### ThroughputCycleDetector Rebound Bug Fixed (LIVE)
- Fixed `_dump_seen_near_empty` flag to prevent mechanical bounce from cancelling empty confirmation
- `empty_confirm_s` reduced from `2.0` → `0.5`
- Deployed and live since `2026-04-12T11:49:35Z`

### Basket Dump Audit Fixes (STAGED 2026-04-13)
- `acquisition.py` — corrected critical `AttributeError`: `_throughput_cycle` → `_throughput_detector`
- Silenced `except Exception: pass` in opto handler → now logs `exc_info=True`
- Throttled `trends_total` logging from 20Hz → 1Hz (`_loop_count % 20`)
- `repo.py` — added `fill_time_ms`, `dump_time_ms` to SELECT queries

---

## Previous Activity (2026-04-10)

### DB Maintenance Staged
- `run_maintenance(keep_days=7)` added to `repo.py`; prunes 8 append-only tables hourly
- Staged on Pi 2026-04-10 12:37 EDT — activates on restart

### machine_id Mismatch Fixed (LIVE)
- `LCS_MACHINE_ID=PLP6` added to systemd. Service restarted 2026-04-10 10:37 EDT.
- `counted_events` now write `machine_id='PLP6'` correctly.

---

## Current State Summary

| Component | Status |
|---|---|
| Opto basket dump counting | ✅ LIVE and correct — 173 total in DB, 40 today |
| `avg_cycle_time_ms` from opto | ✅ STAGED — will be live after restart |
| `basket_cycle_count` (correct, no ÷2) | ✅ STAGED — will be live after restart |
| Hopper fill time tracking | ⛔ DISABLED in config — staged |
| DB maintenance (hourly pruning) | ✅ STAGED — will be live after restart |
| Backend / Supabase | ✅ HEALTHY — receiving data |

## Next Steps
1. **Restart Pi** — all staged changes become live simultaneously
2. Verify first completed-job webhook has `avg_cycle_time_ms > 0` and `basket_cycle_count > 0`
3. Verify Supabase `scale_completion_data` row has correct values
4. If line runs normally (~30 dumps/hr), validate `avg_cycle_time_ms ≈ 103,000 ms` (~1:43 min)
5. Schedule `VACUUM` during next approved downtime window to reclaim SD card space

## Working Rule
Git is source of truth for implementation. Repo docs are source of truth for shared project state. Running Pi is source of truth for what is actually live.
