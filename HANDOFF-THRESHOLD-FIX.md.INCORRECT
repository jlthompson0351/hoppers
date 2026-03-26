# CRITICAL: Fix Throughput Cycle Thresholds

**Priority:** HIGH — Blocks employee efficiency feature  
**Component:** Hopper Scale Pi (PLP6)  
**Issue:** Throughput cycle detector is not completing cycles  
**Root Cause:** Threshold miscalibration  

---

## Problem Summary

The `ThroughputCycleDetector` state machine is running but never completing cycles because the configured thresholds don't match actual production loads.

**Current state:**
- ✅ Service running (9 days uptime)
- ✅ Opto input monitoring active (CH1 basket dumps detected)
- ✅ Dashboard live at `http://172.16.190.25:8080`
- ❌ `throughput_events` table empty (0 rows)
- ❌ Cycles never reach completion
- ❌ No webhooks being sent

**State machine stuck:**
```
EMPTY_STABLE → FILLING → FULL_STABLE → DUMPING → EMPTY_STABLE
                   ↑
              STUCK HERE (never completing)
```

---

## Root Cause

From Talos forensics:
> "The `ThroughputCycleDetector` state machine appears to be waiting for `stable` readings that aren't being met, or the thresholds (`throughput_full_min_lb`, `throughput_rise_trigger_lb`) are not aligned with current material loads."

**Translation:** The Pi doesn't recognize when the hopper is full or when a dump happens because the weight thresholds are wrong.

---

## What Needs to Happen

### 1. Find the Threshold Config

**Locations to check:**
- Dashboard UI: `http://172.16.190.25:8080` (likely has a config/settings page)
- Config file: `/opt/loadcell-transmitter/var/config/` or similar
- Database: Check `set_weight_current` or similar config tables in `app.sqlite3`

**Thresholds to find:**
- `throughput_full_min_lb` — Minimum weight to consider hopper "full"
- `throughput_rise_trigger_lb` — Weight increase threshold to start "filling" state
- `throughput_empty_max_lb` — Maximum weight to consider hopper "empty"
- Stability thresholds (time/weight variance to confirm state)

---

### 2. Determine Correct Values

**Method A: Watch a Live Job**
1. SSH into Pi: `ssh pi@172.16.190.25` (or via Tailscale: `hoppers.tail840434.ts.net`)
2. Open dashboard: `http://172.16.190.25:8080`
3. Run a real production job
4. Watch the live weight readings
5. Note the weight values at each stage:
   - Empty hopper: ~X lbs
   - Loading (rising): X → Y lbs
   - Full hopper: ~Y lbs
   - Dumping: Y → X lbs

**Method B: Ask Justin**
Typical basket weights for this machine:
- Empty hopper: ??? lbs
- Full hopper with 325 lb basket: ??? lbs
- Trigger threshold should be: ??? lbs above empty baseline

---

### 3. Update the Thresholds

**Via Dashboard (Preferred):**
- Navigate to Settings or Configuration
- Update threshold values
- Save/restart if needed

**Via Config File:**
```bash
ssh pi@172.16.190.25
cd /opt/loadcell-transmitter/var/config  # or wherever config lives
# Edit the config file (JSON? YAML? INI?)
sudo systemctl restart loadcell-transmitter
```

**Via Database:**
```bash
sqlite3 /opt/loadcell-transmitter/var/data/app.sqlite3
# Update relevant config table
# Restart service
```

---

### 4. Test Verification

After updating thresholds, run a test job and verify:

1. **Watch live state transitions** (via dashboard logs or DB queries):
   ```sql
   SELECT * FROM events ORDER BY timestamp_utc DESC LIMIT 20;
   ```

2. **Confirm cycle completion** (check throughput_events table):
   ```sql
   SELECT COUNT(*) FROM throughput_events;
   ```
   Should be > 0 after completing a job.

3. **Verify webhook sent** (check job_completion_outbox):
   ```sql
   SELECT * FROM job_completion_outbox ORDER BY created_at DESC LIMIT 5;
   ```

4. **Check Supabase** — Did the webhook arrive?
   ```sql
   SELECT * FROM scale_completion_data ORDER BY created_at DESC LIMIT 5;
   ```

---

## Example Threshold Values (Placeholder)

**These are GUESSES — adjust based on real observations:**

```json
{
  "throughput_config": {
    "empty_max_lb": 50,           // Max weight to consider "empty"
    "rise_trigger_lb": 100,       // Weight increase to trigger "filling"
    "full_min_lb": 300,           // Min weight to consider "full"
    "dump_trigger_lb": -100,      // Weight drop to trigger "dumping"
    "stable_duration_s": 2,       // Seconds to confirm stable state
    "stable_variance_lb": 5       // Max variance to consider "stable"
  }
}
```

**Adjust these based on:**
- Typical basket weight (e.g., 325 lbs)
- Hopper tare weight
- Material characteristics (free-flowing vs sticky)

---

## Why This Blocks Employee Efficiency

The employee efficiency feature relies on:
1. ✅ Basket dump events (opto input) — **WORKING**
2. ❌ Throughput cycle events (hopper fill/dump) — **BLOCKED**
3. ❌ Job completion webhooks — **BLOCKED**

Until cycles complete and webhooks flow, we can't add the efficiency enhancements.

---

## Success Criteria

- [ ] Thresholds identified and documented
- [ ] Thresholds updated to match production loads
- [ ] Test job completes with visible state transitions
- [ ] `throughput_events` table populates (multiple rows)
- [ ] Webhook successfully sent to Supabase
- [ ] Scale completion data appears in Supabase `scale_completion_data` table

---

## Questions?

If you're unsure about threshold values, ask Justin for:
- Typical empty hopper weight
- Typical full hopper weight (with 325 lb basket)
- How many baskets per job (to verify cycle count)

Or send Talos back to the Pi to watch a live job and log the weight readings.

---

**After this fix is verified, proceed to `HANDOFF-EMPLOYEE-EFFICIENCY.md` to add the efficiency enhancements.**
