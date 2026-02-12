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
  - `zero_offset_mv`, `zero_offset_signal`, `zero_offset_updated_utc`, `tare_offset_lbs`

### Runtime mapping
- Main loop: `src/services/acquisition.py`
- Signal normalization:
  - `adjusted_mv = raw_mv - zero_offset_mv`
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
- It uses `lbs_per_mv` to convert weight correction to signal correction.
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

If any other document conflicts with this file on calibration behavior, trust this file.
