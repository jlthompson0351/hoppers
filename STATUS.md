# STATUS

## Repo
- Branch in this workspace: `cursor/scale-image-preparation-021d`
- Product/runtime rollout truth still comes from the tracked docs and deployment history, not from branch name alone.
- Workspace path is environment-specific; use the current repo root instead of hardcoded absolute paths.
- Verify sync state before any future push or deploy.

## Current Focus
1. Clean up repo/docs so the written project state matches reality.
2. Preserve the staged-but-not-yet-live hopper updates and keep them clearly separated from live runtime state.
3. Prepare the repo for a later agent-assisted Pi sync/settings scrape and image-preparation pass.

## Latest Known Product State
- The repo already contains the between-jobs re-zero warning rollout docs and tests.
- Earlier tracked work already includes:
  - configurable floor threshold
  - completed-job webhook/outbox support
  - basket-dump counted events
  - HDMI override and job-target workflow updates

## Current Cleanup Pass
- Root coordination docs are being reconciled so they no longer contradict the actual workspace branch or rollout state.
- Duplicate/stale documentation entry points are being consolidated.
- Remote-ops guidance is being cleaned up so future Cursor/OpenClaw Pi access can follow the Desktop Commander-first rules.
- This cleanup should not overwrite or erase the already-staged hopper runtime updates that still need later rollout validation.

## Deploy Status
- Product/runtime work for the hopper updates is already documented in git and in the deployment log.
- Production Pi still needs an approved restart before the Mar 6 and Mar 16 staged runtime changes become active
- Live validation is still pending for:
  - between-jobs re-zero warning
  - configurable floor threshold / legacy floor signal
  - basket-dump counted events
  - completed-job webhook diagnostics on real job transitions
- Current cleanup work is documentation/process work; it should not be treated as live Pi activation.

## Current Blockers
- Need an approved restart window because the line may be in active use
- Need live validation on the real line after restart
- GitHub push is intentionally deferred unless explicitly approved
- Need a clean, consistent image-preparation runbook before the later clone-image workflow

## Next Steps
1. Finish the repo cleanup without disturbing the staged hopper rollout history.
2. During a later approved window, restart `loadcell-transmitter`.
3. Validate the staged runtime features on the real line.
4. After validation, update `DEPLOY.md`, `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md`.
5. After rollout truth is confirmed, capture a fresh baseline bundle and a current cloneable image.

## Working Rule
Git is the source of truth for implementation, repo docs are the source of truth for shared project state, and the running Pi is the source of truth for what is actually live.
