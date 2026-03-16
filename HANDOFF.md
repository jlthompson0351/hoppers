# HANDOFF

## Current Handoff

### Repo State
- Repo path: use the current repo root; do not rely on machine-specific absolute paths
- Active branch in this workspace: `main`
- Current pulled HEAD before this local standardization pass: `0b53d28`
- Working tree now also includes uncommitted root-doc standardization changes

### What Exists In Git
- between-jobs re-zero warning work and rollout docs on `main`
- configurable floor threshold / legacy floor signal work
- completed-job webhook lifecycle + outbox support
- basket-dump counted events support
- HDMI override and job-target workflow updates

### What Exists Locally In This Session
- root coordination docs were added to align this repo with the Supabase-style setup:
  - `README.md`
  - `OPENCLAW.md`
  - `TODO.md`
  - `STATUS.md`
  - `DECISIONS.md`
  - `RUNBOOK.md`
  - `DEPLOY.md`
  - `HANDOFF.md`
- `docs/README_DOCS.md` was renamed to `docs/OVERVIEW.md`
- references need to use `OVERVIEW.md` instead of the old name

### What Still Needs Reality Check
- whether the current-session doc standardization should be committed/pushed now
- whether the staged Mar 6 + Mar 16 runtime files have been activated with a restart
- whether completed-job webhook delivery works on a real job transition after restart
- whether basket-dump counts, floor-threshold behavior, and re-zero warning all behave correctly on the live line

### Current Shared Workflow
- Start with `README.md`, then read the coordination docs it points to
- Use git as source of truth for implementation and project docs
- Keep rollout reality explicit: local vs pushed vs staged vs live vs validated
- Treat the repo itself as the shared project brain for handoff and continuity

### Next Recommended Step
1. If Justin wants the new repo-doc structure shared now, commit and push these root-doc changes
2. Restart `loadcell-transmitter` during an approved production window
3. Validate the staged runtime features on the real line
4. Update `DEPLOY.md`, `STATUS.md`, `HANDOFF.md`, and `docs/DEPLOYMENT_LOG.md` immediately after validation
