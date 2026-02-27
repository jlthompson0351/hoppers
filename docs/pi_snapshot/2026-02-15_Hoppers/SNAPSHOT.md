# Pi Settings Snapshot: Hoppers (172.16.190.25)

**Captured**: 2026-02-15 14:06 UTC (config version id 9522)
**Status**: ROCK SOLID - Working perfectly, do not touch

---

## 1. SYSTEM INFO

| Property | Value |
|----------|-------|
| Hostname | `Hoppers` |
| IP | `172.16.190.25` (wlan0) |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | `6.12.47+rpt-rpi-v8` (aarch64) |
| Python | 3.13.5 |
| Machine ID | `f1a7f255f2f24f99a9abda456d46558e` |
| Network | WiFi (`wlan0`), eth0 DOWN |
| SSH | Enabled, port 22, user `pi` |

---

## 2. DISPLAY SETTINGS

| Property | Value |
|----------|-------|
| Screen | QDtech MPI5001 5" 800x480 HDMI (USB touch `0484:5750`) |
| Mounting | **Upside down** (for enclosure fit) |
| Framebuffer rotation | `video=HDMI-A-1:800x480@60,rotate=180` in `/boot/firmware/cmdline.txt` |
| Touch calibration | udev rule: `LIBINPUT_CALIBRATION_MATRIX="-1 0 1 0 -1 1"` |
| Touch rule file | `/etc/udev/rules.d/98-touchscreen-rotate.rules` |
| Compositor | `labwc` (Wayland) |
| Kiosk browser | Chromium 142.0.7444.175 `--kiosk http://localhost:8080/hdmi` |
| App display: round_up_enabled | **true** |
| App display: show_decimal_point | **true** |
| App display: weight_decimals | **0** |

### Full kernel cmdline
```
console=serial0,115200 console=tty1 root=PARTUUID=25c45fd1-02 rootfstype=ext4 fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles cfg80211.ieee80211_regdom=US video=HDMI-A-1:800x480@60,rotate=180
```

### Touchscreen udev rule (`/etc/udev/rules.d/98-touchscreen-rotate.rules`)
```
ATTRS{idVendor}=="0484", ATTRS{idProduct}=="5750", ENV{LIBINPUT_CALIBRATION_MATRIX}="-1 0 1 0 -1 1"
```

---

## 3. DATABASE SETTINGS

| Property | Value |
|----------|-------|
| DB path | `/var/lib/loadcell-transmitter/data/app.sqlite3` |
| DB size | ~64 MB |
| Integrity check | **ok** |
| journal_mode | **wal** |
| synchronous | **2** (FULL) |
| wal_autocheckpoint | **1000** |
| foreign_keys | **0** (OFF) |
| busy_timeout | **30000** ms |
| user_version | **0** |
| Config version ID | **9522** |
| Config timestamp | `2026-02-15T20:06:38+00:00` |

### Tables
- `calibration_points`, `config_versions`, `events`, `plc_profile_points`
- `production_dumps`, `production_totals`, `schema_version`
- `throughput_events`, `trends_channels`, `trends_excitation`, `trends_total`

---

## 4. APP CONFIG SETTINGS (every single one)

### 4.1 Scale / Zero
| Setting | Value |
|---------|-------|
| zero_offset_mv | **0.02566119596854257** |
| zero_offset_lbs | **2.4200517645500286** |
| zero_offset_signal | **0.02566119596854257** |
| zero_offset_updated_utc | `2026-02-15T20:06:37+00:00` |
| tare_offset_lbs | **0.0** |
| last_tare_utc | `2026-02-15T17:21:28+00:00` |
| allow_opto_tare | **false** |

### 4.2 Zero Tracking
| Setting | Value |
|---------|-------|
| enabled | **true** |
| deadband_lb | **0.1** |
| hold_s | **6.0** |
| negative_hold_s | **1.0** |
| persist_interval_s | **1.0** |
| range_lb | **10.0** |
| rate_lbs | **0.8** |

### 4.3 DAQ (24b8vin)
| Setting | Value |
|---------|-------|
| stack_level | **0** |
| channel | **7** (CH8, 0-indexed) |
| gain_code | **6** |
| average_samples | **2** |
| sample_rate | **0** (250 SPS) |
| enabled_channels | `[F,F,F,F,F,F,F,T]` (only CH8) |

### 4.4 DAQ 24b8vin Per-Channel
All 8 channels: `enabled=false`, `gain_code=7`, `role="Not used"`

