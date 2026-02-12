---
description: MANDATORY documentation updates after any code change
alwaysApply: true
---

# Documentation Sync Rules

## 🔴 CRITICAL: Document Every Change

**After ANY fix, deployment, or configuration change, documentation MUST be updated.**

This is NOT optional. If documentation wasn't updated, the task is NOT complete.

## Required Documentation After Changes

### For Bug Fixes
Update `docs/MaintenanceAndTroubleshooting.md`:
```markdown
### [Issue Title]
**Date**: YYYY-MM-DD
**Symptom**: What the user reported
**Root Cause**: What was actually wrong
**Solution**: Exact fix (commands, code changes)
**Prevention**: How to avoid in future
**Files Changed**: List of modified files
```

### For Deployments
Update `docs/DEPLOYMENT_LOG.md`:
```markdown
## YYYY-MM-DD - v1.X.X Deployment

**Deployed By**: [name]
**Sites Updated**: [list of Pi IPs/sites]
**Files Changed**:
- src/file1.py (bug fix for X)
- src/file2.py (new feature Y)

**Reason**: [why this deployment was needed]
**Verification**: [how we confirmed it works]
**Rollback Plan**: [how to undo if needed]
```

### For Configuration Changes
Update the relevant settings docs:
- `docs/MegaIND_Settings_SPEC.md` - MegaIND configuration
- `docs/24b8vin_Settings_Schema.json` - DAQ configuration
- `docs/Architecture.md` - System-level changes

### For New Features
- Update `README.md` if user-facing
- Update `docs/CURRENT_IMPLEMENTATION.md`
- Update relevant hardware docs if touching hardware

## Code → Doc Mappings

When these files change, update corresponding docs:

| Code Changed | Update These Docs |
|--------------|-------------------|
| `src/hw/sequent_*.py` | `docs/Architecture.md`, hardware reference docs |
| `src/services/acquisition.py` | `docs/CalibrationProcedure.md`, `docs/CALIBRATION_CURRENT_STATE.md`, `docs/Architecture.md` |
| `src/core/zeroing.py` | `docs/CalibrationProcedure.md`, `docs/CALIBRATION_CURRENT_STATE.md` |
| `src/core/zero_tracking.py` | `docs/DRIFT_COMPENSATION_DIAGRAM.md`, `docs/ZERO_VS_TARE_FIX.md`, `docs/ZERO_TRACKING_OPERATOR_GUIDE.md` |
| `src/app/routes.py` | `docs/CURRENT_UI_REFERENCE.md` |
| `src/db/schema.py` | `docs/Architecture.md` (Section 5) |
| `deploy_*.ps1`, `scripts/*.sh` | `docs/CONNECTION_GUIDE.md`, `README.md` |
| Any calibration logic | `docs/CalibrationProcedure.md` |

## Documentation Standards

### Format Requirements
- Use Markdown
- Include code examples with actual file paths
- Use tables for reference data
- Include dates on major updates
- Use checkboxes for procedures: `- [ ] Step`

### Quality Requirements
- Commands must be copy-pasteable
- Include expected output where helpful
- Explain the "why" not just the "what"
- Keep docs operator-friendly (not just for developers)

## Enforcement Checklist

Before marking ANY task complete, verify:
- [ ] Was documentation updated?
- [ ] Are commands/examples accurate and tested?
- [ ] Is the root cause explained (for fixes)?
- [ ] Is the change logged in appropriate tracking doc?
- [ ] Did you update `docs/TODAY_SUMMARY.md` if significant?

## TODAY_SUMMARY.md Updates

For significant changes, update `docs/TODAY_SUMMARY.md`:
- Current system status
- What was changed today
- What's working vs what needs attention
- Next steps / pending items

This file should be a quick "where we are" snapshot for anyone picking up the project.

## Don't Over-Document

Skip updating docs for:
- Internal refactoring with no behavior change
- Comment-only changes
- Whitespace/formatting fixes
- Temporary debug code (that gets removed)

But when in doubt, document it. Future you will thank present you.
