# HANDOFF

## Current State (2026-04-13) — STAGED, PENDING PI RESTART

### What's staged on the Pi right now

All changes are on Pi disk at `/opt/loadcell-transmitter`. Service is still running the old code.
**A Pi restart is all that's needed to make everything live.**

#### Files staged

| File | What changed |
|---|---|
| `src/core/throughput_cycle.py` | Complete rewrite — simpler design, dump detected as ≥25 lb drop from peak, full debug logging |
| `src/services/acquisition.py` | Multiple fixes — see details below |
| `src/db/repo.py` | `fill_time_ms` / `dump_time_ms` included in SELECT queries |
| `src/app/routes.py` | `fill_time_ms` / `dump_time_ms` in JSON/CSV API endpoints |
| `config_versions` (SQLite DB) | `throughput.enabled = false`, `dump_drop_lb = 25.0` |

#### `acquisition.py` key changes staged

1. **`basket_cycle_count = basket_dump_count_raw`** — removed wrong `÷ 2`. The 30-second cooldown already deduplicates double-fire opto signals; each `counted_event` = one basket rotation cycle.
2. **`avg_cycle_time_ms` from opto** — calculated as `(last_dump_utc - first_dump_utc) / (count - 1)`. Previously pulled from `throughput_events` (broken); now derived from opto timestamps.
3. **`anomaly_detected = False`** — removed odd/even check that was meaningless once cooldown deduplication was in place.
4. **`throughput.enabled = False`** — hopper weight cycle tracking disabled in config.
5. **Critical bug fix**: `_throughput_cycle.state` → `_throughput_detector.state` (AttributeError was silently swallowing all opto events in one code path)
6. **`trends_total` throttled** 20Hz → 1Hz (`_loop_count % 20`)
7. **Silent exception handlers** → now log with `exc_info=True`

---

### Architecture: Opto Is the Source of Truth

The key decision made on 2026-04-13:

**The ISO/opto signal counts basket rotation cycles. That is the only reliable metric for cycle time.**

- Each opto fire = one complete basket rotation dump (cooldown suppresses second fire of double-shake)
- Cycle time = time between opto fires (~1:43 min at current production rate)
- If cycle time grows > baseline → line is starving for parts
- Hopper weight cycle tracking (fill_time_ms, throughput_events) was disabled — it's unreliable due to mechanical vibration causing false DUMPING triggers on the 6 lb threshold

---

### What the Next Completed Job Webhook Will Send

After restart, the next job completion will send these from opto data:

```json
{
  "basket_dump_count_raw": 40,
  "basket_cycle_count": 40,
  "avg_cycle_time_ms": 103000,
  "first_basket_dump_utc": "2026-04-13T12:20:04+00:00",
  "last_basket_dump_utc": "2026-04-13T15:07:36+00:00",
  "idle_gaps": [...],
  "anomaly_detected": false,
  "avg_hopper_load_time_ms": 0,
  "hopper_load_times": [],
  "dump_events": []
}
```

`avg_cycle_time_ms ≈ 103,000 ms` (1:43 min) is the expected value at current production rate.

---

### Verification After Restart

1. Check `journalctl -u loadcell-transmitter -n 50` — confirm clean startup, no errors
2. Watch `counted_events` — dumps should appear every ~1:43 min
3. After next job completes, check the Supabase `scale_completion_data` row:
   - `avg_cycle_time_ms` should be ~103,000
   - `basket_dump_count_raw` = actual count (not halved)
   - `basket_cycle_count` = same as `basket_dump_count_raw`
4. Check `throughput_events` table — should stay at 3 rows (disabled, nothing new expected)

---

## Previous Handoff State

### 2026-04-12 — ThroughputCycleDetector Rebound Bug Fixed (LIVE)
- `_dump_seen_near_empty` flag added — mechanical bounce after dump no longer cancels empty confirmation
- `empty_confirm_s: 2.0 → 0.5` — catches brief empty windows
- Service restarted 2026-04-12 11:49 EDT

### 2026-04-10 — machine_id Fix (LIVE)
- `LCS_MACHINE_ID=PLP6` added to systemd unit
- `counted_events` now correctly write `machine_id='PLP6'`
- All basket dump data has been accurate since 2026-04-10 10:37 EDT

### 2026-04-10 — DB Maintenance Staged (ACTIVATES ON RESTART)
- Hourly `run_maintenance(keep_days=7)` added to `repo.py`
- Prunes `events`, `trends_total`, `throughput_events`, `counted_events`, and other append-only tables
- Will run first prune ~1 hour after restart
- Schedule a `VACUUM` during next downtime window after first prune

### 2026-03-26 — Opto Wiring Fix (LIVE)
- Physical wire is on IN1; was mapped to TARE, changed to `Basket Dump Count`
- `counted_events` started writing correctly from this date

---

### Cross-Project Contract

Hopper's role in the three-project manufacturing system:
1. **Hopper** (Pi scale runtime) — source of `basket_dump_count`, `avg_cycle_time_ms`, `first/last_basket_dump_utc`, `idle_gaps`, set weight, rezero warnings
2. **Supabase** — mirrors fields into `scale_completion_data` and `completed_jobs`
3. **Frontend** — consumes from Supabase for machine kiosk and efficiency dashboards

Key metric for line performance: `avg_cycle_time_ms`. If this is longer than baseline (~103,000 ms), the line is starving for parts.

---

### Next Steps for Next Agent

1. After Pi restart, verify metrics are flowing correctly (see Verification section above)
2. Confirm `avg_cycle_time_ms` in Supabase `scale_completion_data` for the first post-restart job
3. Consider adding Supabase-side alert: if `avg_cycle_time_ms > baseline * 1.3` → line starving flag
4. Schedule Pi `VACUUM` during approved downtime window (after first maintenance prune runs)
5. Consider re-enabling `throughput.enabled = true` and testing the new `dump_drop_lb = 25` if fill time data becomes important later

### Working Rule
Git is source of truth for implementation. Repo docs are source of truth for project state. Running Pi is source of truth for what is actually live.