### 4.5 MegaIND
| Setting | Value |
|---------|-------|
| stack_level | **2** |

### 4.6 I2C
| Setting | Value |
|---------|-------|
| bus | **1** |

I2C devices detected: `0x31` (24b8vin DAQ), `0x52` (MegaIND stack 2)

### 4.7 Excitation Monitoring
| Setting | Value |
|---------|-------|
| enabled | **true** |
| ai_channel | **1** |
| fault_v | **8.0** |
| warn_v | **9.0** |

### 4.8 Filter (Kalman)
| Setting | Value |
|---------|-------|
| use_kalman | **true** |
| kalman_q (process noise) | **5.5** |
| kalman_r (measurement noise) | **80.0** |
| alpha (EMA fallback) | **0.18** |
| median_enabled | **false** |
| median_window | 5 |
| notch_enabled | **false** |
| notch_freq | 60 |
| stability_window | **15** |
| stability_threshold | **3.0** |
| stability_stddev_lb | **3.0** |
| stability_slope_lbs | **4.0** |

### 4.9 Drift Compensation
| Setting | Value |
|---------|-------|
| ema_alpha | **0.02** |
| ratio_threshold | **0.12** |
| consecutive_required | **20** |

### 4.10 Output (PLC)
| Setting | Value |
|---------|-------|
| mode | **0_10V** |
| ao_channel_v | **2** |
| ao_channel_ma | **2** |
| armed | **true** |
| safe_v | **0.0** |
| safe_ma | **4.0** |
| ramp_enabled | **false** |
| ramp_rate_v | 5.0 |
| ramp_rate_ma | 8.0 |
| deadband_enabled | **false** |
| deadband_lb | 0.0 |
| nudge_value | 0.0 |
| test_mode | **false** |
| test_value | 0.0 |
| calibration_active | **false** |

### 4.11 Range
| Setting | Value |
|---------|-------|
| min_lb | **0.0** |
| max_lb | **300.0** |

### 4.12 Alarms
| Setting | Value |
|---------|-------|
| allow_negative | **false** |
| underload_lb | **-5.0** |
| high_lb | null (off) |
| low_lb | null (off) |
| overload_lb | null (off) |
| overload_action | **alarm** |
| rate_lbs | null (off) |

### 4.13 Startup
| Setting | Value |
|---------|-------|
| auto_arm | **true** |
| auto_zero | **false** |
| delay_s | **5** |
| output_value | **0.0** |
| require_manual_zero_before_auto_zero | **true** |

### 4.14 Fault
| Setting | Value |
|---------|-------|
| delay_s | **2.0** |
| recovery | **auto** |

### 4.15 Timing
| Setting | Value |
|---------|-------|
| loop_rate_hz | **20** |
| config_refresh_s | **2.0** |
| board_offline_s | **5** |
| i2c_retry_count | **3** |

### 4.16 Logging
| Setting | Value |
|---------|-------|
| log_weight | **true** |
| log_output | **true** |
| log_raw | **false** |
| event_only | **false** |
| interval_s | **1** |
| retention_days | **30** |

### 4.17 Throughput (Dump Detection)
| Setting | Value |
|---------|-------|
| enabled | **true** |
| dump_drop_lb | **6.0** |
| empty_threshold_lb | **2.0** |
| empty_confirm_s | **0.3** |
| full_min_lb | **15.0** |
| full_stability_s | **0.4** |
| rise_trigger_lb | **8.0** |
| min_processed_lb | **5.0** |
| max_cycle_s | **900.0** |
| device_id | null |
| hopper_id | null |

### 4.18 Dump Detection (legacy)
| Setting | Value |
|---------|-------|
| drop_threshold_lb | **25.0** |
| min_prev_stable_lb | **10.0** |

### 4.19 Production
| Setting | Value |
|---------|-------|
| shift_start_utc | `2026-02-13T20:15:38+00:00` |

### 4.20 Opto Actions
| Opto Input | Action |
|------------|--------|
| 1 | **tare** |
| 2 | **zero** |
| 3 | **print** |
| 4 | **none** |

### 4.21 MegaIND I/O Rules
| Setting | Value |
|---------|-------|
| armed | **true** |
| allow_plc_channel | **false** |
| safe_v | **0.0** |
| AO channels 1-4 | all `enabled=false`, `value_v=0.0` |
| Rules 1-4 | all `enabled=false` |

### 4.22 UI
| Setting | Value |
|---------|-------|
| poll_rate_ms | **500** |
| timezone | **UTC** |
| maintenance_enabled | **false** |

