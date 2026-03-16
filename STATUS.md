# STATUS

## Repo
- Branch in this workspace: `main`
- Current pulled HEAD before this local doc-normalization pass: `0b53d28`
- Workspace path is environment-specific; use the current repo root instead of hardcoded absolute paths
- Verify sync state with `git status --short --branch`

## Current Focus
1. Standardize this repo to the same root-doc workflow used in the Supabase repo
2. Keep rollout reality clear for the staged-but-not-yet-live hopper features
3. Prepare for the next approved production restart/validation window

## Latest Pulled State
- `origin/main` includes the between-jobs re-zero warning rollout docs and tests
- Earlier main-branch work already includes:
  - configurable floor threshold
  - completed-job webhook/outbox support
  - basket-dump counted events
  - HDMI override and job-target workflow updates

## Current Session Changes
- Root coordination files were added to match the shared project setup:
  - `README.md`
  - `OPENCLAW.md`
  - `TODO.md`
  - `STATUS.md`
  - `DECISIONS.md`
  - `RUNBOOK.md`
  - `DEPLOY.md`
  - `HANDOFF.md`
- `docs/README_DOCS.md` was renamed to `docs/OVERVIEW.md` so root `README.md` stays the single startup README
- Reference links are being aligned to the new `OVERVIEW.md` name

## Deploy Status
- Local code is aligned with `origin/main` for product/runtime work at `0b53d28`
- Production Pi still needs an approved restart before the Mar 6 and Mar 16 staged runtime changes become active
- Live validation is still pending for:
  - between-jobs re-zero warning
  - configurable floor threshold / legacy floor signal
  - basket-dump counted events
  - completed-job webhook diagnostics on real job transitions

## Current Blockers
- Need an approved restart window because the line may be in active use
- Need live validation on the real line after restart
- Need this repo-doc standardization committed/pushed before it becomes shared state for other workspaces

## Next Steps
1. Review and commit/push the new root-doc workflow if Justin wants it shared now
2. Restart `loadcell-transmitter` during an approved window
3. Validate the staged runtime features on the real line
4. Update `DEPLOY.md`, `STATUS.md`, and `HANDOFF.md` immediately after validation

## Working Rule
Git is the source of truth for implementation, repo docs are the source of truth for shared project state, and the running Pi is the source of truth for what is actually live.
