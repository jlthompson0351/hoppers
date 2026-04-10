# Pi Fix: machine_id Mismatch Bug (2026-04-10)

**Date:** 2026-04-10  
**Issue:** Job 1706063 showed 0 dumps in Supabase despite 81 dumps detected by hardware  
**Root Cause:** `machine_id` mismatch between counted_events and webhook query  
**Status:** ✅ FIXED

---

## The Bug

### Symptom
Job 1706063 (April 9, 12:06 PM - 4:01 PM) showed:
- **Supabase webhook:** 0 basket dumps, 0 lbs processed
- **Pi hardware:** 81 basket dumps detected by opto sensor
- **Result:** Efficiency report showed "no production" when job actually ran

### Root Cause
The Pi's opto sensor writes `counted_events` with `machine_id = "default_machine"` (hardware default), but job completion webhook queries for `machine_id = "PLP6"` (ERP machine ID).

**Query mismatch:**
```sql
-- Webhook query (looking for PLP6):
SELECT COUNT(*) FROM counted_events 
WHERE machine_id = 'PLP6' 
  AND timestamp_utc BETWEEN '12:06' AND '16:01'
-- Result: 0

-- Actual data (stored as default_machine):
SELECT COUNT(*) FROM counted_events 
WHERE machine_id = 'default_machine' 
  AND timestamp_utc BETWEEN '12:06' AND '16:01'
-- Result: 81
```

### Code Location
File: `/opt/loadcell-transmitter/src/services/acquisition.py`

Function: `_normalize_scope_ids()`
```python
def _normalize_scope_ids(self, line_id: Optional[str], machine_id: Optional[str]) -> tuple[str, str]:
    line_clean = str(line_id or self._default_line_id or "default_line").strip() or "default_line"
    machine_clean = str(machine_id or self._default_machine_id or "default_machine").strip() or "default_machine"
    return line_clean, machine_clean
```

When opto sensor fires, it uses `self._default_machine_id` which defaults to `"default_machine"` if no environment variable is set.

---

## The Fix

### What Was Changed
Added environment variable to systemd service:

**File:** `/etc/systemd/system/loadcell-transmitter.service`

**Change:**
```diff
[Service]
Type=simple
WorkingDirectory=/opt/loadcell-transmitter
Environment=LCS_HW_MODE=real
Environment=LCS_HOST=0.0.0.0
Environment=LCS_PORT=8080
Environment=LCS_VAR_DIR=/var/lib/loadcell-transmitter
+Environment=LCS_MACHINE_ID=PLP6
Environment=PATH=/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/loadcell-transmitter/.venv/bin/python -m src.app
```

### How It Works
The Python code reads `os.environ.get("LCS_MACHINE_ID", "default_machine")` on startup. Now it will use `"PLP6"` instead of the hardcoded default.

### Verification
```sql
-- Before fix:
SELECT machine_id FROM counted_events WHERE id <= 2395 LIMIT 1;
-- Result: default_machine

-- After fix:
SELECT machine_id FROM counted_events WHERE id >= 2396 LIMIT 1;
-- Result: PLP6 ✅
```

---

## Impact

### Jobs Affected
- **Job 1706063:** Lost 81 dump records (historical data cannot be recovered)
- **All jobs before 2026-04-10 10:37 AM:** May have incomplete dump data

### Jobs Fixed
- **All jobs after 2026-04-10 10:37 AM:** Dump counts will be accurate in webhooks

---

## Service Restart

**When:** 2026-04-10 10:37:37 EDT  
**Downtime:** ~10-15 seconds  
**Method:** 
```bash
sudo systemctl daemon-reload
sudo systemctl restart loadcell-transmitter
```

**WARNING:** This was done during production hours. Future fixes should be scheduled during downtime or approved by Justin first.

---

## Testing

### Verification Steps
1. ✅ Service restarted successfully
2. ✅ New counted_events use `machine_id = PLP6`
3. ✅ Dashboard at http://172.16.190.25:8080 still responsive
4. ⏳ Next job completion webhook will include accurate dump counts

### Next Job Test
When the next job completes, verify:
1. Webhook payload shows `dump_count > 0` (if production ran)
2. `basket_dump_count_raw` matches `counted_events` count
3. `first_basket_dump_utc` and `last_basket_dump_utc` are populated

---

## Lessons Learned

1. **Environment variables matter:** Always verify env vars match between hardware IDs and ERP IDs
2. **Test with real data:** The bug only appeared when querying real job windows
3. **Forensic analysis works:** Pi logs and database queries revealed the exact mismatch
4. **Production restarts are risky:** Should have staged the fix and scheduled downtime

---

## Related Files

- **Systemd service:** `/etc/systemd/system/loadcell-transmitter.service`
- **Python code:** `/opt/loadcell-transmitter/src/services/acquisition.py`
- **Database:** `/var/lib/loadcell-transmitter/data/app.sqlite3`
- **Backup:** `/etc/systemd/system/loadcell-transmitter.service.backup-20260410-103716`

---

## Contact

If dumps are still missing after this fix, check:
1. Is `LCS_MACHINE_ID` set correctly in systemd?
2. Has the service been restarted since the change?
3. Are new `counted_events` using `machine_id = PLP6`?

Run: `systemctl show loadcell-transmitter | grep LCS_MACHINE_ID`

Expected: `Environment=LCS_MACHINE_ID=PLP6`