### 4.23 Watchdog
| Setting | Value |
|---------|-------|
| daq_enabled | **false** |
| daq_period_s | 120 |
| megaind_enabled | **false** |
| megaind_period_s | 120 |

### 4.24 Disabled Features
| Feature | Status |
|---------|--------|
| LEDs | **off** |
| OneWire | **off** |
| RS485 | **off** |

---

## 5. SERVICE SETTINGS

### systemd unit (`/etc/systemd/system/loadcell-transmitter.service`)
```ini
[Unit]
Description=Load Cell Scale Transmitter (Flask + acquisition loop)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/loadcell-transmitter
Environment=LCS_HW_MODE=real
Environment=LCS_HOST=0.0.0.0
Environment=LCS_PORT=8080
Environment=LCS_VAR_DIR=/var/lib/loadcell-transmitter
Environment=PATH=/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/loadcell-transmitter/.venv/bin/python -m src.app
Restart=always
RestartSec=2
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
```

### Key enabled system services
- `loadcell-transmitter.service` - **enabled** (active, running)
- `ssh.service` - enabled
- `NetworkManager.service` - enabled
- `lightdm.service` - enabled
- `bluetooth.service` - enabled
- `avahi-daemon.service` - enabled

### User systemd (kiosk)
- `/home/pi/.config/systemd/user/kiosk.service` present

### Crontabs
- pi: **none**
- root: **none**

---

## 6. PYTHON PACKAGES (venv)

| Package | Version |
|---------|---------|
| Flask | 3.0.0 |
| waitress | 2.1.2 |
| numpy | 2.3.5 |
| sm24b8vin | 1.0.1 |
| smmegaind | 1.0.4 |
| smbus2 | 0.5.0 |
| RPi.GPIO | 0.7.1 |
| pymodbus | 3.11.4 |
| loguru | 0.7.3 |
| Jinja2 | 3.1.6 |
| Werkzeug | 3.1.4 |
| blinker | 1.9.0 |
| click | 8.3.1 |
| itsdangerous | 2.2.0 |
| MarkupSafe | 3.0.3 |

---

## 7. RAW CONFIG JSON

