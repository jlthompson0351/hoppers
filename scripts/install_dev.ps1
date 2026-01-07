$ErrorActionPreference = "Stop"

if (-Not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Dev install complete."
Write-Host "Run: scripts\run_dev.ps1"


