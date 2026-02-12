---
name: ssh-fleet-manager
description: SSH into Raspberry Pi kiosks using Desktop Commander with plink for password-based authentication. Use when connecting to Pis, running remote commands, checking kiosk status, or troubleshooting devices in the fleet.
---

# SSH Fleet Manager

Connect to and manage Raspberry Pi kiosks using Desktop Commander's `start_process` MCP tool with plink.

## When to Use

- User wants to SSH into a Pi (PLP5, kiosk-001, etc.)
- Running commands remotely on kiosks
- Checking service status or logs
- Troubleshooting kiosk issues
- Deploying configuration changes

## Fleet Device Lookup

Read `fleet/devices.json` to find device information:

```javascript
// Device structure
{
  "id": "kiosk-001",
  "displayName": "Receiving (Line 1)",
  "ssh": {
    "host": "192.168.9.39",  // or piconnect hostname
    "port": 22,
    "user": "plp5_screen"
  }
}
```

## SSH Using Desktop Commander

**CRITICAL**: Always use Desktop Commander's `start_process` MCP tool for SSH commands. The built-in Cursor terminal doesn't handle plink password authentication well.

### Basic Pattern

```javascript
start_process({
  command: 'plink.exe -pw PASSWORD USERNAME@HOST "COMMAND"',
  timeout_ms: 15000,
  shell: "powershell.exe"
})
```

### First Connection (Accept Host Key)

```javascript
start_process({
  command: 'echo y | plink.exe -pw depor plp5_screen@192.168.9.39 "hostname"',
  timeout_ms: 15000,
  shell: "powershell.exe"
})
```

## Common Commands

### Health Checks

**Check if kiosk is running:**
```bash
ps aux | grep chromium | grep -v grep
```

**System resources:**
```bash
free -h && df -h && uptime
```

**Kiosk services (Gold Standard):**
```bash
systemctl --user list-units 'kiosk-*'
```

### Service Management

**Restart chromium:**
```bash
systemctl --user restart kiosk-chromium.service
```

**Check service status:**
```bash
systemctl --user status kiosk-chromium.service
```

**View watchdog logs:**
```bash
tail -50 kiosk/chromium-watchdog.log
```

### Diagnostics

**System info:**
```bash
uname -a && hostname
```

**Network status:**
```bash
ip addr show && ping -c 3 8.8.8.8
```

**Recent errors:**
```bash
journalctl --user -u kiosk-chromium.service -n 20
```

## Fleet CLI Integration

The project has a Node.js CLI that can generate SSH commands:

```bash
# Dry-run (prints command)
npm run fleet -- ssh kiosk-001 -- uptime

# Execute
npm run fleet -- ssh kiosk-001 --run -- uptime
```

Use this to get device info, then execute via Desktop Commander for better reliability.

## Default Credentials

- **Username**: `plp5_screen`
- **Password**: `depor`
- **Port**: 22

## Quick Reference

| Task | Command Pattern |
|------|----------------|
| Health check | `ps aux \| grep chromium && free -h` |
| Restart kiosk | `systemctl --user restart kiosk-chromium.service` |
| Check logs | `tail -50 kiosk/chromium-watchdog.log` |
| System info | `uname -a && uptime` |
| Reboot Pi | `sudo reboot` |

## Gold Standard Reference

For complete kiosk architecture details, see `docs/KIOSK_GOLD_STANDARD.md`.
