# SSH Fleet Manager Skill

Specialized skill for managing SSH connections to Raspberry Pi kiosks in the Depor fleet.

## Purpose

This skill enables seamless SSH access to Raspberry Pi devices using Desktop Commander's `start_process` MCP tool with plink (Windows SSH client that supports password authentication).

## When to Use

- Connecting to any Pi in the fleet (PLP5, PLP6, kiosk-001, etc.)
- Running remote commands on kiosks
- Checking service status
- Troubleshooting kiosk issues
- Deploying configuration changes

## Key Features

1. **Password-Based SSH**: Uses plink with passwords (no SSH keys required)
2. **Fleet Integration**: Reads device info from `fleet/devices.json`
3. **Desktop Commander**: Leverages the MCP tool that works reliably on Windows
4. **Auto Device Lookup**: Finds Pi by ID, display name, or site

## Common Patterns

### Basic SSH Command
```powershell
# Using Desktop Commander start_process:
plink.exe -pw PASSWORD USERNAME@HOST "COMMAND"
```

### With Auto-Accept Host Key (First Connection)
```powershell
echo y | plink.exe -pw PASSWORD USERNAME@HOST "COMMAND"
```

### Interactive Session
```powershell
# Start interactive SSH
plink.exe -pw PASSWORD USERNAME@HOST
```

## Fleet Device Structure

Devices are stored in `fleet/devices.json`:
```json
{
  "id": "kiosk-001",
  "displayName": "Receiving (Line 1)",
  "ssh": {
    "host": "192.168.9.39",
    "port": 22,
    "user": "plp5_screen"
  }
}
```

## Common Commands

### Health Checks
```bash
# Check if kiosk is running
ps aux | grep chromium

# Check system resources
free -h && df -h

# Check uptime
uptime
```

### Service Management (Gold Standard)
```bash
# List kiosk services
systemctl --user list-units 'kiosk-*'

# Restart chromium service
systemctl --user restart kiosk-chromium.service

# Check watchdog logs
tail -20 kiosk/chromium-watchdog.log
```

### System Diagnostics
```bash
# System info
uname -a

# Network status
ip addr show

# Disk usage
df -h

# Memory usage
free -m

# Running processes
ps aux | head -20
```

## Desktop Commander Integration

Always use Desktop Commander's `start_process` tool for SSH commands:

```javascript
// Example call
start_process({
  command: 'echo y | plink.exe -pw depor plp5_screen@192.168.9.39 "uptime"',
  timeout_ms: 30000,
  shell: "powershell.exe"
})
```

## Error Handling

Common issues and solutions:

1. **Connection Refused**: Check if SSH is enabled on Pi
2. **Host Key Verification**: Use `echo y |` prefix on first connection
3. **Timeout**: Increase `timeout_ms` for long-running commands
4. **Permission Denied**: Verify username and password

## Security Notes

- Passwords are hardcoded for automation purposes
- Consider SSH key-based auth for production environments
- Default password for fleet: `depor` (username: `plp5_screen`)
- Always use secure channels when sharing credentials

## Integration with Fleet CLI

This skill complements the existing Node.js fleet CLI:

```bash
# Fleet CLI (dry-run)
npm run fleet -- ssh kiosk-001 -- uptime

# Fleet CLI (execute)
npm run fleet -- ssh kiosk-001 --run -- uptime
```

The skill provides the same functionality through the AI agent with Desktop Commander.
