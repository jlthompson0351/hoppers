# Set Weight Persistence Runbook

## Scope

This runbook covers rollout of durable set-weight persistence, append-only audit history, and completed-job webhook outbox plumbing in SQLite:

- `set_weight_current` (quick latest lookup by line/machine)
- `set_weight_history` (append-only audit per authenticated receipt)
- `job_lifecycle_state` (active job tracker per line/machine)
- `job_completion_outbox` (retryable completed-job outbound webhook queue)
- `counted_events` (opto-driven counts, e.g. basket_dump; schema v7; completed-job payload includes `basket_dump_count`)

No Raspberry Pi reboot is required for this rollout.
Service restart is still required to load new code/migrations.

### 3. Manual Override (HDMI UI)
- Operators with the 4-digit Manager PIN can manually override the active set weight from the HDMI interface.
- Overrides are submitted to `POST /api/job/override`.
- They flow through the exact same persistence pipeline as webhooks (`record_set_weight_receipt`), ensuring they are logged in `set_weight_history`.
- Override records are explicitly tagged with `source="manual_override:overridden:hdmi"` and metadata `{"manual_override": true, "reason": "overridden"}`.

## Pre-Deployment Safety

1. Confirm DB path:
   - `/var/lib/loadcell-transmitter/data/app.sqlite3`
2. Capture an online SQLite backup (safe in WAL mode):
   - `sudo sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 ".backup /var/lib/loadcell-transmitter/data/app.sqlite3.pre-set-weight-v3.bak"`
3. Optional integrity check:
   - `sudo sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 "PRAGMA integrity_check;"`

## Deployment Steps (No Pi Reboot)

1. Deploy updated files to `/opt/loadcell-transmitter`:
   - `src/db/schema.py`
   - `src/db/migrate.py`
   - `src/db/repo.py`
   - `src/app/routes.py`
   - `src/services/acquisition.py`
   - test files/docs as needed
2. Apply service process restart so migration code is loaded (during approved production window):
   - `sudo systemctl restart loadcell-transmitter`
3. Validate service health:
   - `sudo systemctl is-active loadcell-transmitter`
   - `sudo journalctl -u loadcell-transmitter -n 200 --no-pager`

## Post-Deploy Verification

1. Confirm schema version and new tables:
   - `sudo sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 "SELECT version FROM schema_version;"`
   - `sudo sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 ".tables" | grep -E "set_weight_current|set_weight_history|job_lifecycle_state|job_completion_outbox|counted_events"`
2. Confirm new timestamp column:
   - `sudo sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 "PRAGMA table_info(set_weight_history);"` (verify `record_time_set_utc`)
3. Send a webhook payload and verify:
   - `set_weight_current` row updates for expected `line_id` + `machine_id`
   - one `set_weight_history` row inserted
4. Send the same `idempotencyKey` again and verify:
   - another `set_weight_history` row inserted
   - `duplicate_event=1`
   - `set_weight_current` remains unchanged

### Completed-job webhook checks

1. Set `job_control.completed_job_webhook_url` in Settings.
2. Send two different normal job IDs sequentially on the same machine scope.
3. Verify one row appears in `job_completion_outbox`.
4. Verify payload includes expected summary fields:
   - `line_id`, `machine_id`, `cycle_count`, `dump_count`, `basket_dump_count`
   - `override_seen`, `override_count`
   - `final_set_weight_lbs`, `final_set_weight_unit`
5. Verify re-zero diagnostic fields are present when applicable:
   - `rezero_warning_seen`
   - `rezero_warning_reason`
   - `rezero_warning_weight_lbs`
   - `rezero_warning_threshold_lbs`
   - `post_dump_rezero_applied`
   - `post_dump_rezero_last_apply_utc`
6. Verify outbound status transitions:
   - success: `status='sent'`
   - endpoint unavailable: `attempt_count` increments, `next_retry_at_utc` advances, `last_error` populated

## Power-Cycle Test Procedure

1. Send a known set weight for a known scope.
2. Record expected latest values:
   - `set_weight_current.set_weight_lbs`
   - `set_weight_current.source_event_id`
3. Restart the service process:
   - `sudo systemctl restart loadcell-transmitter`
4. Verify `/api/job/status` or `/api/snapshot` reports the same set weight.
5. Verify DB still matches expected `set_weight_current` row.

For destructive power-cut validation, run in staging first; compare DB values before/after power restoration.

## Monitoring Signals

- Watch app events:
  - `JOB_WEBHOOK_RECEIVED`
  - `JOB_CONTROL_CLEARED`
  - `JOB_CONTROL_LEGACY_PERSIST_FAILED` (warning only; durable path remains in set-weight tables)
- Alert if:
  - DB write errors occur repeatedly
  - history rows stop increasing despite incoming webhooks
  - disk free space drops below operational threshold

## Troubleshooting Checklist

1. Permissions:
   - Service user can read/write `/var/lib/loadcell-transmitter/data`.
2. Disk full:
   - Check `df -h`; if full, archive/rotate data before retrying writes.
3. SQLite lock contention:
   - Verify no rogue process holds the DB file.
4. Corruption handling:
   - Run `PRAGMA integrity_check;`
   - restore from `.backup` if corruption is detected.
5. Scope mismatch:
   - Confirm payload `line_id` and `machine_id` match expected machine scope.
6. Unit mismatch:
   - Ensure webhook `unit` is one of: `lb`, `kg`, `g`, `oz`.

## Rollback

1. Stop service:
   - `sudo systemctl stop loadcell-transmitter`
2. Restore code to previous release.
3. Restore database backup:
   - `sudo cp /var/lib/loadcell-transmitter/data/app.sqlite3.pre-set-weight-v3.bak /var/lib/loadcell-transmitter/data/app.sqlite3`
   - `sudo chown pi:pi /var/lib/loadcell-transmitter/data/app.sqlite3`
4. Start service:
   - `sudo systemctl start loadcell-transmitter`
5. Validate service and API health.
