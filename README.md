# Hoppers Load Cell Scale System

Single startup document for this repo. If a human, Cursor, or OpenClaw session starts cold, begin here.

**Production Pi (LAN):** `172.16.190.25`  
**Production Pi (Tailscale):** `100.114.238.54` / MagicDNS `hoppers.tail840434.ts.net`  
**Dashboard (LAN):** `http://172.16.190.25:8080`  
**Dashboard (Funnel / off-LAN):** `https://hoppers.tail840434.ts.net`  
**Service:** `loadcell-transmitter`  
**Runtime Path:** `/opt/loadcell-transmitter`

Industrial hopper-scale system for Raspberry Pi + Sequent hardware. The product work in this repo covers live weighing, PLC analog output, job-target webhook flow, HDMI operator UI, dump/count tracking, and production rollouts on the Pi.

---

## Start Here

This repo now uses a **git-first, repo-docs-first** workflow.

### One README policy
- `README.md` at repo root is the only README intended as a startup hub.
- Folder-specific orientation docs should use names like `OVERVIEW.md` or `GUIDE.md` instead of more README files.
- If you tell a fresh agent "read the README," this is the file they should read.

### Read these files next, in order
1. `TODO.md`
2. `STATUS.md`
3. `DECISIONS.md`
4. `RUNBOOK.md`
5. `DEPLOY.md`
6. `HANDOFF.md`
7. `OPENCLAW.md` if OpenClaw-specific guidance or cross-project setup guidance is needed

### Working rules
- **Git is the source of truth for implementation**
- **Repo docs are the source of truth for shared project state**
- **Live Pi/runtime state is the source of truth for what is actually deployed**
- Chat context alone is not proof that something is in git or live
- `local` is not the same as `pushed`
- `pushed` is not the same as `staged on Pi`
- `staged on Pi` is not the same as `running live`
- `running live` is not the same as `validated live`
- This line can be in production use; do not restart/reboot/reset the Pi without an approved window

### Fresh-session prompt
Use this when opening a new work area with any agent:

> Read `README.md`, then `TODO.md`, `STATUS.md`, `DECISIONS.md`, `RUNBOOK.md`, `DEPLOY.md`, and `HANDOFF.md`. Report the current branch, current focus, blockers, deploy status, and next recommended step before changing code.

### Recommended work loop
1. Check the current branch and git status
2. Pull the intended branch with a fast-forward-only update
3. Read the coordination docs above
4. Read the specific detailed docs you need under `docs/`
5. Do the work in repo files
6. Update repo docs as state changes
7. Preserve staged-vs-live rollout truth; do not let cleanup work erase staged hopper updates
8. Deploy/apply and validate separately
9. Commit and push when allowed

---

## Shared Project Files

| File | Purpose |
|------|---------|
| `README.md` | single startup hub and repo orientation |
| `TODO.md` | current tasks, next actions, follow-up work |
| `STATUS.md` | current repo/deploy state, blockers, next steps |
| `DECISIONS.md` | durable architectural and workflow decisions |
| `RUNBOOK.md` | how to work in this repo without drifting from reality |
| `DEPLOY.md` | coded vs pushed vs staged vs live vs validated |
| `HANDOFF.md` | concise next-agent handoff |
| `OPENCLAW.md` | OpenClaw operating standard and future-project setup template |

These files should stay current so humans, Cursor, and OpenClaw can all pull the same project state from git.

---

## Project Structure

```text
repo-root/
├── README.md
├── OPENCLAW.md
├── TODO.md
├── STATUS.md
├── DECISIONS.md
├── RUNBOOK.md
├── DEPLOY.md
├── HANDOFF.md
├── docs/                    # detailed product, rollout, hardware, and troubleshooting docs
├── src/                     # application code
├── tests/                   # regression coverage
├── scripts/                 # helper scripts
├── deploy_to_pi/            # file-copy deployment helpers
├── systemd/                 # service unit example
└── .vendor/                 # vendored hardware libraries
```

### Common work areas
- `src/` — Flask app, acquisition loop, hardware, repo layer, output logic
- `tests/` — targeted regression tests for runtime behavior
- `docs/` — detailed runbooks, implementation notes, rollout history, hardware references
- `deploy_to_pi/` — deployment helper copies/scripts for Pi rollout

---

## Detailed Documentation Reference

Start with:
- `docs/OVERVIEW.md` — guide to the documentation set
- `docs/CURRENT_IMPLEMENTATION.md` — detailed implementation/reference snapshot
- `docs/CURRENT_UI_REFERENCE.md` — UI/API surface reference
- `docs/DEPLOYMENT_LOG.md` — rollout history and staged/live notes
- `docs/TODO_BACKLOG.md` — longer backlog and rollout follow-ups

Use these for deeper topic work:
- `docs/JOB_COMPLETION_WEBHOOK_RUNBOOK.md`
- `docs/SET_WEIGHT_PERSISTENCE_RUNBOOK.md`
- `docs/SCALE_IMAGE_PREPARATION_RUNBOOK.md`
- `docs/HDMI_KIOSK_RUNBOOK.md`
- `docs/PLC_OUTPUT_VERIFICATION.md`
- `docs/CalibrationProcedure.md`
- `docs/CALIBRATION_CURRENT_STATE.md`
- `docs/WiringAndCommissioning.md`
- `docs/MaintenanceAndTroubleshooting.md`

---

## Backend / Runtime Reality Rules

### Keep these states separate
- **In git locally**
- **Pushed to remote**
- **Staged on the Pi**
- **Running live on the Pi**
- **Validated live**

They are not the same.

### Source of truth order
1. Live system behavior on the Pi
2. Deployment state recorded in `DEPLOY.md` and `docs/DEPLOYMENT_LOG.md`
3. Implementation in git
4. Detailed docs in `docs/`

### Runtime change rule
If acquisition logic, hardware behavior, job-control behavior, or deployment state changes:
1. Update code/docs
2. Record whether the change is only local, pushed, staged, or live
3. Restart/apply only in an approved production window
4. Validate on the real line
5. Update `STATUS.md`, `DEPLOY.md`, and `HANDOFF.md`

---

## Development Quick Start

### Inspect repo state
```bash
git status --short --branch
git branch --show-current
git pull --ff-only origin <current-branch>
```

### Run local tests
```bash
python -m pytest tests/test_rezero_warning.py tests/test_job_completion_webhook.py tests/test_snapshot_job_control.py
```

### Run app locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.app
```

---

**Last Updated:** 2026-03-16  
**Workflow Version:** Git-first repo handoff model
