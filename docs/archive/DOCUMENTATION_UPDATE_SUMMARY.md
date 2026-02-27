# Documentation Update Summary — Max Weight / Scale Range Removal

**Date**: February 15, 2026  
**Change**: Removed all references to deprecated "max weight" / "scale range" / min_lb/max_lb concept from documentation

## Background

The system has been updated to drive PLC output entirely via PLC profile training points (Calibration Hub). The concept of user-facing "min/max weight" or "scale range" settings no longer exists. A hard-coded linear fallback (0-250 lb = 0-10V) exists internally only when zero profile points are trained.

## Files Updated

### Core Specification & Architecture (3 files)

1. **docs/SRS.md**
   - Updated FR-01: Changed from "Weight Range & Accuracy Goal" to "Accuracy Goal"
   - Removed "Range: 0-300 lb" reference
   - Updated FR-07 PLC Output Behavior to describe profile-based mapping instead of configured min/max range

2. **docs/CURRENT_IMPLEMENTATION.md**
   - Replaced "Range Settings" section with deprecation notice
   - Explained new profile-based system with internal 0-250 lb fallback
   - Updated recent changes section: "Proportional Mapping" → "Profile-Based Mapping"

3. **docs/Architecture.md**
   - Updated output_writer.py description to reference PLC profile points
   - Updated SQLite data model description for plc_profile_points
   - Clarified internal fallback behavior

### User Documentation (1 file)

4. **README.md**
   - Replaced "Common PLC Scaling" section with "PLC Output Configuration"
   - Explained Calibration Hub training workflow
   - Removed "Configure range in Settings → Weight Range" reference

### Test & Verification Docs (3 files)

5. **docs/PLC_OUTPUT_VERIFICATION.md**
   - Updated Half-Scale Decision Gate section to reference profile points instead of "Settings min/max"
   - Updated Full System Test to describe profile curve verification
   - Removed formula references to max_weight
   - Added note about internal 0-250 lb fallback

6. **docs/HardwareTestReadiness_TODAY.md**
   - Updated Phase 4.1 "Configure Output Mode" to reference Calibration Hub training
   - Removed "Set scale range: Min weight/Max weight" instructions
   - Updated test procedures to verify against trained profile curve
   - Updated checklist: "Scale range configured" → "PLC profile points trained"
   - Updated troubleshooting: "Verify scale range settings" → "Verify PLC profile points trained"

7. **docs/QUICK_START_HARDWARE_TEST.md**
   - Updated Phase 4 to reference Calibration Hub for PLC profile training
   - Removed "Set scale range: 0-150 lb" instructions
   - Updated troubleshooting section

### Summary & Reference Docs (2 files)

8. **docs/TODAY_SUMMARY.md**
   - Updated Step 5 "Analog Output Test" to reference profile training
   - Updated troubleshooting table: "Verify scale range config" → "Verify PLC profile points trained"

9. **docs/CURRENT_UI_REFERENCE.md**
   - Removed "Min Weight: [0.0]" and "Max Weight: [300.0]" from UI mockup
   - Updated "Output Configuration" card to reference Calibration Hub
   - Updated Settings tab description to remove "Weight range" reference
   - Updated Key Features list

## What Was NOT Changed (Intentionally Preserved)

### Zero Tracking Range
- All references to `zero_tracking.range_lb` were preserved
- This is a different feature (zero tracking activation threshold) and is still active

### Throughput/Dump Detection
- References to dump detection thresholds and ranges were preserved
- These are production measurement features, not output scaling

### Production Weight Range
- Generic references to "production weight range" or "expected range" in the context of accuracy goals were preserved
- These describe the physical operating range, not the removed configuration setting

### Hardware Specifications
- References to hardware gain ranges, ADC ranges, and DAC ranges were preserved
- These are hardware capabilities, not user-facing configuration

## Key Terminology Changes

| Old Term | New Description |
|----------|-----------------|
| "Configure range in Settings" | "Train PLC profile points in Calibration Hub" |
| "Scale range (min/max lb)" | "PLC profile curve (trained weight/voltage pairs)" |
| "Linear Range (active)" | "Profile Curve (active)" or "Internal 0-250 lb fallback" |
| "Verify scale range config" | "Verify PLC profile points trained" |
| "max_weight formula" | "Profile curve interpolation" |
| "Configured min/max weight range" | "PLC profile training points" |

## Validation

All documentation searches confirm:
- ✅ Zero references to "min_lb" or "max_lb" (except deprecation notice)
- ✅ Zero references to "maximum weight" or "minimum weight" in output scaling context
- ✅ Zero references to "Configure range in Settings"
- ✅ Zero references to "Linear Range" as output mapping mode
- ✅ Zero references to "scale range" or "weight range" in output scaling context
- ✅ "zero_tracking.range_lb" references preserved (different feature)

## Summary

All documentation has been updated to reflect the new reality:
- PLC output mapping is configured via Calibration Hub (train weight/voltage pairs)
- System calculates volts-per-pound from saved profile points
- No user-facing range settings exist anymore
- Internal linear fallback (0-250 lb) only kicks in when no profile points are trained

The documentation is now consistent with the implemented architecture where Calibration Hub is the single source of truth for both weight calibration and PLC output mapping.
