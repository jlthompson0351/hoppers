# Calibration Current State (Feb 2026)

This document is the current source of truth for weight calibration behavior in this repository.

Scope:
- Weight calibration only (signal mV -> lb)
- Not PLC output correction-point workflow
- Not board factory calibration CLI tools

## 1) Current code behavior

### Storage
- Calibration points are stored in SQLite table `calibration_points`:
  - `id`, `ts`, `known_weight_lbs`, `signal`, `ratiometric`
  - Defined in `src/db/schema.py`
- Point add path:
  - `src/app/routes.py` -> `/api/calibration/add`
  - `src/db/repo.py::add_calibration_point()` (`INSERT`, append-only)
- Zero/tare offsets are stored in config JSON (`config_versions` -> `scale`):
  - **`zero_offset_mv`** — CANONICAL source of truth (signal domain correction)
  - `zero_offset_signal` — Legacy alias (same as `zero_offset_mv`)
  - `zero_offset_lbs` — Derived/cached field for display compatibility
  - `zero_offset_updated_utc` — Timestamp of last zero operation
  - `tare_offset_lbs` — Weight domain tare (applied after calibration)

### Runtime mapping
- Main loop: `src/services/acquisition.py`
- **Signal normalization (Zero applied in Signal Domain BEFORE calibration)**:
  - `adjusted_mv = raw_mv - zero_offset_mv`
  - Zero correction happens in mV space before weight conversion
  - This ensures zero tracking does not alter calibration slope/gain
- Mapping modes:
  - `>=2 points`: two-point linear from endpoint points (`slope`, `intercept`)
  - `1 point`: single-point slope through origin
  - `0 points`: uncalibrated fallback (`adjusted_mv * 100.0`)
- Calibration points are queried sorted by `known_weight_lbs ASC` from `get_calibration_points()`.

### Re-running calibration at the same known weight (for example, 50 lb)
- Each run appends a new row.
- Existing rows are not auto-averaged and not hard-overwritten in-place.
- Runtime still computes linear conversion from endpoint points.

### Zero tracking separation
- Zero tracking (`src/core/zero_tracking.py`) adjusts only baseline offset (`zero_offset_mv`).
- **Zero tracking calculates drift in lbs, then converts to mV for storage**:
  - Measures current gross weight (lbs)
  - Converts weight error to signal error using `lbs_per_mv` from calibration slope
  - Stores result as `zero_offset_mv` (canonical)
  - Derives `zero_offset_lbs` from `zero_offset_mv * lbs_per_mv` for display
- It does not intentionally rewrite span/gain calibration.
- It is gated by stability/load/tare/no-calibration conditions.

## 2) Weekly operator guidance (current behavior)

1. Clear TARE.
2. Ensure platform is empty and stable.
3. Press ZERO (or allow zero tracking to settle if enabled and appropriate).
4. Apply known check weight (for example, 50 lb), wait for STABLE.
5. Add calibration point.
6. Verify with at least one additional check weight when available.
7. If duplicate stale points exist at the same known weight, clean them in Calibration Hub.

## 3) Hardening direction agreed in review

- Keep two-point linear as primary operator model (zero + one known span weight).
- Make active-point selection deterministic (latest point per known weight).
- Add explicit calibration mode semantics:
  - default `overwrite` for active point behavior
  - optional `average` only with explicit operator confirmation under stable conditions
- Add explicit calibration history records with:
  - timestamp
  - known weight
  - resulting slope/intercept
  - calibration method
- Expose calibration metadata in API/dashboard:
  - method
  - slope/intercept
  - last calibration timestamp

## 4) Live Calibration Snapshot (Feb 24, 2026)

**Zero Offset:** 32.68 lbs (0.29 mV)
**Zero Target:** 3.0 lbs
**Curve:** 9-point piecewise linear

| Point | Known Weight (lb) | Signal (mV) |
|-------|-------------------|-------------|
| 1 | 3.0 | 5.644 |
| 2 | 25.0 | 5.840 |
| 3 | 50.0 | 6.064 |
| 4 | 100.0 | 6.510 |
| 5 | 150.0 | 6.957 |
| 6 | 200.0 | 7.403 |
| 7 | 250.0 | 7.849 |
| 8 | 300.0 | 8.296 |
| 9 | 335.0 | 8.608 |

If any other document conflicts with this file on calibration behavior, trust this file.
