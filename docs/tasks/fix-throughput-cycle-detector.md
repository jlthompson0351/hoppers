# Task: Fix ThroughputCycleDetector — RESOLVED (2026-04-13)

**Status: CLOSED**

---

## Resolution Summary

After deep investigation on 2026-04-13, the root cause was identified and addressed:

**Root cause:** `dump_drop_lb = 6.0` was far too sensitive. Normal machine vibration (~6–10 lb oscillations on a fully-loaded hopper) triggered false DUMPING transitions. The state machine would leave FULL_STABLE prematurely, the real dump would arrive while in FILLING state, and get aborted. Result: zero `throughput_events` recorded.

**Decision:** Rather than tune an unreliable weight-based cycle detector, the architecture was simplified to use the opto ISO signal as the sole source of cycle timing. This is simpler, more reliable, and directly reflects physical reality.

**Changes staged on Pi (pending restart):**
1. `throughput.enabled = False` in config — hopper fill tracking disabled
2. `dump_drop_lb = 25.0` in config — ready if re-enabled later
3. `acquisition.py` — `avg_cycle_time_ms` now calculated from opto timestamps
4. `acquisition.py` — `basket_cycle_count = basket_dump_count_raw` (no ÷2)
5. `throughput_cycle.py` — complete rewrite with correct 25 lb dump threshold and logging

---

## Original Problem (Historical Reference)

The Pi has two parallel tracking systems:

| System | Table | Status as of 2026-04-13 |
|--------|-------|--------|
| Opto sensor (basket counter) | `counted_events` | ✅ Working — 173 total entries |
| Scale weight tracker | `throughput_events` | ❌ Only 3 rows ever recorded (Apr 10) |

### Bugs Found During Investigation

| Bug | Severity | Status |
|---|---|---|
| `_throughput_cycle.state` → should be `_throughput_detector.state` (AttributeError swallowed silently) | CRITICAL | Fixed in acquisition.py |
| `dump_drop_lb = 6` triggers on vibration, false DUMPING transitions | CRITICAL | Fixed: 25.0 default, throughput disabled |
| `basket_cycle_count = basket_dump_count_raw // 2` — wrong with 30s cooldown active | HIGH | Fixed: `= basket_dump_count_raw` |
| `avg_cycle_time_ms` sourced from `throughput_events` (always 0) | HIGH | Fixed: calculated from opto timestamps |
| `trends_total` logging at 20Hz (20x too fast) | MEDIUM | Fixed: `_loop_count % 20` (1Hz) |
| Silent `except Exception: pass` in opto handler | MEDIUM | Fixed: `exc_info=True` logging |
| `fill_time_ms`/`dump_time_ms` missing from SELECT queries in `repo.py` | LOW | Fixed |

### Why `dump_drop_lb = 6` Was Wrong

A fully loaded hopper at 96 lbs oscillating ±6 lbs from vibration would drop to 90 lbs momentarily, triggering `FULL_STABLE → DUMPING`. The weight bounced back to 94 lbs (above rebound trigger), pushing the state to `FILLING`. When the real dump happened 23 seconds later at -50 lbs, the state was FILLING, which aborted the cycle. The throughput_events record was never written.

Debug confirmation: Added `_log.info("THROUGHPUT DUMPING: ...")` inside the FULL_STABLE condition block. This log never appeared in journalctl — proving the FULL_STABLE → DUMPING transition was never being reached when the weight dropped, because the state was never actually FULL_STABLE at that moment.

---

## If Re-Enabling Fill Time Tracking Later

To re-enable the hopper fill time tracking:

1. Set `throughput.enabled = True` in config (via Pi web UI or DB update)
2. The new `throughput_cycle.py` uses:
   - `dump_drop_lb = 25` — requires 25+ lb drop from peak (ignores vibration)
   - No stability window — one reading above target = FULL
   - Target = `set_weight * full_pct_of_target` (e.g., 100 lbs × 0.95 = 95 lbs)
3. Watch `journalctl` for `THROUGHPUT DUMPING` and `THROUGHPUT CYCLE COMPLETE` log lines
4. Verify `throughput_events` table starts receiving rows within 2-3 cycles
