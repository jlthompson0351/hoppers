# RUNBOOK

## Purpose

Use this file to work in this repo without drifting away from git reality or live-line reality.

---

## Standard startup procedure

1. Check repo state:
   ```bash
   git status --short --branch
   git branch --show-current
   ```
2. Pull the intended branch with a fast-forward-only update.
   - Use the branch you are actually working on:
     ```bash
     git pull --ff-only origin <current-branch>
     ```
3. Read the root coordination docs in this order:
   - `README.md`
   - `TODO.md`
   - `STATUS.md`
   - `DECISIONS.md`
   - `RUNBOOK.md`
   - `DEPLOY.md`
   - `HANDOFF.md`
4. Read `OPENCLAW.md` if you need the cross-project/OpenClaw operating standard.
5. Read only the detailed docs needed for the task, usually starting with `docs/OVERVIEW.md`.

---

## Working rules

### Keep states separate
Always distinguish between:
- local code/docs
- pushed remote state
- staged-on-Pi files
- running live service state
- validated live behavior

### Be branch-aware
- Check the actual checked-out branch before changing files.
- Shared work should normally stay on `main` unless Justin explicitly asks otherwise.
- Do not leave local-only branches hanging around as invisible project state.

### Keep root docs current
If the task changes repo state, blockers, rollout state, or next steps, update:
- `TODO.md`
- `STATUS.md`
- `DEPLOY.md`
- `HANDOFF.md`
- `DECISIONS.md` if a durable choice changed

When cleaning docs, preserve the existing staged rollout history instead of flattening it into "live" or "done".

---

## Detailed-doc entry points

Use these depending on the task:

- `docs/OVERVIEW.md` — docs index
- `docs/CURRENT_IMPLEMENTATION.md` — detailed implementation behavior
- `docs/CURRENT_UI_REFERENCE.md` — UI/API reference
- `docs/DEPLOYMENT_LOG.md` — historical rollout record
- `docs/APPROVED_WINDOW_CHECKLIST.md` — approved restart-window activation + validation steps
- `docs/TODO_BACKLOG.md` — long-form backlog and staged rollout notes
- `docs/JOB_COMPLETION_WEBHOOK_RUNBOOK.md` — completed-job webhook flow
- `docs/SET_WEIGHT_PERSISTENCE_RUNBOOK.md` — set-weight persistence / lifecycle storage
- `docs/HDMI_KIOSK_RUNBOOK.md` — kiosk behavior
- `docs/PLC_OUTPUT_VERIFICATION.md` — PLC output test guidance
- `docs/CalibrationProcedure.md` and `docs/CALIBRATION_CURRENT_STATE.md` — calibration behavior

---

## When changing runtime code

1. Change the smallest correct set of files.
2. Run targeted tests for the touched behavior.
3. If job-control / warning / snapshot behavior changed, prefer focused regression tests.
4. Update rollout docs if the live activation story changed.

Typical targeted test examples:
```bash
python -m pytest tests/test_rezero_warning.py tests/test_job_completion_webhook.py tests/test_snapshot_job_control.py
python -m pytest tests/test_target_signal_mode.py tests/test_throughput_guard.py tests/test_counted_events.py
```

---

## When changing deployment state

### Before claiming something is live
- Confirm whether the change is only local, pushed, or merely staged on the Pi.
- If a restart has not happened, the feature is not live yet.

### Production safety rule
- Do not restart `loadcell-transmitter`, reboot the Pi, or disrupt the line without an approved window.
- If files are copied while production continues, record them as staged only.

### After an approved rollout
1. Use `docs/APPROVED_WINDOW_CHECKLIST.md`
2. Restart service once
3. Verify service health
4. Verify the changed UI/runtime behavior on the real line
5. Verify any webhook/outbox behavior with real payloads if relevant
6. Update `DEPLOY.md`, `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md`

---

## Wrap-up checklist

Before ending meaningful work:
- [ ] repo docs updated
- [ ] deploy status recorded accurately
- [ ] blockers and next step written down
- [ ] changes committed if requested
- [ ] pushed if requested/allowed
- [ ] live validation status clearly separated from coding status
