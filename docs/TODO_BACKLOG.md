# TODO Backlog

## 2026-02-27 - Post-live-test follow-ups

- [ ] Investigate mode auto-switch bug (`legacy_weight_mapping` -> `target_signal_mode`).
  - Reported behavior: operator sets Legacy mode, but it switches back to Job Target mode.
  - Verify all write paths that can change mode (`/api/job/mode`, settings save flow, startup/config sync code, external scripts).
  - Expected behavior: mode only changes when explicitly requested by operator/API.

- [ ] Ensure mode persistence on startup/reboot.
  - Persist and honor selected `job_control.mode` and `job_control.enabled` exactly as last saved.
  - Confirm startup logic does not overwrite mode with defaults.
  - Add/expand regression tests for mode persistence across restart.
