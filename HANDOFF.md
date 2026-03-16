# HANDOFF

## Current Handoff

### Repo State
- Repo path: use the current repo root; do not rely on machine-specific absolute paths
- Active branch in this workspace: `cursor/scale-image-preparation-021d`
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
- whether the staged Mar 6 + Mar 16 runtime files have been activated with a restart
- whether completed-job webhook delivery works on a real job transition after restart
- whether basket-dump counts, floor-threshold behavior, and re-zero warning all behave correctly on the live line
- whether the latest documented backup/baseline state matches what should be used for the next clone-image capture

### Current Shared Workflow
- Start with `README.md`, then read the coordination docs it points to
- Use git as source of truth for implementation and project docs
- Keep rollout reality explicit: local vs pushed vs staged vs live vs validated
- Do not lose or blur the already-staged hopper updates while cleaning docs
- Treat the repo itself as the shared project brain for handoff and continuity

### Next Recommended Step
1. Finish the repo cleanup and image-prep runbook consolidation.
2. Push cleanup changes only when explicitly approved.
3. During an approved production window, restart `loadcell-transmitter`.
4. Validate the staged runtime features on the real line.
5. After rollout truth is confirmed, capture a fresh baseline bundle and a current cloneable image.
