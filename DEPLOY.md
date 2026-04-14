# DEPLOY

## Production target
- **Pi (plant LAN):** `172.16.190.25`
- **Pi (Tailscale IPv4):** `100.114.238.54`
- **Pi (MagicDNS):** `hoppers` / `hoppers.tail840434.ts.net`
- **Dashboard (LAN):** `http://172.16.190.25:8080`
- **Dashboard (Tailscale Funnel, HTTPS):** `https://hoppers.tail840434.ts.net`
- **SSH (off-site, tailnet):** `pi@100.114.238.54` or `pi@hoppers.tail840434.ts.net` (same user as LAN; use your usual Pi password)
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
| `receive-scale-webhook`: flip status→processed after sync | Yes | No | N/A | No | No | File at `supabase/functions/receive-scale-webhook/index.ts`; needs `supabase login` then `supabase functions deploy` |
| `process-job-event`: add all v2 fields to scale sync | Yes | No | N/A | No | No | File at `supabase/functions/process-job-event/index.ts`; needed for basket_cycle_count/hopper_load_times etc to reach completed_jobs |
| Backfill 42 stale `pending` rows → `processed` | N/A | N/A | N/A | Yes | Yes | SQL ran live 2026-03-26; all 42 rows now processed |
| Fill detection fixes (full_stability_s=5.0, empty_confirm_s=2.0, full_pct_of_target=0.80, zero artifact suppression, fill outlier filtering) | Yes | Yes | Yes | Yes | Yes | Staged before service restart 22:28 EDT Apr 10; verified live Apr 11 — 21 BASKET_DUMP events observed |
| `patch_throughput_config.py` — write throughput config to DB | Yes | Yes | Yes | Yes | Yes | Ran Apr 11; full_pct_of_target=0.80 now in DB; full_stability_s and empty_confirm_s already at target |
| v2 webhook schema (new Pi firmware) | Yes | Pending | Yes | No | No | Staged on Pi; requires `loadcell-transmitter` restart before v2 payload is live |
| Job-target webhook cutover + HDMI target UI | Yes | Yes | Yes | Yes | Yes | Live baseline from Feb 27 rollout |
| Completed-job webhook lifecycle/outbox | Yes | Yes | Yes | Yes | Yes | Verified live Mar 17 via PLP6 outbox row `60` and backend replay acceptance |
| Configurable floor threshold / legacy floor signal | Yes | Yes | Yes | Yes | No | Runtime appears live, but floor-threshold behavior still needs explicit line validation |
| Basket-dump counted events | Yes | Yes | Yes | Yes | No | `basket_dump_count` field observed live; non-zero opto-count validation still pending |
| Between-jobs re-zero warning + webhook diagnostics | Yes | Yes | Yes | Yes | No | Expanded fields observed live; true warning case still needs validation |
| Smaller stable-drift capture for re-zero warning | Yes | Pending | Yes | No | No | Staged on Pi Mar 18; needs restart before real-line warning behavior can be checked |
| HDMI tare removal + tare-source tracing | Yes | Pending | Yes | No | No | HDMI tare controls removed and source logging added; requires restart and event validation |
| HDMI enlarged bottom controls | Yes | Pending | Yes | No | No | Latest `ZERO` / `CLEAR ZERO` / `OVERRIDE` layout copied to Pi Mar 18 |
| Repo cleanup + image-prep readiness docs | Yes | Yes | N/A | N/A | N/A | Current cleanup pass pushed to `main` |

---

## Current production picture

### Known live baseline
- Public job webhook path and target-mode workflow are live
- HDMI job-target UI is live
- Production line is active enough that restart/reboot must be treated carefully

### While the line is in use
- Safe work can include read-only Pi verification, backend alignment, and documentation updates.
- Do not treat unverified behavior as complete just because the expanded runtime is now visible live on the Pi.
- Use `docs/APPROVED_WINDOW_CHECKLIST.md` as the single restart-window checklist once maintenance begins.

### Verified live observation (Mar 17, 2026)
- `PLP6` completed-job outbox row `60` was created and marked `sent` at `2026-03-17T23:08:27+00:00` for job `1704584`.
- The stored live payload included `basket_dump_count` plus the expanded re-zero diagnostic fields.
- Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200` for all 5 requests; 4 stored successfully and 1 was correctly treated as a duplicate.

### Known live-but-not-fully-validated work
The following now appear to be live on production, but still need remaining line validation:
- configurable floor threshold + legacy floor signal behavior
- basket-dump counted-event support with non-zero pulse verification
- between-jobs re-zero warning behavior when a true warning condition occurs

### Staged-on-Pi but not yet live (Mar 18, 2026)
The following have been copied into `/opt/loadcell-transmitter` but still require a service restart before they can run:
- smaller stable-drift capture for the between-jobs re-zero warning path
- HDMI tare removal from the operator UI
- tare event/source tracing to distinguish web/API versus opto-triggered tare
- enlarged HDMI bottom touch controls for `ZERO`, `CLEAR ZERO`, and `OVERRIDE`

### Current cleanup rule
- Documentation cleanup must not erase or flatten the staged hopper rollout history.
- Repo docs should now show the completed-job runtime as live where verified, and keep the remaining unverified behavior clearly marked as pending.
- The current cleanup/docs pass is now pushed to `main`; future pushes still require explicit approval.

---

## Next approved-window checklist

Primary checklist: `docs/APPROVED_WINDOW_CHECKLIST.md`

1. Restart `loadcell-transmitter`
2. Confirm service is healthy after restart
3. Validate between-jobs re-zero warning behavior, including smaller stable-drift capture expectations
4. Validate floor threshold + legacy floor signal behavior in Settings/runtime
5. Validate basket-dump opto counting
6. Validate that HDMI no longer exposes tare and that the enlarged touch controls fit/behave correctly
7. Validate completed-job webhook payload and outbox delivery on a real job transition
8. Review tare-related events to confirm whether any future unexpected tare comes from web/API requests or opto input
9. Update this file plus `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md`

---

## Reporting rule

Do not collapse these into one statement:
- "coded"
- "pushed"
- "staged"
- "live"
- "validated"

This repo should always say exactly which of those are true.
