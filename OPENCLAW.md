# OPENCLAW

## Purpose

This file defines how OpenClaw should interact with this repo and how future repos should be set up to support the same handoff-friendly workflow.

Use this file as the cross-project standard.

---

## How OpenClaw Should Work In This Repo

### Startup rule
When OpenClaw starts in this repo, it should:

1. Read `README.md`
2. Read `TODO.md`
3. Read `STATUS.md`
4. Read `DECISIONS.md`
5. Read `RUNBOOK.md`
6. Read `DEPLOY.md`
7. Read `HANDOFF.md`
8. Read this file if OpenClaw-specific operating guidance is needed

### Source-of-truth rule
OpenClaw should treat:

- git as the source of truth for implementation
- repo docs as the source of truth for shared project state
- live systems as the source of truth for deployed/runtime state

OpenClaw should not treat chat memory alone as proof that work exists.

### Branch rule
- Work on the branch currently checked out unless explicitly told to switch
- In this repo, shared work should normally land on `main` unless Justin explicitly wants something else
- Do not leave stray local-only branches behind
- Do not hardcode machine-specific absolute paths

### Handoff rule
Before ending meaningful work, OpenClaw should update the repo docs so the next human or agent can continue without guessing.

Minimum docs to keep current:
- `TODO.md`
- `STATUS.md`
- `DECISIONS.md`
- `HANDOFF.md`
- `DEPLOY.md` when rollout state changed

### Deployment rule
OpenClaw should keep these states separate:
- in git locally
- pushed to remote
- staged on Pi
- deployed/running live
- validated live

If backend or runtime work changed, OpenClaw should record what is coded versus what is actually live.

### Production safety rule
- The hopper line may be in active production use
- Do not reboot the Pi or restart `loadcell-transmitter` without an approved window
- If files are only staged onto the Pi, record that clearly and do not claim the feature is live yet

---

## Standard Project Setup For Future Repos

If you want another project to work like this one, create these root files:

- `README.md`
- `OPENCLAW.md`
- `TODO.md`
- `STATUS.md`
- `DECISIONS.md`
- `RUNBOOK.md`
- `DEPLOY.md`
- `HANDOFF.md`

### Required meanings

| File | Required purpose |
|------|------------------|
| `README.md` | single startup hub for all humans and agents |
| `OPENCLAW.md` | OpenClaw operating standard and cross-project setup guide |
| `TODO.md` | current tasks and next actions |
| `STATUS.md` | current branch/state/blockers/next steps |
| `DECISIONS.md` | durable project decisions only |
| `RUNBOOK.md` | standard working procedure |
| `DEPLOY.md` | coded vs pushed vs staged vs live vs validated |
| `HANDOFF.md` | concise next-agent handoff |

### Required repo rules

Every project set up this way should follow these rules:

1. Root `README.md` is the only startup README in the repo
2. Folder-level orientation docs should use names like `OVERVIEW.md` or `GUIDE.md`
3. Shared state must live in git-tracked docs, not only in chat
4. Docs must be branch-aware and path-agnostic
5. Agents should start by reading the root docs before changing code
6. Work is not "done" just because it exists in chat or only in local files

### Recommended root README structure

Each project's root `README.md` should include:

1. project summary
2. startup order for docs
3. working rules
4. fresh-session prompt
5. shared project file table
6. project structure
7. deployment reality rules
8. documentation reference

### Recommended startup prompt

Use this in any new project that follows this model:

> Read `README.md`, then `TODO.md`, `STATUS.md`, `DECISIONS.md`, `RUNBOOK.md`, `DEPLOY.md`, and `HANDOFF.md`. Report the current branch, current focus, blockers, deploy status, and next recommended step before changing code.

### Recommended wrap-up behavior

At the end of meaningful work:

1. update repo docs
2. commit changes
3. push when allowed
4. record what still needs validation
5. leave the next agent a clear first step

---

## What OpenClaw Should Avoid

OpenClaw should avoid:

- assuming a specific branch without checking
- relying on machine-specific paths
- creating alternate startup READMEs
- leaving important status only in chat
- claiming deploy success without validation
- treating local unpushed work as shared team state
- restarting a production line in use without explicit approval

---

## Suggested Copy-Paste Bootstrap For Other Repos

When preparing another repo to work like this one, add the root files above and put this instruction in the new repo's `README.md`:

> This repo uses a git-first, repo-docs-first workflow. Start with `README.md`, then read `TODO.md`, `STATUS.md`, `DECISIONS.md`, `RUNBOOK.md`, `DEPLOY.md`, `HANDOFF.md`, and `OPENCLAW.md` if OpenClaw-specific guidance is needed.

Then make sure:

- the repo has only one startup README
- the handoff docs mention the active branch, not a hardcoded one
- the docs avoid local machine paths
- the next agent can start cold with no chat history

---

## Bottom Line

OpenClaw should use this repo the same way a careful human teammate would:

- start from the root docs
- trust git and live systems over memory
- keep shared state written down
- leave the repo easier for the next agent than it found it
