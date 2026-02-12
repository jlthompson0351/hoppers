# HDMI Dashboard Runbook

This project now includes a dedicated HDMI operator page at `/hdmi` with:

- Two-column 800x480 layout:
  - Left: centered live weight card
  - Right: daily/shift totals placeholder panel
- Tare and zero metadata under weight:
  - `Tare`
  - `Zero Offset`
  - `Zero Tracking`
  - `Zero Updated`
- `ZERO`
- `TARE`
- `CLEAR TARE`
- `SETTINGS` (opens `/settings`)
- `CLEAR SHIFT TOTAL` (UI placeholder for upcoming DB integration)

## Kiosk Setup on Raspberry Pi

Run the setup script on the Pi:

```bash
sudo bash /opt/loadcell-transmitter/scripts/setup_kiosk.sh
```

Default launch URL is:

```text
http://localhost:8080/hdmi
```

## What Setup Creates

- `~/kiosk.sh` (Chromium full-screen launcher)
- `~/.config/systemd/user/kiosk.service` (auto-start UI service)
- `~/Desktop/Scale HDMI.desktop` (manual one-click launcher)
- `~/.local/share/applications/scale-hdmi.desktop` (app menu entry)

## Power-On Behavior

For hands-off startup at boot:

1. Ensure backend service is enabled (`loadcell-transmitter.service`)
2. Ensure desktop auto-login is enabled for the kiosk user
3. Ensure user service is enabled (`kiosk.service`)

After boot, Chromium opens `/hdmi` in full-screen mode.

## Quick Validation

1. Open `http://localhost:8080/hdmi`
2. Confirm live weight is updating
3. Confirm `ZERO` and `TARE` are disabled when unstable
4. Confirm `CLEAR TARE` works
5. Confirm `SETTINGS` opens `/settings`
6. Confirm `Zero Offset`, `Zero Tracking`, and `Zero Updated` update from `/api/snapshot`
7. Confirm `CLEAR SHIFT TOTAL` shows a placeholder feedback message (no backend mutation yet)
