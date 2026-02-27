---
name: ssh-fleet-manager
description: Safely connects to remote devices (Raspberry Pi/Linux) using Desktop Commander. Handles authentication, command execution, and log retrieval.
---

# SSH Fleet Manager

This skill provides a robust, safe way to interact with remote devices without using raw shell commands.
It uses `Desktop Commander` to manage the SSH session, ensuring stability and preventing "Access Denied" errors.

## Workflow

### 1. Identify Target
*   Ask the user for the target IP address if not provided.
*   Check for stored credentials (e.g., in `.env` or a secure config file).
*   **Default Credentials:** User: `pi`, Password: `raspberry` (or ask user).

### 2. Connect via Desktop Commander
*   **DO NOT** run `ssh` or `plink` directly in the `Shell` tool.
*   **USE** `user-desktop-commander-start_process` with the command:
    `plink -ssh -pw [PASSWORD] [USER]@[IP] "[COMMAND]"`
    *(Note: On Windows, `plink` is preferred for automation. Ensure it's in the PATH or use the full path to `plink.exe`)*

### 3. Execute Commands
*   For simple commands (e.g., `ls`, `cat`), run them directly via `plink`.
*   For complex tasks (e.g., deployment), consider using `scp` or `rsync` via `Desktop Commander`.

### 4. Retrieve Logs
*   **DO NOT** use `tail -f` (blocking).
*   **USE** `journalctl -u [SERVICE] -n [LINES] --no-pager` to get a snapshot.
*   Parse the output for errors or anomalies.

## Example Usage
**User:** "Check the logs on the Pi."
**Agent:**
1.  Identifies IP (e.g., 172.16.190.25).
2.  Constructs command: `plink -ssh -pw raspberry pi@172.16.190.25 "journalctl -u loadcell-transmitter -n 50 --no-pager"`
3.  Executes via `Desktop Commander`.
4.  Returns parsed logs.

## Error Handling
*   If `plink` fails with "Access Denied", ask the user for the correct password.
*   If the connection times out, verify the IP and network status.
