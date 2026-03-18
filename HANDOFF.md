# HANDOFF

## Current Handoff

### Repo State
- Repo path: use the current repo root; do not rely on machine-specific absolute paths
- Active branch in this workspace: `main`
- Current work is a cleanup/reconciliation pass over docs, runbooks, and handoff guidance.
- Treat the deployment docs as the source of truth for staged/live runtime state.

### What Exists In Git
- between-jobs re-zero warning work and rollout docs
- configurable floor threshold / legacy floor signal work
- completed-job webhook lifecycle + outbox support
- basket-dump counted events support
- HDMI override and job-target workflow updates
- The deployment history for those changes already exists and should be preserved during cleanup.

### What This Cleanup Pass Is Doing
- Reconciling root coordination docs so they match the actual workspace branch and current project reality.
- Consolidating duplicate/stale documentation entry points.
- Cleaning up future agent-operating guidance for Pi access, staged rollout tracking, and image preparation.
- Preserving the distinction between:
  - code/docs in git
  - anything pushed later
  - files already staged on the Pi
  - what is actually live after restart/validation

### What Still Needs Reality Check
- the exact production restart/activation moment that made the Mar 6 + Mar 16 runtime live
- whether basket-dump counts, floor-threshold behavior, and re-zero warning all behave correctly on the live line
- whether the latest documented backup/baseline state matches what should be used for the next clone-image capture
- whether Hopper's current completed-job payload shape fully matches the next frontend machine-kiosk metrics brief

### What Was Confirmed Live
- On 2026-03-17, Pi DB inspection over Tailscale confirmed completed-job webhook/outbox runtime is live for `PLP6`.
- Outbox row `60` for job `1704584` was marked `sent` at `2026-03-17T23:08:27+00:00`.
- That live payload included `basket_dump_count` plus the expanded re-zero diagnostic fields.
- Replay of the last 5 real Pi completed-job payloads to the backend webhook returned HTTP `200` for all requests; 4 stored and 1 duplicate was ignored correctly.

### Cross-Project Frontend Brief
- The next planned frontend change is on the public per-machine kiosk page.
- Frontend wants to preserve the pinned active job card and add compact recent-completed-job cards below it.
- Hopper's role is to remain the upstream source/runtime for machine/job completion metrics such as:
  - average basket weight
  - final set weight
  - final set weight unit
  - average cycle time
  - basket dump count
  - explicit re-zero warning and post-dump re-zero diagnostics
- Supabase mirrors the relevant fields into `completed_jobs`, and the frontend will consume them from there.
- Keep this contract visible in repo docs so future agents do not treat Hopper as an isolated scale app.

### Current Shared Workflow
- Start with `README.md`, then read the coordination docs it points to
- Use git as source of truth for implementation and project docs
- Keep rollout reality explicit: local vs pushed vs staged vs live vs validated
- Do not lose or blur the already-staged hopper updates while cleaning docs
- Treat the repo itself as the shared project brain for handoff and continuity

### Next Recommended Step
1. Keep rollout truth current as more live observations come in.
2. While the line is in use, continue read-only verification and backend/doc alignment as needed.
3. During an approved production window, use `docs/APPROVED_WINDOW_CHECKLIST.md` to validate the remaining floor-threshold, basket-dump, and re-zero-warning behavior on the real line.
4. After that validation, update the root coordination docs and deployment log again.
5. After rollout truth is confirmed, capture a fresh baseline bundle and a current cloneable image.
