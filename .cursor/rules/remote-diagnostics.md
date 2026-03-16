---
description: Remote troubleshooting standards for fleet management
---

# Remote Diagnostics Rules

## Design for Remote Support

When you can't be on-site, you need to diagnose and fix remotely. Every feature must support this.

### Required for Every Feature

When adding new features:
- [ ] Add diagnostic info to `/api/snapshot` if runtime state
- [ ] Log key events to SQLite events table
- [ ] Include feature status in health checks
- [ ] Document troubleshooting in `docs/MaintenanceAndTroubleshooting.md`

## Logging Standards (Remote-Friendly)

### Required Context in Logs
Every log message must include enough context to diagnose remotely:

```python
# GOOD - Remote-friendly log
logger.error(
    f"DAQ read failed: I2C timeout on 24b8vin at 0x31, "
    f"channel={channel}, attempt={retry}/3, will retry in {backoff}s"
)

# BAD - Useless for remote diagnosis
logger.error("Read failed")
```

### Log Levels
- **ERROR**: Faults that affect operation (hardware failures, service crashes)
- **WARNING**: Recoverable issues (retry succeeded, degraded mode)
- **INFO**: Normal operations (startup, config changes, calibration)
- **DEBUG**: Detailed diagnostics (loop timing, raw values)

### Event Logging to Database
Critical events should be logged to SQLite for historical analysis:
```python
# Log to events table for permanent record
self._repo.log_event(
    event_type="HARDWARE_FAULT",
    severity="ERROR",
    details={"board": "24b8vin", "error": str(e)}
)
```

## Health Check API

Every Pi should expose `/api/health` with:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-30T14:30:00Z",
  "version": "v1.2.3",
  "uptime_seconds": 86400,
  "boards": {
    "24b8vin": {"present": true, "firmware": "1.4"},
    "megaind": {"present": true, "firmware": "4.08"}
  },
  "acquisition_rate_hz": 17.2,
  "faults_active": [],
  "storage_used_mb": 145
}
```

## Remote Diagnostic Commands

### Agent-first rule
If an AI agent is running these diagnostics, use Desktop Commander to launch the remote command instead of raw shell SSH.

### Quick Health Check
```powershell
# Check if Pi is reachable and service running
plink -pw <password> pi@172.16.190.25 "systemctl is-active loadcell-transmitter"
```

### View Recent Logs
```powershell
# Last 50 log lines
plink -pw <password> pi@172.16.190.25 "sudo journalctl -u loadcell-transmitter -n 50"

# Only errors
plink -pw <password> pi@172.16.190.25 "sudo journalctl -u loadcell-transmitter -n 100 | grep -i error"
```

### Check Hardware Status
```powershell
# I2C device scan
plink -pw <password> pi@172.16.190.25 "sudo i2cdetect -y 1"
```

### Check Database Health
```powershell
# SQLite integrity check
plink -pw <password> pi@172.16.190.25 "sqlite3 /var/lib/loadcell-transmitter/app.sqlite3 'PRAGMA integrity_check;'"
```

### Check Disk Space
```powershell
plink -pw <password> pi@172.16.190.25 "df -h /"
```

## Common Remote Troubleshooting Workflows

### "Dashboard won't load"
1. Ping Pi: `ping 172.16.190.25`
2. Check service: `systemctl is-active loadcell-transmitter`
3. Check logs for errors
4. Check port 8080 is listening: `ss -tlnp | grep 8080`

### "I/O shows OFFLINE"
1. Check I2C devices present: `i2cdetect -y 1`
2. Check recent logs for hardware errors
3. Verify 24V power supply
4. May need physical inspection if boards not detected

### "Weight reading is wrong"
1. Check zero offset in UI
2. Check calibration points in database
3. Check excitation voltage
4. May need re-calibration (requires on-site)

## Documenting Remote Sessions

After remote troubleshooting, document:
```markdown
## Remote Diagnosis - YYYY-MM-DD

**Site**: [Site Name]
**Reported Issue**: [What operator reported]
**Diagnosis**: [What you found]
**Commands Run**: [List of diagnostic commands]
**Resolution**: [What fixed it / what needs on-site attention]
**Follow-up**: [Any pending actions]
```

Add to `docs/MaintenanceAndTroubleshooting.md` if it's a new issue type.
