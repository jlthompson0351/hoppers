# Connect CH1 Opto Input to Acquisition Loop

**Priority:** HIGH — Required for employee efficiency feature  
**Component:** Hopper Scale Pi (PLP6)  
**Issue:** Basket dump count always 0 in webhooks  
**Root Cause:** CH1 opto events not integrated into `counted_events` table  

---

## Problem Summary

The CH1 opto input is monitoring basket dumps and logging to `basket_monitor.log`, but the data is NOT being recorded in the `counted_events` table or included in the webhook payload.

**Current state:**
- ✅ CH1 hardware wired correctly (VEX1=positive, IN1=negative)
- ✅ `_poll_buttons` in `acquisition.py` monitoring CH1
- ✅ Events logging to `basket_monitor.log`
- ❌ Events NOT written to `counted_events` table
- ❌ `basket_dump_count` is 0 in all webhooks

**Result:** Employee efficiency feature cannot calculate basket cycles without this data.

---

## What Needs to Happen

### 1. Verify Current Opto Monitoring

Check that CH1 events are being detected:

```bash
ssh pi@hoppers.tail840434.ts.net
tail -50 /opt/loadcell-transmitter/logs/basket_monitor.log
```

**Expected:** Should see recent timestamp entries when baskets dump.

---

### 2. Connect Opto Events to `counted_events` Table

**Location:** `/opt/loadcell-transmitter/src/services/acquisition.py`

**Current code** (in `_poll_buttons` or similar):
```python
# CH1 opto detection happens here
# Currently only logs to file
```

**Add database write:**
```python
# When CH1 pulse detected:
repo.record_counted_event(
    event_type="basket_dump",
    timestamp_utc=now_utc_iso(),
    job_id=lifecycle_state.active_job_id,  # if job active
    metadata={"channel": "CH1", "pulse_count": pulse_count}
)
```

**Verify `repo.record_counted_event()` method exists:**
```bash
grep -n "record_counted_event" /opt/loadcell-transmitter/src/db/repo.py
```

If it doesn't exist, add it:
```python
def record_counted_event(self, event_type: str, timestamp_utc: str, job_id: str = None, metadata: dict = None):
    """Record a counted event (basket dump, etc.) to the database."""
    self.execute(
        "INSERT INTO counted_events (event_type, timestamp_utc, job_id, metadata_json) VALUES (?, ?, ?, ?)",
        (event_type, timestamp_utc, job_id, json.dumps(metadata or {}))
    )
```

---

### 3. Create `counted_events` Table (If Missing)

**Database:** `/var/lib/loadcell-transmitter/data/app.sqlite3` ← **LIVE DATABASE**

Check if table exists:
```bash
sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 ".tables" | grep counted
```

If missing, create it:
```sql
CREATE TABLE IF NOT EXISTS counted_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  timestamp_utc TEXT NOT NULL,
  job_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_counted_events_type ON counted_events(event_type);
CREATE INDEX IF NOT EXISTS idx_counted_events_job ON counted_events(job_id);
CREATE INDEX IF NOT EXISTS idx_counted_events_timestamp ON counted_events(timestamp_utc);
```

---

### 4. Update Webhook Payload

**Location:** `_build_completed_job_payload` in `acquisition.py`

**Add query for basket dumps:**
```python
# Query basket dump events for this job
basket_dump_events = repo.query_counted_events(
    event_type="basket_dump",
    job_id=lifecycle_state.active_job_id
)

basket_dump_count_raw = len(basket_dump_events)
```

**Update payload:**
```python
payload = {
    # ... existing fields ...
    "basket_dump_count": basket_dump_count_raw,  # Update this (currently hardcoded to 0)
}
```

---

### 5. Test Verification

After changes deployed:

1. **Restart service:**
   ```bash
   sudo systemctl restart loadcell-transmitter
   ```

2. **Run a test job** (or wait for next production job)

3. **Check `counted_events` table:**
   ```bash
   sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 \
     "SELECT COUNT(*) FROM counted_events WHERE event_type='basket_dump';"
   ```
   Should be > 0

4. **Check webhook payload** in Supabase:
   ```sql
   SELECT basket_dump_count FROM scale_completion_data 
   ORDER BY created_at DESC LIMIT 5;
   ```
   Should show non-zero values

---

## Critical Database Path

⚠️ **ALWAYS USE THE LIVE DATABASE:**

```
/var/lib/loadcell-transmitter/data/app.sqlite3
```

**DO NOT USE:**
- `/opt/loadcell-transmitter/app.sqlite3` (0 bytes, placeholder)
- `/opt/loadcell-transmitter/var/data/app.sqlite3` (stale, not updated)

**How to verify you're on the right one:**
```bash
sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 \
  "SELECT COUNT(*) FROM throughput_events;"
```
**Should return:** ~4,700+ rows  
**If 0:** You're looking at the wrong database

---

## Success Criteria

- [ ] `counted_events` table exists and has schema
- [ ] CH1 pulses write to `counted_events` with `event_type='basket_dump'`
- [ ] Webhook payload includes non-zero `basket_dump_count`
- [ ] Supabase `scale_completion_data` shows basket dump counts
- [ ] Employee efficiency feature can proceed (has dump data)

---

## After This Fix

Once basket dumps are flowing to the webhook, proceed to:
1. **`HANDOFF-EMPLOYEE-EFFICIENCY.md`** — Add dump timestamps, idle gaps, efficiency enhancements
2. Supabase calculation logic
3. Frontend UI

This is the only blocker. Everything else is ready.
