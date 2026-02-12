# SD Card Disaster Recovery Runbook

Mission objective: recover from a dead SD card with a repeatable process that captures everything, restores everything, and proves recovery time.

## Scope

This runbook uses two PowerShell scripts in `scripts/`:

- `pull_pi_baseline.ps1`: pulls a full baseline snapshot from the live Pi to this Windows machine.
- `restore_pi_from_baseline.ps1`: restores that baseline onto a fresh flashed Pi over SSH.

The workflow is designed for mission-critical recovery drills and real incidents.

## What Gets Captured

The baseline pull captures all major recovery-critical layers:

- Application code:
  - `/opt/loadcell-transmitter` (default includes `.venv`; optional skip).
  - `/home/pi/hoppers` (legacy path, if present).
- Runtime data:
  - `/var/lib/loadcell-transmitter` (SQLite, runtime state, logs if present).
- Service + OS config:
  - `/etc/systemd/system/loadcell-transmitter.service`.
  - Identity/network snapshot files (`hostname`, `hosts`, `dhcpcd`, `interfaces`, `sshd_config`, `wpa_supplicant` when present).
  - Boot display/config files (`/boot/config.txt`, `/boot/firmware/config.txt` when present).
- Kiosk files:
  - `~/kiosk.sh`, `~/.config/systemd/user/kiosk.service`, desktop/app launchers when present.
- Inventory/report outputs:
  - `systemctl` status/unit output.
  - `journalctl` tail for `loadcell-transmitter`.
  - `i2cdetect` output with fallback path.
  - Package list (`dpkg-query`).
  - Venv package freeze if venv exists.
  - File listings and SHA256 manifests for app/data trees.
  - SQLite integrity check when `sqlite3` is available.

## One-Time Prereqs (Windows Machine)

1. Ensure `plink` and `pscp` are installed and in `PATH`.
2. Run scripts from repo root:
   - `C:\Users\jthompson\Desktop\Scales`
3. Ensure SSH access to Pi works:
   - `plink -pw <password> pi@<ip-or-hostname> "hostname"`

## Phase A - Baseline Pull (Live Pi)

From repo root:

```powershell
.\scripts\pull_pi_baseline.ps1 -PiHost 172.16.190.25 -PiUser pi
```

Optional flags:

- `-SkipVenv` to reduce size and pull time.
- `-JournalLines 4000` for deeper logs.
- `-BackupRoot ".\backups"` to control where artifacts are stored.
- `-KeepRemoteStage` for post-run remote inspection.

Expected output:

- `.\backups\pi-baseline-<host>-<timestamp>\artifacts\...`
- `.\backups\pi-baseline-<host>-<timestamp>\reports\...`

## Phase B - Baseline Validation (Do Not Skip)

In the pulled backup folder, verify:

1. Required artifacts exist:
   - `opt_loadcell_transmitter.tar.gz`
   - `var_lib_loadcell_transmitter.tar.gz`
   - `etc_loadcell_service.tar.gz`
2. `reports/local_artifact_sha256.txt` exists and is non-empty.
3. `reports/systemctl_loadcell_status.txt` shows expected service state.
4. `reports/i2cdetect_bus1.txt` shows expected board addresses.
5. `reports/sqlite_integrity_check.txt` reports `ok` when present.

If any of these fail, pull again before proceeding.

## Phase C - Flash Fresh SD + First Boot

1. Flash fresh Raspberry Pi OS to a new SD card.
2. Complete Pi Connect setup so you can locate/access the Pi quickly.
3. Boot Pi and get reachable host/IP.
4. Confirm SSH works:

```powershell
plink -pw <password> pi@<new-host-or-ip> "hostname && uname -a"
```

## Phase D - Restore to Fresh Pi

Run restore against the backup folder from Phase A:

```powershell
.\scripts\restore_pi_from_baseline.ps1 `
  -BackupPath ".\backups\pi-baseline-<host>-<timestamp>" `
  -PiHost <new-host-or-ip> `
  -PiUser pi
```

Optional restore flags:

- `-SkipAptInstall` if base image already has required packages and you want faster restore.
- `-RestoreIdentityNetwork` to apply identity/network files from backup.
- `-RestoreBootConfig` to apply boot config from backup.
- `-KeepRemoteStage` for remote post-check.

Important:

- `-RestoreIdentityNetwork` can change hostname/network behavior; use only when intentional.
- `-RestoreBootConfig` may require reboot to fully apply display settings.

## Phase E - Post-Restore Verification

1. Service health:

```powershell
plink -pw <password> pi@<host> "sudo systemctl status loadcell-transmitter --no-pager"
```

2. Dashboard reachable:
   - `http://<host>:8080`
3. Hardware visibility:
   - Check dashboard "Boards Online" and live weight updates.
4. Optional direct I2C check:

```powershell
plink -pw <password> pi@<host> "sudo i2cdetect -y 1 || sudo /usr/sbin/i2cdetect -y 1"
```

5. Restore report folder exists locally:
   - `<BackupPath>\restore-reports\restore_reports\`

## Phase F - Timed Recovery Drill

Goal: measure real-world dead-card to running-system time.

Start stopwatch at first action after inserting fresh flashed card:

1. Boot + discover host/IP via Pi Connect.
2. Run `restore_pi_from_baseline.ps1`.
3. Stop timer when:
   - `loadcell-transmitter` is `active (running)`, and
   - dashboard is loading live data at `:8080`.

Record:

- Total minutes.
- Any manual interventions.
- Any errors/warnings from restore reports.
- Improvement actions for next run.

## Artifacts and Reports Layout

Typical backup directory:

- `artifacts/`: compressed snapshots of code/data/config.
- `reports/`: capture-time diagnostics and manifests.
- `restore-reports/restore_reports/`: restore-time diagnostics and status outputs.

## Recovery Philosophy

For this project, the "source of truth" is the live Pi baseline + pulled artifacts, not assumptions in documentation.

Use this process whenever:

- docs may be stale,
- hardware behavior changed,
- site-specific calibration/settings matter,
- downtime risk is unacceptable.
