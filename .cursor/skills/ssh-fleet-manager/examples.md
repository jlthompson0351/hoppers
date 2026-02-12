##SSH Fleet Manager Examples

Real SSH sessions and common patterns.

## Example 1: Quick Health Check

**Scenario:** Check if PTP2 is running properly

```powershell
# Windows PowerShell
plink.exe -pw depor ptp2@172.16.190.29 "systemctl --user list-units 'kiosk-*' --no-legend && ps aux | grep chromium | head -3"
```

**Output:**
```
  kiosk-auto-refresh.service     loaded active running PTP2 Auto-Refresh Monitor
  kiosk-chromium.service         loaded active running PTP2 Chromium Kiosk Display
  kiosk-display-rotation.service loaded active running PTP2 Display Rotation Monitor
  kiosk-health-monitor.service   loaded active running PTP2 System Health Monitor
  kiosk-watchdog.service         loaded active running PTP2 Chromium Watchdog Monitor
ptp2      1809 47.8  3.1 50938068 124040 ?     Rsl  18:50   chromium --kiosk ...
```

**Result:** ✅ All 5 services running, Chromium active

---

## Example 2: First Connection (Accept Host Key)

```powershell
# Use "echo y" to auto-accept host key
echo y | plink.exe -pw depor ptp2@172.16.190.29 "hostname"
```

**Output:**
```
The host key is not cached for this server:
  172.16.190.29 (port 22)
Store key in cache? (y/n) PTP2
```

**Result:** Host key cached, future connections won't prompt

---

## Example 3: Service Restart

**Scenario:** Chromium is frozen, restart it

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "systemctl --user restart kiosk-chromium.service && sleep 3 && ps aux | grep chromium | wc -l"
```

**Output:**
```
7
```

**Result:** Service restarted, 7 chromium processes running (healthy)

---

## Example 4: Check Logs

**Scenario:** Investigate why kiosk crashed

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "tail -20 ~/kiosk/chromium-watchdog.log"
```

**Output:**
```
[2026-01-28 18:51:00] ===== Smart Chromium watchdog started =====
[2026-01-28 18:51:01] Health: HTTP=200 DevTools=OK CPU=2.3%
[2026-01-28 18:52:01] Health: HTTP=200 DevTools=OK CPU=2.1%
[2026-01-28 18:53:01] RESTART TRIGGERED: CPU below 5% for 180s (likely frozen)
[2026-01-28 18:53:10] Health: HTTP=200 DevTools=OK CPU=8.5%
```

**Result:** Watchdog detected CPU freeze and restarted Chromium at 18:53

---

## Example 5: System Resources

**Scenario:** Check if Pi has enough memory/disk

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "free -h && echo '---' && df -h / && echo '---' && uptime"
```

**Output:**
```
               total        used        free      shared  buff/cache   available
Mem:           3.7Gi       1.2Gi       2.1Gi        12Mi       534Mi       2.4Gi
Swap:             0B          0B          0B
---
Filesystem      Size  Used Avail Use% Mounted on
/dev/mmcblk0p2   29G   12G   16G  43% /
---
 18:51:00 up  3:14,  1 user,  load average: 0.52, 0.58, 0.61
```

**Analysis:**
- ✅ Memory: 2.1GB free (good)
- ✅ Disk: 16GB free (good)
- ✅ Load: 0.52 (healthy)

---

## Example 6: Display Rotation Check

**Scenario:** Verify portrait mode is applied

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 wlr-randr | grep -A5 'HDMI-A-1' | grep -E '(Enabled|Transform)'"
```

**Output:**
```
  Enabled: yes
  Transform: 90
```

**Result:** ✅ Display detected, 90° rotation applied (portrait)

---

## Example 7: Network Configuration

