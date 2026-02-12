---
name: pi-backup
description: Performs a live, full-system clone of a remote Raspberry Pi using RonR's image-backup utility.
---

# Raspberry Pi Backup Skill

## Description
Performs a live, full-system clone of a remote Raspberry Pi using RonR's `image-backup` utility. This creates a standard `.img` file that can be flashed to any SD card to restore the system to this exact state.

## Prerequisites
1.  **SSH Access**: You must have SSH access to the Pi (e.g., `ssh pi@192.168.1.x`).
2.  **Tool Installed**: The `image-backup` utility must be installed on the Pi.

## CRITICAL EXECUTION RULE
**You MUST use the `user-desktop-commander-start_process` and `user-desktop-commander-interact_with_process` tools for ALL terminal commands (SSH, rsync, etc.).**
**DO NOT use the standard `Shell` tool.**

## Workflow

### Phase 1: Setup & Verification
If the user hasn't confirmed the tool is installed, guide them:

1.  **Check for Tool**:
    Use Desktop Commander to run:
    ```bash
    ssh user@pi-ip "which image-backup"
    ```
2.  **Install (if missing)**:
    Tell the user to run these commands on the Pi (or run them via Desktop Commander if interactive SSH is established):
    ```bash
    sudo apt-get install git -y
    git clone https://github.com/seamusdemora/RonR-RPi-image-utils.git
    cd RonR-RPi-image-utils
    sudo install image-backup /usr/local/sbin/
    ```

### Phase 2: Execute Backup
Once setup is confirmed, perform the backup.

1.  **Define Variables**:
    - Ask for the Pi's IP address/Hostname.
    - Ask for the backup destination on the local machine (default: `./backups/`).

2.  **Run Remote Backup**:
    - *Note: It is faster to back up to a mounted USB drive on the Pi, but if that's not available, we back up to a temporary file on the Pi and pull it.*
    - Use Desktop Commander to run:
      ```bash
      ssh user@pi-ip "sudo image-backup --initial /tmp/scale-project-backup.img"
      ```
    - *Warn the user this may take 15-30 minutes.*

3.  **Download Image**:
    - Use Desktop Commander to run `rsync` to pull the image to the local machine:
      ```bash
      rsync -avz --progress user@pi-ip:/tmp/scale-project-backup.img ./backups/scale-project-backup-$(date +%Y%m%d).img
      ```

4.  **Cleanup**:
    - Delete the temp file on the Pi to free space (Use Desktop Commander):
      ```bash
      ssh user@pi-ip "sudo rm /tmp/scale-project-backup.img"
      ```

### Phase 3: Validation
1.  **Check Size**: Verify the downloaded file exists and has a reasonable size (e.g., >1GB) using Desktop Commander file tools.
2.  **Report**: 
    - "Backup complete. Saved to `./backups/scale-project-backup-[DATE].img`."
    - "You can flash this file to a new SD card using Raspberry Pi Imager."
    - "**Note on Pi Connect**: This image contains your device identity. If you flash this to a *new* Pi (to add a second device), run `rpi-connect signout` then `rpi-connect signin` to generate a new ID. If you are just replacing a broken Pi, you don't need to do anything."
