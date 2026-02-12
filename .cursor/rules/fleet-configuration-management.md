---
description: Managing configurations across multiple deployed Pi systems
alwaysApply: true
---

# Fleet Configuration Management

## Multi-Site Architecture

### Configuration Levels
1. **Universal Settings** - Same across all Pis (safety limits, retry logic)
2. **Site-Specific Settings** - Per-location (calibration, IP, PLC scaling)
3. **Device-Specific Settings** - Per-Pi (I2C addresses if different, hostname)

### Configuration Storage
```
configs/
  ├── site_templates/          # Reusable templates for new sites
  │   ├── 4leg_250lb_static.json
  │   ├── 4leg_500lb_dynamic.json
  │   └── README.md
  └── deployed/                # Actual deployed configs (one per site)
      ├── pi_172.16.190.25.json
      └── [future sites...]
```

## Fleet Inventory (REQUIRED)

Maintain `docs/FLEET_INVENTORY.md` with ALL deployed Pis:

```markdown
| Site | Pi IP | Hostname | Version | Hopper | Capacity | Status |
|------|-------|----------|---------|--------|----------|--------|
| Site A | 172.16.190.25 | Hoppers | v1.2.3 | 4-leg | 250 lb | ✅ |
```

**Update this file after EVERY deployment or site change.**

## Version Control Requirements

### Tagging Deployments
When deploying to production:
```bash
# Tag the commit that was deployed
git tag -a v1.2.3 -m "Deployed to Site A on 2025-01-30"
git push origin v1.2.3
```

### Tracking Site Versions
Track which version is running on each Pi in `docs/FLEET_INVENTORY.md`.

## Configuration Protection Rules

### ⚠️ NEVER Overwrite Calibration
During code deployments:
- DO deploy code files (`src/`, `scripts/`)
- DO NOT overwrite database (`app.sqlite3`)
- DO NOT overwrite site config without backup

### ⚠️ ALWAYS Backup Before Deployment
Before deploying to any Pi:
```powershell
# Backup database
plink -pw depor pi@[IP] "cp /var/lib/loadcell-transmitter/app.sqlite3 /var/lib/loadcell-transmitter/app.sqlite3.backup-$(date +%Y%m%d)"
```

### ⚠️ Document Site Differences
Each site may have unique:
- Calibration curves (from their specific load cells)
- PLC scaling (different PLC configurations)
- Channel mapping (different number of load cells)
- Tuning parameters (different application dynamics)

## Deployment Workflow (Multi-Site)

1. **Test changes on development** (local or test Pi)
2. **Create deployment package** with version tag
3. **Identify target sites** (all? subset? one?)
4. **Backup calibration data** from target Pis
5. **Deploy to target Pis** (use fleet-deployment skill)
6. **Verify each Pi** separately
7. **Update fleet inventory** with new versions
8. **Document deployment** in `docs/DEPLOYMENT_LOG.md`

## Site-Specific Documentation

For each site, maintain notes in fleet inventory or separate site docs:
- Physical location and contact info
- Site-specific quirks or configuration
- Calibration history
- Maintenance history
- Known issues

## New Site Checklist

When adding a new Pi to the fleet:
- [ ] Assign static IP or document DHCP reservation
- [ ] Add to `docs/FLEET_INVENTORY.md`
- [ ] Create site-specific config from template
- [ ] Save config to `configs/deployed/`
- [ ] Document installation in deployment log
- [ ] Backup initial calibration after commissioning
