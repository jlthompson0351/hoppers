$ErrorActionPreference = "Stop"

if (-Not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

$env:LCS_HW_MODE = "sim"
$env:LCS_HOST = "127.0.0.1"
$env:LCS_PORT = "8080"

python -m src.app


