# Deployment Log

This document records all deployments to production Pi systems.

---

## 2026-02-12 14:27 EST - PLC Output Auto-Armed on Power Up

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - core logic update  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/db/repo.py` - changed default `output.armed` state from `False` to `True`
- `src/app/routes.py` - changed default `megaind_io.armed` state from `False` to `True`
- `deploy_to_pi/repo.py` - changed default `output.armed` and `megaind_io.armed` from `False` to `True`
- `deploy_to_pi/routes.py` - changed default `megaind_io.armed` state from `False` to `True`

**Reason for Deployment**:
- User requirement: 0-10V PLC output must always default to ARMED/ON after every power up
- Previous behavior: outputs defaulted to DISARMED, requiring manual arming after each restart
- New behavior: outputs default to ARMED, automatically writing weight data on startup
- Disarm toggle still available for maintenance (e.g., when removing hardware cards)

**Verification**:
- Service restarted successfully via `sudo systemctl kill -s SIGKILL` + `start`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE (DAQ stack=0, MegaIND stack=2)
- Web UI serving on http://172.16.190.25:8080
- No errors in startup logs

**Notes**:
- This change affects **new installations** and **database resets**
- Existing systems retain their current armed state until database is reset or settings are saved
- Manual disarm is still possible via Settings page or Calibration Hub
- Change applies to both main PLC output and MegaIND I/O extra outputs

---

## 2026-02-12 08:14 EST - HDMI Layout + Zero Metadata Update

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - template + service restart  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/app/templates/hdmi.html` - centered weight card, zero metadata lines, and shift totals placeholder panel

**Reason for Deployment**:
- Improve readability on physical 800x480 HDMI screen.
- Mirror dashboard zero diagnostics directly on HDMI (`Zero Offset`, `Zero Tracking`, `Zero Updated`).
- Reserve space for upcoming database-backed daily/shift totals while keeping existing bottom controls unchanged.

**Verification**:
- `loadcell-transmitter` restarted successfully and reported `active`.
- `kiosk.service` restarted successfully and reported `active`.
- Remote file check confirmed `zero-tracking-info` and `CLEAR SHIFT TOTAL` markup exists in deployed `hdmi.html`.
- Live endpoint check (`curl http://localhost:8080/hdmi`) returned updated HDMI markup.

**Notes**:
- `CLEAR SHIFT TOTAL` is currently UI-only placeholder behavior.
- Back-end shift/day total clear actions will be wired after throughput database integration.

---

## 2026-02-11 11:59 EST - Excitation Monitoring Toggle

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - code + templates  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/app/routes.py` - persisted new `excitation.enabled` toggle from Settings form
- `src/services/acquisition.py` - excitation fault gating now conditional on `excitation.enabled`
- `src/db/repo.py` - default config includes `excitation.enabled: true`
- `src/app/templates/settings.html` - added "Enable Excitation Monitoring" UI toggle
- `src/app/templates/scale_settings.html` - added `DISABLED` excitation status display

**Reason for Deployment**:
- Field issue: output was being forced safe because excitation monitoring was active while excitation input was not being used.
- Added operator control to enable/disable excitation fault participation without changing calibration math.

**Verification**:
- Service restarted successfully on Pi.
- `systemctl is-active loadcell-transmitter` returned `active`.
- Remote template check confirmed new setting label exists:
  - `Enable Excitation Monitoring`

**Notes**:
- When monitoring is OFF, excitation does not force safe output.
- DAQ/MegaIND offline faults still force safe behavior as before.

---

## 2025-01-30 - AI Development System Setup

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - Configuration only  
**Version**: N/A (infrastructure setup)

**What Was Added**:
- `.cursor/rules/` - 5 rule files for code standards, deployment, documentation
- `.cursor/skills/` - 7 skill folders for common tasks
- `.cursor/agents/` - 8 subagent files for specialized assistance
- `configs/site_templates/` - Template infrastructure
- `docs/FLEET_INVENTORY.md` - Fleet tracking document
- `docs/DEPLOYMENT_LOG.md` - This deployment log

**Files Created**:
```
.cursor/
├── rules/
│   ├── industrial-code-standards.md
│   ├── pi-deployment.md
│   ├── documentation-sync.md
│   ├── fleet-configuration-management.md
│   └── remote-diagnostics.md
├── skills/
│   ├── deploy-to-pi/SKILL.md
│   ├── sync-hardware-docs/SKILL.md
│   ├── calibration-wizard/SKILL.md
│   ├── i2c-diagnostics/SKILL.md
│   ├── fleet-deployment/SKILL.md
│   ├── backup-calibration-data/SKILL.md
│   └── site-commissioning/SKILL.md
└── agents/
    ├── pi-deployment-specialist.md
    ├── hardware-integration-reviewer.md
    ├── calibration-specialist.md
    ├── documentation-updater.md
    ├── plc-integration-specialist.md
    ├── troubleshooting-guide.md
    ├── fleet-monitor.md
    └── auto-documenter.md

configs/
├── site_templates/
│   └── README.md
└── deployed/
    └── (empty - for future site configs)

docs/
├── FLEET_INVENTORY.md
└── DEPLOYMENT_LOG.md
```

**Reason**: Establish AI-assisted development workflow with automatic documentation, deployment safety, and fleet management capabilities.

**Notes**: 
- No code changes to production Pi
- Configuration files only in local repository
- Ready for future multi-site deployment

---

## Template for Future Deployments

```markdown
## YYYY-MM-DD HH:MM - vX.Y.Z

**Deployed By**: [name]
**Sites Updated**: 
- Site A (172.16.190.25) ✅
- Site B (xxx.xxx.xxx.xxx) ✅

**Files Changed**:
- `src/file1.py` - [reason]
- `src/file2.py` - [reason]

**Reason for Deployment**: 
[Why this was needed - bug fix, feature, etc.]

**Pre-Deployment**:
- [ ] Tested locally
- [ ] Backup created
- [ ] User confirmed

**Verification**:
- [ ] Service running
- [ ] Dashboard accessible
- [ ] Feature tested
- [ ] Logs checked

**Rollback Plan**:
[Commands to rollback if needed]

**Notes**:
[Any observations]
```

---

## Deployment Guidelines

### Before Any Deployment
1. Test changes locally
2. Backup calibration data on target Pi
3. Identify ALL files that need deployment
4. Get user confirmation

### After Any Deployment
1. Verify service running
2. Test the changed feature
3. Check logs for errors
4. Update this log
5. Update FLEET_INVENTORY.md with new version

### Rollback Procedure
```powershell
# Restore database if needed
plink -pw depor pi@[IP] "cp /var/lib/loadcell-transmitter/app.sqlite3.backup /var/lib/loadcell-transmitter/app.sqlite3"

# Restore code
plink -pw depor pi@[IP] "cd /opt/loadcell-transmitter && git checkout [commit]"

# Restart
plink -pw depor pi@[IP] "sudo systemctl restart loadcell-transmitter"
```
