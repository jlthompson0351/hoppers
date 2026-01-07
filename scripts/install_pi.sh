#!/usr/bin/env bash
set -euo pipefail

echo "Installing Python venv + requirements (offline-friendly if wheels are available locally)."

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Install complete."
echo "Next:"
echo "  - run simulated:   ./scripts/run_pi.sh"
echo "  - set up systemd:  sudo cp systemd/loadcell-transmitter.service /etc/systemd/system/"
echo "                    sudo systemctl daemon-reload"
echo "                    sudo systemctl enable --now loadcell-transmitter"


