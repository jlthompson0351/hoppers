# TODO Backlog

## 2026-02-27 - Post-live-test follow-ups

- [x] Persist Job Target set weight across restart/power cycle.
  - Root cause: `_job_set_weight` lived in-memory only, so startup defaulted to waiting/no active job.
  - Fix: persist `job_control.set_weight`/`active`/`meta` on webhook + clear, restore on service startup, and fall back to persisted values in `/api/snapshot`.
  - Added regression tests for restart restore + clear persistence + snapshot persisted fallback.

- [x] Add relational set-weight persistence + webhook audit tables.
  - Added SQLite `set_weight_current` (latest per line/machine) and append-only `set_weight_history`.
  - Persist full authenticated webhook JSON payload into `set_weight_history.metadata_json`.
  - Added runbook: `docs/SET_WEIGHT_PERSISTENCE_RUNBOOK.md`.

- [x] Add manager-only PIN-protected HDMI Override flow for job targets.
  - Replaced `SETTINGS` button with `OVERRIDE` on HDMI UI.
  - Added 4-digit PIN configuration to Settings > Job Target Mode.
  - Added `/api/job/override` endpoint that reuses `record_set_weight_receipt` to log overrides in `set_weight_history` with `manual_override:overridden:hdmi` source.

- [ ] Ensure mode persistence on startup/reboot.
  - Persist and honor selected `job_control.mode` and `job_control.enabled` exactly as last saved.
  - Confirm startup logic does not overwrite mode with defaults.
  - Add/expand regression tests for mode persistence across restart.

- [x] Investigate processing weight and dump counting regression.
  - Reported behavior: processing weight and dump counting are not working anymore.
  - Trace where processing weight is calculated and where dump counts are incremented/reset.
  - Add/expand regression tests to cover processing weight updates and dump counting.

- [ ] Audit weight storage and dump detection logic.
  - Reported behavior: processing weight is not adding up correctly and/or dumps are not being detected.
  - Trace how weight is stored at each stage (raw read → processed weight → stored value).
  - Verify dump detection thresholds, conditions, and state transitions are firing as expected.
  - Determine whether the issue is in weight accumulation, dump detection, or both.
  - Add regression tests to cover weight storage accuracy and dump detection edge cases.

- [ ] Create a new complete OS image backup with latest add-ons.
  - Run a full post-change image backup (current production stack + job-target persistence updates).
  - Label backup with date/version and store checksum + location for restore verification.
