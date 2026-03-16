# Scale Image Preparation Runbook

Use this runbook when the goal is **not just recovery**, but preparing the current working hopper scale so another SD card / another Pi can be built from it safely.

This workflow is intentionally separate from a normal deployment or a normal disaster-recovery restore.

---

## Goal

Create a trustworthy, repeatable path for turning the current Hoppers system into a reusable build source for another scale.

That means capturing **both**:

1. a **structured baseline pull** for recovery, inspection, and state scraping
2. a **full cloneable image** for flashing another SD card

---

## Before You Start

Do **not** assume the live Pi, the repo, and the staged runtime files are all in the same state.

First verify:

1. what is live on the Pi
2. what is only staged on the Pi
3. what is in git locally
4. what has or has not been pushed yet

Use:

- `DEPLOY.md`
- `STATUS.md`
- `HANDOFF.md`
- `docs/DEPLOYMENT_LOG.md`
- `docs/TODO_BACKLOG.md`

If those disagree, fix the docs first before imaging anything.

---

## Recommended Workflow

### Phase 1 — Repo truth cleanup

Before touching the Pi:

1. Clean up repo docs so they accurately show:
   - live baseline
   - staged-but-not-live runtime updates
   - pending restart/validation work
2. Do **not** flatten staged changes into "live".
3. Do **not** claim image-readiness until rollout truth is clear.

---

### Phase 2 — Pi state scrape / settings refresh

When remote access is available:

1. Use **Desktop Commander** to launch `plink`-based commands from the desktop side.
2. Pull current evidence from the Pi:
   - hostname / OS info
   - service status
   - recent `journalctl` output
   - current SQLite-backed config snapshot
   - deployment/runtime file timestamps if needed
3. Compare what the Pi shows against:
   - `DEPLOY.md`
   - `docs/DEPLOYMENT_LOG.md`
   - the latest snapshot/baseline docs

Goal:

- confirm whether the Mar 5 / Mar 6 / Mar 16 runtime updates are still only staged or have actually been restarted/live

---

### Phase 3 — Approved production window

If the desired clone image should include the staged hopper updates, you need an approved restart/validation window.

During that window:

1. restart `loadcell-transmitter`
2. verify service health
3. validate:
   - completed-job webhook lifecycle/outbox
   - floor threshold / legacy floor signal behavior
   - basket-dump counting
   - between-jobs re-zero warning
4. update:
   - `DEPLOY.md`
   - `STATUS.md`
   - `HANDOFF.md`
   - `docs/DEPLOYMENT_LOG.md`

If no approved restart happens, the future image should be documented as matching the currently live baseline, not the staged files.

---

### Phase 4 — Capture a fresh structured baseline

Run the baseline capture first, even if the final goal is a full image.

Use:

- `scripts/pull_pi_baseline.ps1`
- `docs/SD_CARD_DISASTER_RECOVERY_RUNBOOK.md`

Why this matters:

- it captures app/data/config in a reviewable structure
- it preserves service files, kiosk files, network/identity snapshots, and SQLite backups
- it gives you reports you can inspect before trusting a full image

Baseline output should include:

- application tree snapshot
- `/var/lib/loadcell-transmitter` snapshot
- service unit snapshot
- network/identity artifacts
- boot/display artifacts
- kiosk artifacts
- SQLite backup + integrity outputs
- manifests/checksums

---

### Phase 5 — Capture a full cloneable image

After the baseline pull is complete and reviewed, capture a full SD-card-style image.

The repo’s current reference approach is the RonR `image-backup` workflow documented in:

- `.cursor/skills/pi-backup/SKILL.md`

Expected output:

- a `.img` file that can be flashed directly onto a new SD card

Record with the image:

1. file path
2. capture date
3. whether it reflects:
   - the currently live baseline only, or
   - the live baseline plus validated Mar 5/6/16 updates
4. checksum
5. any follow-up steps required after flashing

---

## Baseline Pull vs Full Image

### Use a baseline pull when you need:

- human-readable recovery artifacts
- SQLite/config inspection
- service/config auditing
- a restore path that can target a fresh Pi over SSH

### Use a full image when you need:

- an exact SD-card clone
- the fastest path to build another identical unit
- a flashable image for bench prep

### Best practice

Do both.

The structured baseline tells you **what** you captured.
The full image lets you **recreate** it quickly.

---

## Clone Safety Checklist

When flashing a full image onto a **new** Pi for an additional scale, assume the image contains machine identity from the source device.

Review and adjust as needed:

### 1. Host identity

- hostname
- network identity files
- SSH host keys if your process requires regeneration

### 2. Raspberry Pi Connect identity

If this is a brand-new second Pi, not a straight hardware replacement:

- sign out / re-register Pi Connect as needed

### 3. Tailscale identity

If the source system is already enrolled in Tailscale:

- avoid duplicate node identity
- re-auth / rename the cloned node as needed

### 4. Site-specific machine identifiers

Review app/runtime config for values that should remain unique per installation, such as:

- line / machine scope values used by webhook flows
- any future hopper or device IDs
- backend endpoint or token settings if they should differ by site

### 5. Calibration / physical fit

A clone image copies software state, not physical calibration truth.

Before production use on the new unit:

- confirm wiring matches
- confirm board addresses match
- confirm display rotation/touch behavior matches
- verify calibration still corresponds to the physical hopper/load-cell hardware

---

## Documentation Updates Required After Capture

After a new baseline or image is created, update:

- `docs/FLEET_INVENTORY.md`
- `docs/TODO_BACKLOG.md`
- `STATUS.md`
- `HANDOFF.md`
- `DEPLOY.md` if rollout truth changed before capture

Record:

- artifact location
- date
- whether it is baseline-only or full image
- checksum
- whether it reflects staged changes or validated live changes

---

## Minimum Evidence Before Saying "Ready to Clone"

Do not say the scale is ready to clone until you can point to:

1. clean repo/docs truth
2. clear live vs staged status
3. a fresh structured baseline pull
4. a full image artifact
5. documented post-clone identity steps

Without all five, the system is only **partially** prepared.
