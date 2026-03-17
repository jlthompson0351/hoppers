# Approved Window Checklist

## Scope

Use this only during an approved maintenance window when the line can tolerate one service restart.

This checklist covers activation and validation of the staged:

- completed-job webhook lifecycle/outbox updates
- basket-dump counted events
- configurable floor threshold / legacy floor signal behavior
- between-jobs re-zero warning and completed-job diagnostics

## Do Not Start Unless

- the line is not actively depending on the running scale service
- backend is ready to accept both old and new completed-job payload shapes during cutover
- the operator knows one restart of `loadcell-transmitter` is planned

## Activation Steps

1. Restart `loadcell-transmitter` once.
2. Confirm the service is healthy before testing any runtime behavior.
3. Confirm the app is serving normally before starting a real job transition test.

## Live Validation

### Completed-Job Webhook

1. Run a normal job transition so one completed-job payload is generated.
2. Verify the payload reaches the backend successfully.
3. Verify the payload contains:
   - `basket_dump_count`
   - `rezero_warning_seen`
   - `rezero_warning_reason`
   - `rezero_warning_weight_lbs`
   - `rezero_warning_threshold_lbs`
   - `post_dump_rezero_applied`
   - `post_dump_rezero_last_apply_utc`
4. Verify backend uses `job_end_record_time_set_utc` as the analytic completion time.
5. Verify duplicate delivery, if it occurs, is treated as a success-path idempotent replay rather than an error.

### Basket Dump Counting

1. In Settings > Buttons, map the intended MegaIND opto input to `Basket Dump Count`.
2. Pulse the PLC signal and verify counts increment once per rising edge.
3. Close a job transition and verify the completed-job payload reports the expected `basket_dump_count`.

### Floor Threshold / Legacy Floor Signal

1. Open Settings and verify `Floor Threshold` is visible and persists.
2. In Job Target Signal mode, verify `0.0 lb` is accepted.
3. In Legacy Weight Mapping mode, verify the PLC output holds the configured floor signal at or below the floor threshold.

### Re-Zero Warning

1. Run a completed dump/cycle and let the scale settle empty before the next job.
2. Verify the warning only appears when stable zero-relative weight exceeds the configured threshold.
3. Press `ZERO` and verify the warning clears.
4. Verify the next completed-job payload includes the expected warning/re-zero diagnostic fields.

## Post-Restart Proof

Do not mark these features live until all of the following are true:

- service restarted successfully
- service stayed healthy after restart
- webhook payload observed on a real job transition
- `basket_dump_count` validated live
- floor-threshold behavior validated live
- re-zero warning behavior validated live

## Documentation After Validation

After successful validation, update:

- `DEPLOY.md`
- `STATUS.md`
- `HANDOFF.md`
- `docs/DEPLOYMENT_LOG.md`
- `docs/TODO_BACKLOG.md`