**Scenario:** Get IP addresses and MAC addresses

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "hostname && ip addr show | grep -E '(inet |ether)'"
```

**Output:**
```
PTP2
    inet 127.0.0.1/8 scope host lo
    inet 172.16.190.29/24 brd 172.16.190.255 scope global dynamic wlan0
    ether e4:5f:01:79:6c:7b brd ff:ff:ff:ff:ff:ff
```

**Result:** 
- Hostname: PTP2
- WiFi IP: 172.16.190.29
- MAC: e4:5f:01:79:6c:7b

---

## Example 8: Start All Services After Reboot

**Scenario:** Pi rebooted, services need manual start

```powershell
plink.exe -pw depor ptp2@172.16.190.29 "systemctl --user start kiosk-chromium.service kiosk-watchdog.service kiosk-auto-refresh.service kiosk-health-monitor.service kiosk-display-rotation.service && sleep 5 && systemctl --user list-units 'kiosk-*' --no-legend"
```

**Output:**
```
  kiosk-auto-refresh.service     loaded active running PTP2 Auto-Refresh Monitor
  kiosk-chromium.service         loaded active running PTP2 Chromium Kiosk Display
  kiosk-display-rotation.service loaded active running PTP2 Display Rotation Monitor
  kiosk-health-monitor.service   loaded active running PTP2 System Health Monitor
  kiosk-watchdog.service         loaded active running PTP2 Chromium Watchdog Monitor
```

**Result:** ✅ All services started successfully

---

## Example 9: Parallel SSH to Multiple Devices

**Scenario:** Check uptime on PTP2 and PLP5 simultaneously

```javascript
// Tool call 1
Shell({
  command: 'plink.exe -pw depor ptp2@172.16.190.29 "uptime"'
})

// Tool call 2 (in parallel)
Shell({
  command: 'plink.exe -pw depor plp5_screen@192.168.9.39 "uptime"'
})
```

**Result:** Both commands execute simultaneously, faster than sequential

---

## Example 10: File Upload Using Pipe

**Scenario:** Upload a config file from Windows

```powershell
# Create local file first
type "C:\temp\kiosk-config.json" | plink.exe -pw depor ptp2@172.16.190.29 "cat > ~/kiosk/config.json"

# Verify upload
plink.exe -pw depor ptp2@172.16.190.29 "cat ~/kiosk/config.json"
```

**Result:** File uploaded via stdin pipe

---

## Common Command Patterns

### Pattern 1: Chain Commands with &&
```bash
# Only run second command if first succeeds
"command1 && command2 && command3"
```

### Pattern 2: Background Process
```bash
# Start and forget
"sudo reboot"  # SSH will disconnect, that's expected
```

### Pattern 3: Multi-line Output
```bash
# Use echo separator
"free -h && echo '---' && df -h && echo '---' && uptime"
```

### Pattern 4: Conditional Execution
```bash
# Run alternative command if first fails
"systemctl --user status kiosk-chromium.service || echo 'Service not found'"
```

---

## Troubleshooting SSH Issues

### Issue 1: "Connection refused"
```
FATAL ERROR: Network error: Connection refused
```

**Causes:**
- Pi is off or not connected to network
- Wrong IP address
- SSH service not running

**Fix:** Ping first, then verify IP

### Issue 2: "Host key verification failed"
```
WARNING - POTENTIAL SECURITY BREACH!
```

**Cause:** IP changed but old host key cached

**Fix:** Remove from known_hosts or use `echo y | plink`

### Issue 3: "Access denied"
```
Access denied
```

**Causes:**
- Wrong password
- Wrong username
- Account locked

**Fix:** Verify credentials, check user exists on Pi

---

## Performance Tips

1. **Parallel execution** - Run multiple SSH commands simultaneously
2. **Short timeouts** - Don't wait forever for unresponsive devices
3. **Batch commands** - Use `&&` to chain related commands
4. **Filter output** - Use `grep`, `head`, `tail` to reduce data transfer
5. **Reuse connections** - Keep SSH session open for multiple commands (not applicable with plink)
