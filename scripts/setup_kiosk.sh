#!/bin/bash
# Setup Elecrow 5" 800x480 display and Chromium kiosk for Scale HDMI page.
# Run on the Raspberry Pi: sudo bash setup_kiosk.sh
# Prerequisites: Raspberry Pi OS with desktop, app already running on port 8080.

set -e

KIOSK_URL="${KIOSK_URL:-http://localhost:8080/hdmi}"
PI_USER="${PI_USER:-pi}"
HOME_DIR="/home/$PI_USER"

echo "=== Kiosk setup: $KIOSK_URL ==="

# 1. HDMI config for 800x480 (Elecrow 5" Display-B)
CONFIG_TXT="/boot/config.txt"
MARKER="# Scale kiosk display (Elecrow 5in 800x480)"
if ! grep -q "hdmi_cvt=800 480" "$CONFIG_TXT" 2>/dev/null; then
  echo "Adding HDMI 800x480 settings to $CONFIG_TXT"
  sudo tee -a "$CONFIG_TXT" << EOF

$MARKER
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
EOF
  echo "HDMI config added. Reboot required for display change."
else
  echo "HDMI 800x480 already present in config.txt"
fi

# 2. Install Chromium and unclutter
echo "Installing Chromium and unclutter..."
sudo apt-get update -qq
sudo apt-get install -y chromium-browser unclutter xserver-xorg xinit || true
# Raspberry Pi OS Bookworm may use 'chromium' package
if ! command -v chromium-browser >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
  sudo apt-get install -y chromium || true
fi

# 3. Kiosk launcher script
SCRIPT="$HOME_DIR/kiosk.sh"
echo "Creating $SCRIPT"
sudo -u "$PI_USER" mkdir -p "$HOME_DIR/.config/chromium/Default" 2>/dev/null || true
sudo tee "$SCRIPT" << 'KIOSK_SCRIPT'
#!/bin/bash
URL="http://localhost:8080/hdmi"
if [ -n "$KIOSK_URL" ]; then URL="$KIOSK_URL"; fi

# Disable screen blanking
xset s noblank
xset s off
xset -dpms

# Prevent Chromium crash dialogs
PREFS="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PREFS" ]; then
  sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS" 2>/dev/null || true
  sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS" 2>/dev/null || true
fi

# Hide mouse cursor after 0.5s idle
unclutter -idle 0.5 -root &

CHROMIUM=$(command -v chromium-browser || command -v chromium || echo "chromium-browser")
exec "$CHROMIUM" \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --disable-restore-session-state \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --disable-ipc-flooding-protection \
  "$URL"
KIOSK_SCRIPT
# Inject URL into script
sudo sed -i "s|http://localhost:8080/hdmi|$KIOSK_URL|" "$SCRIPT"
sudo chown "$PI_USER:$PI_USER" "$SCRIPT"
sudo chmod +x "$SCRIPT"

# 4. Desktop launchers (desktop icon + app menu entry)
DESKTOP_FILE="$HOME_DIR/Desktop/Scale HDMI.desktop"
APPS_DIR="$HOME_DIR/.local/share/applications"
APP_FILE="$APPS_DIR/scale-hdmi.desktop"
echo "Creating launcher shortcuts..."
sudo -u "$PI_USER" mkdir -p "$HOME_DIR/Desktop" "$APPS_DIR"
sudo tee "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Scale HDMI
Comment=Launch full-screen HDMI scale UI
Exec=$SCRIPT
Icon=applications-internet
Terminal=false
Categories=Utility;
StartupNotify=false
EOF
sudo tee "$APP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Scale HDMI
Comment=Launch full-screen HDMI scale UI
Exec=$SCRIPT
Icon=applications-internet
Terminal=false
Categories=Utility;
StartupNotify=false
EOF
sudo chown "$PI_USER:$PI_USER" "$DESKTOP_FILE" "$APP_FILE"
sudo chmod +x "$DESKTOP_FILE" "$APP_FILE"

# 5. Systemd user service for kiosk
SVC_DIR="$HOME_DIR/.config/systemd/user"
sudo -u "$PI_USER" mkdir -p "$SVC_DIR"
sudo tee "$SVC_DIR/kiosk.service" << EOF
[Unit]
Description=Scale Kiosk (Chromium)
After=graphical.target

[Service]
Type=simple
Environment=DISPLAY=:0
Environment=KIOSK_URL=$KIOSK_URL
ExecStart=$SCRIPT
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
sudo chown -R "$PI_USER:$PI_USER" "$SVC_DIR"

# 6. Enable lingering so user service runs without login
echo "Enabling loginctl linger for $PI_USER..."
sudo loginctl enable-linger "$PI_USER" 2>/dev/null || true

# 7. Enable and start (user service)
echo "Enabling kiosk user service..."
sudo -u "$PI_USER" XDG_RUNTIME_DIR=/run/user/$(id -u "$PI_USER") systemctl --user daemon-reload
sudo -u "$PI_USER" XDG_RUNTIME_DIR=/run/user/$(id -u "$PI_USER") systemctl --user enable kiosk.service
echo "To start kiosk now (with X already running): sudo -u $PI_USER systemctl --user start kiosk.service"
echo "Or reboot; if auto-login to desktop is enabled, start the service from the pi user session."

echo "Desktop launcher created: $DESKTOP_FILE"
echo "=== Done. Reboot to apply HDMI and start kiosk (ensure desktop auto-login is on). ==="