```json
{
  "alarms": {
    "allow_negative": false,
    "high_lb": null,
    "low_lb": null,
    "overload_action": "alarm",
    "overload_lb": null,
    "rate_lbs": null,
    "underload_lb": -5.0
  },
  "daq": {
    "average_samples": 2,
    "channel": 7,
    "enabled_channels": [false, false, false, false, false, false, false, true],
    "gain_code": 6,
    "sample_rate": 0,
    "stack_level": 0
  },
  "daq24b8vin": {
    "average_samples": 2,
    "channels": [
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"},
      {"enabled": false, "gain_code": 7, "role": "Not used"}
    ],
    "stack_level": 0
  },
  "display": {
    "round_up_enabled": true,
    "show_decimal_point": true,
    "weight_decimals": 0
  },
  "drift": {
    "consecutive_required": 20,
    "ema_alpha": 0.02,
    "ratio_threshold": 0.12
  },
  "dump_detection": {
    "drop_threshold_lb": 25.0,
    "min_prev_stable_lb": 10.0
  },
  "excitation": {
    "ai_channel": 1,
    "enabled": true,
    "fault_v": 8.0,
    "warn_v": 9.0
  },
  "fault": {
    "delay_s": 2.0,
    "recovery": "auto"
  },
  "filter": {
    "alpha": 0.18,
    "kalman_measurement_noise": 80.0,
    "kalman_process_noise": 5.5,
    "kalman_q": 5.5,
    "kalman_r": 80.0,
    "median_enabled": false,
    "median_window": 5,
    "notch_enabled": false,
    "notch_freq": 60,
    "stability_slope_lbs": 4.0,
    "stability_stddev_lb": 3.0,
    "stability_threshold": 3.0,
    "stability_window": 15,
    "use_kalman": true
  },
  "i2c": {"bus": 1},
  "leds": {"enabled": false},
  "logging": {
    "event_only": false,
    "interval_s": 1,
    "log_output": true,
    "log_raw": false,
    "log_weight": true,
    "retention_days": 30
  },
  "megaind": {"stack_level": 2},
  "megaind_io": {
    "allow_plc_channel": false,
    "ao_v": [
      {"enabled": false, "value_v": 0.0},
      {"enabled": false, "value_v": 0.0},
      {"enabled": false, "value_v": 0.0},
      {"enabled": false, "value_v": 0.0}
    ],
    "armed": true,
    "rules": [
      {"condition": "gte", "else_enabled": false, "enabled": false, "false_value_v": 0.0, "input_ch": 1, "input_kind": "ai_v", "output_ch": 1, "threshold": 0.0, "true_value_v": 0.0},
      {"condition": "gte", "else_enabled": false, "enabled": false, "false_value_v": 0.0, "input_ch": 1, "input_kind": "ai_v", "output_ch": 1, "threshold": 0.0, "true_value_v": 0.0},
      {"condition": "gte", "else_enabled": false, "enabled": false, "false_value_v": 0.0, "input_ch": 1, "input_kind": "ai_v", "output_ch": 1, "threshold": 0.0, "true_value_v": 0.0},
      {"condition": "gte", "else_enabled": false, "enabled": false, "false_value_v": 0.0, "input_ch": 1, "input_kind": "ai_v", "output_ch": 1, "threshold": 0.0, "true_value_v": 0.0}
    ],
    "safe_v": 0.0
  },
  "onewire": {"enabled": false},
  "opto_actions": {"1": "tare", "2": "zero", "3": "print", "4": "none"},
  "output": {
    "ao_channel": 2,
    "ao_channel_ma": 2,
    "ao_channel_v": 2,
    "armed": true,
    "calibration_active": false,
    "deadband_enabled": false,
    "deadband_lb": 0.0,
    "mode": "0_10V",
    "nudge_value": 0.0,
    "ramp_enabled": false,
    "ramp_rate_ma": 8.0,
    "ramp_rate_v": 5.0,
    "safe_ma": 4.0,
    "safe_v": 0.0,
    "test_mode": false,
    "test_value": 0.0
  },
  "production": {"shift_start_utc": "2026-02-13T20:15:38+00:00"},
  "range": {"max_lb": 300.0, "min_lb": 0.0},
  "rs485": {"enabled": false},
  "scale": {
    "allow_opto_tare": false,
    "last_tare_utc": "2026-02-15T17:21:28+00:00",
    "tare_offset_lbs": 0.0,
    "zero_offset_lbs": 2.4200517645500286,
    "zero_offset_mv": 0.02566119596854257,
    "zero_offset_signal": 0.02566119596854257,
    "zero_offset_updated_utc": "2026-02-15T20:06:37+00:00"
  },
  "startup": {
    "auto_arm": true,
    "auto_zero": false,
    "delay_s": 5,
    "output_value": 0.0,
    "require_manual_zero_before_auto_zero": true
  },
  "throughput": {
    "device_id": null,
    "dump_drop_lb": 6.0,
    "empty_confirm_s": 0.3,
    "empty_threshold_lb": 2.0,
    "enabled": true,
    "full_min_lb": 15.0,
    "full_stability_s": 0.4,
    "hopper_id": null,
    "max_cycle_s": 900.0,
    "min_processed_lb": 5.0,
    "rise_trigger_lb": 8.0
  },
  "timing": {
    "board_offline_s": 5,
    "config_refresh_s": 2.0,
    "i2c_retry_count": 3,
    "loop_rate_hz": 20
  },
  "ui": {
    "maintenance_enabled": false,
    "poll_rate_ms": 500,
    "timezone": "UTC"
  },
  "watchdog": {
    "daq_enabled": false,
    "daq_period_s": 120,
    "megaind_enabled": false,
    "megaind_period_s": 120
  },
  "zero_tracking": {
    "deadband_lb": 0.1,
    "enabled": true,
    "hold_s": 6.0,
    "negative_hold_s": 1.0,
    "persist_interval_s": 1.0,
    "range_lb": 10.0,
    "rate_lbs": 0.8
  }
}
```

---

## 8. BACKUP ARTIFACTS

- Full baseline bundle: `backups/pi-baseline-172.16.190.25-20260215-140649/`
- SQLite backup: `backups/.../artifacts/app.sqlite3.backup` (64 MB, consistent snapshot)
- Boot config tar: `backups/.../artifacts/boot_config.tar.gz`
- Network/identity tar: `backups/.../artifacts/etc_identity_network.tar.gz`
- Service unit tar: `backups/.../artifacts/etc_loadcell_service.tar.gz`
- App code tar: `backups/.../artifacts/opt_loadcell_transmitter.tar.gz`
- Kiosk files tar: `backups/.../artifacts/home_pi_kiosk_files.tar.gz`
