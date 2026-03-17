# DEPLOY

## Production target
- **Pi:** `172.16.190.25`
- **Tailscale/Funnel URL:** `https://hoppers.tail840434.ts.net`
- **Dashboard:** `http://172.16.190.25:8080`
- **Service:** `loadcell-transmitter`
- **Runtime path:** `/opt/loadcell-transmitter`

---

## Deployment reality

Keep these states separate for every change:

1. **in git locally**
2. **pushed to remote**
3. **staged on Pi**
4. **running live**
5. **validated live**

A copied file is not live until the service is restarted. A restarted service is not validated until the changed behavior is checked on the real line.

---

## Current rollout matrix

| Change | In git locally | Pushed | Staged on Pi | Running live | Validated live | Notes |
|------|---|---|---|---|---|---|
| Job-target webhook cutover + HDMI target UI | Yes | Yes | Yes | Yes | Yes | Live baseline from Feb 27 rollout |
| Completed-job webhook lifecycle/outbox | Yes | Yes | Yes | No | No | Requires approved restart to activate staged runtime |
| Configurable floor threshold / legacy floor signal | Yes | Yes | Yes | No | No | Staged on Pi Mar 6; restart pending |
| Basket-dump counted events | Yes | Yes | Yes | No | No | Staged on Pi Mar 6; restart pending |
| Between-jobs re-zero warning + webhook diagnostics | Yes | Yes | Yes | No | No | Staged on Pi Mar 16; restart pending |
| Repo cleanup + image-prep readiness docs | Yes | No | N/A | N/A | N/A | Current cleanup pass; push later only with explicit approval |

---

## Current production picture

### Known live baseline
- Public job webhook path and target-mode workflow are live
- HDMI job-target UI is live
- Production line is active enough that restart/reboot must be treated carefully

### While the line is in use
- Safe work is limited to no-restart prep: docs, backend alignment, and approved-window checklist preparation.
- Do not treat staged runtime files as live behavior until `loadcell-transmitter` is restarted and validated on the real line.
- Use `docs/APPROVED_WINDOW_CHECKLIST.md` as the single restart-window checklist once maintenance begins.

### Known staged-but-not-active work
The following have been copied to the production runtime path but are still inactive until `loadcell-transmitter` is restarted in an approved window:
- completed-job webhook lifecycle/outbox changes
- configurable floor threshold + legacy floor signal behavior
- basket-dump counted-event support
- between-jobs re-zero warning + completed-job diagnostic additions

### Current cleanup rule
- Documentation cleanup must not erase or flatten the staged hopper rollout history.
- If repo docs are updated before the next approved restart, they should continue to show those hopper changes as **staged, not live**.
- GitHub push for the cleanup/docs work is intentionally deferred until explicitly approved.

---

## Next approved-window checklist

Primary checklist: `docs/APPROVED_WINDOW_CHECKLIST.md`

1. Restart `loadcell-transmitter`
2. Confirm service is healthy after restart
3. Validate between-jobs re-zero warning behavior
4. Validate floor threshold + legacy floor signal behavior in Settings/runtime
5. Validate basket-dump opto counting
6. Validate completed-job webhook payload and outbox delivery on a real job transition
7. Update this file plus `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md`

---

## Reporting rule

Do not collapse these into one statement:
- "coded"
- "pushed"
- "staged"
- "live"
- "validated"

This repo should always say exactly which of those are true.
