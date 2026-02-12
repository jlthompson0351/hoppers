---
description: Raspberry Pi deployment and testing procedures
globs: ["deploy_*.ps1", "scripts/*.sh", "scripts/*.ps1"]
---

# Raspberry Pi Deployment Rules

## Current Deployment Target

| Property | Value |
|----------|-------|
| **Pi IP** | 172.16.190.25 |
| **Username** | pi |
| **Password** | depor |
| **Install Path** | `/opt/loadcell-transmitter/` |
| **Data Path** | `/var/lib/loadcell-transmitter/` |
| **Service** | `loadcell-transmitter.service` |
| **Dashboard** | http://172.16.190.25:8080 |

## Pre-Deployment Checklist

Before deploying ANY code to Pi:
- [ ] Test locally with `python -m src.app`
- [ ] Check syntax: `python -m py_compile src/**/*.py`
- [ ] Run linter if available
- [ ] Verify requirements.txt includes all new dependencies
- [ ] Identify ALL files that need to be deployed
- [ ] Backup calibration data if touching database-related code

## Deployment Commands

### Windows (pscp/plink)
```powershell
# Copy single file
pscp -pw depor local_file.py pi@172.16.190.25:/opt/loadcell-transmitter/path/to/file.py

# Copy directory
pscp -r -pw depor src pi@172.16.190.25:/opt/loadcell-transmitter/

# Restart service
plink -pw depor pi@172.16.190.25 "sudo systemctl restart loadcell-transmitter"

# Check status
plink -pw depor pi@172.16.190.25 "sudo systemctl status loadcell-transmitter --no-pager"

# View logs
plink -pw depor pi@172.16.190.25 "sudo journalctl -u loadcell-transmitter -n 50"
```

## Post-Deployment Verification

After EVERY deployment:
- [ ] Check service started: `systemctl is-active loadcell-transmitter`
- [ ] Dashboard accessible: http://172.16.190.25:8080
- [ ] I/O status shows expected state (LIVE or OFFLINE)
- [ ] Hard refresh browser (Ctrl+Shift+R) to clear cached JS/CSS
- [ ] Test the specific feature that was changed
- [ ] Monitor logs for 1-2 minutes for errors
- [ ] Update documentation (see documentation-sync rule)

## Rollback Procedure

If deployment fails:
```powershell
# Restore previous version from git
plink -pw depor pi@172.16.190.25 "cd /opt/loadcell-transmitter && git checkout [previous-commit]"

# Or restore from backup
plink -pw depor pi@172.16.190.25 "cp /var/lib/loadcell-transmitter/app.sqlite3.backup /var/lib/loadcell-transmitter/app.sqlite3"

# Restart
plink -pw depor pi@172.16.190.25 "sudo systemctl restart loadcell-transmitter"
```

## Safety Rules

- ⚠️ NEVER deploy untested code to production Pi
- ⚠️ ALWAYS backup calibration data before database-related changes
- ⚠️ ALWAYS verify service restarts successfully
- ⚠️ NEVER overwrite site-specific configuration without backup
- ⚠️ ALWAYS document what was deployed and why

## File Ownership

Files on Pi should be owned by `pi:pi`:
```bash
sudo chown -R pi:pi /opt/loadcell-transmitter/
```

Database directory owned by service:
```bash
sudo chown -R pi:pi /var/lib/loadcell-transmitter/
```
