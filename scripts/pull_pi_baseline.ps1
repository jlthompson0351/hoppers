param(
  [string]$PiHost = "172.16.190.25",
  [string]$PiUser = "pi",
  [string]$BackupRoot = ".\backups",
  [SecureString]$PiPassword,
  [int]$JournalLines = 2000,
  [switch]$SkipVenv,
  [switch]$KeepRemoteStage
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-PlainTextFromSecureString {
  param([Parameter(Mandatory = $true)][SecureString]$SecureValue)
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  }
  finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

function Get-ExecutablePath {
  param([Parameter(Mandatory = $true)][string]$Name)
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $cmd) {
    throw "Required executable '$Name' was not found in PATH."
  }
  return $cmd.Source
}

function Invoke-PlinkCommand {
  param(
    [Parameter(Mandatory = $true)][string]$PlinkPath,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$Command
  )
  & $PlinkPath -batch -pw $script:PlainPassword $Target $Command
  if ($LASTEXITCODE -ne 0) {
    throw "plink failed with exit code $LASTEXITCODE."
  }
}

function Invoke-PscpDownload {
  param(
    [Parameter(Mandatory = $true)][string]$PscpPath,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [switch]$Recursive
  )
  $pscpArgs = @("-batch", "-pw", $script:PlainPassword)
  if ($Recursive) {
    $pscpArgs += "-r"
  }
  $pscpArgs += @("${Target}:$RemotePath", $LocalPath)
  & $PscpPath @pscpArgs
  if ($LASTEXITCODE -ne 0) {
    throw "pscp download failed with exit code $LASTEXITCODE."
  }
}

if ($JournalLines -lt 50) {
  throw "JournalLines must be at least 50."
}

$plinkPath = Get-ExecutablePath -Name "plink"
$pscpPath = Get-ExecutablePath -Name "pscp"

if (-not $PiPassword) {
  $PiPassword = Read-Host "Enter Pi password for $PiUser@$PiHost" -AsSecureString
}
$script:PlainPassword = Get-PlainTextFromSecureString -SecureValue $PiPassword
$passwordB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script:PlainPassword))

if (-not (Test-Path -LiteralPath $BackupRoot)) {
  New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
}
$backupRootPath = (Resolve-Path -LiteralPath $BackupRoot).Path

$hostSlug = ($PiHost -replace "[^A-Za-z0-9\.-]", "_")
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundleName = "pi-baseline-$hostSlug-$stamp"
$remoteStage = "/tmp/$bundleName"
$localStage = Join-Path $backupRootPath $bundleName
$target = "$PiUser@$PiHost"
$includeVenvFlag = if ($SkipVenv) { "0" } else { "1" }

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "Pulling mission-critical Pi baseline" -ForegroundColor Cyan
Write-Host "Target: $target" -ForegroundColor Cyan
Write-Host "Local output: $localStage" -ForegroundColor Cyan
Write-Host "Include venv: $($includeVenvFlag -eq '1')" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

$remoteScript = @'
#!/usr/bin/env bash
set -euo pipefail

STAGE_DIR="$1"
INCLUDE_VENV="$2"
JOURNAL_LINES="$3"
SUDO_PASS_B64="${4:-}"

ARTIFACTS="$STAGE_DIR/artifacts"
REPORTS="$STAGE_DIR/reports"
mkdir -p "$ARTIFACTS" "$REPORTS"

SUDO_PASS=""
if [ -n "$SUDO_PASS_B64" ]; then
  SUDO_PASS="$(printf '%s' "$SUDO_PASS_B64" | base64 -d || true)"
fi

sudo_shell() {
  local cmd="$1"
  if sudo -n true >/dev/null 2>&1; then
    sudo -n bash -lc "$cmd"
    return
  fi
  if [ -n "$SUDO_PASS" ]; then
    printf '%s\n' "$SUDO_PASS" | sudo -S -p '' bash -lc "$cmd"
    return
  fi
  sudo bash -lc "$cmd"
}

capture_cmd() {
  local outfile="$1"
  local cmd="$2"
  {
    echo "### COMMAND: $cmd"
    bash -lc "$cmd"
  } >"$outfile" 2>&1 || true
}

capture_sudo() {
  local outfile="$1"
  local cmd="$2"
  {
    echo "### COMMAND (sudo): $cmd"
    sudo_shell "$cmd"
  } >"$outfile" 2>&1 || true
}

create_tar() {
  local archive_name="$1"
  shift
  local existing=()
  for rel_path in "$@"; do
    if sudo_shell "test -e '/$rel_path'"; then
      existing+=("$rel_path")
    fi
  done

  if [ "${#existing[@]}" -eq 0 ]; then
    echo "SKIPPED: none of the requested paths exist." >"$ARTIFACTS/$archive_name.SKIPPED.txt"
    return
  fi

  local rel_list=""
  for rel_path in "${existing[@]}"; do
    rel_list="$rel_list '$rel_path'"
  done

  # GNU tar returns exit=1 for non-fatal warnings like:
  #   - "file changed as we read it" (common for WAL sqlite + logs)
  # This baseline pull is best-effort; record the warning and continue so the
  # rest of the bundle still downloads.
  set +e
  sudo_shell "tar --numeric-owner --xattrs --acls -czf '$ARTIFACTS/$archive_name' -C /$rel_list"
  local tar_status=$?
  set -e
  if [ "$tar_status" -ne 0 ]; then
    echo "WARN: tar exited $tar_status for $archive_name" >"$ARTIFACTS/$archive_name.WARN.txt"
  fi
}

capture_cmd "$REPORTS/date_utc.txt" "date -u --iso-8601=seconds"
capture_cmd "$REPORTS/uname.txt" "uname -a"
capture_cmd "$REPORTS/os_release.txt" "cat /etc/os-release"
capture_cmd "$REPORTS/hostnamectl.txt" "hostnamectl"
capture_cmd "$REPORTS/ip_addr.txt" "ip -brief addr"
capture_cmd "$REPORTS/ip_route.txt" "ip route"
capture_sudo "$REPORTS/systemctl_loadcell_status.txt" "systemctl status loadcell-transmitter --no-pager"
capture_sudo "$REPORTS/systemctl_loadcell_cat.txt" "systemctl cat loadcell-transmitter"
capture_sudo "$REPORTS/journal_loadcell_tail.txt" "journalctl -u loadcell-transmitter -n $JOURNAL_LINES --no-pager"
capture_sudo "$REPORTS/dpkg_packages.txt" "dpkg-query -W -f='\${binary:Package}\t\${Version}\n'"

{
  echo "### COMMAND (sudo): i2cdetect -y 1 (fallback to /usr/sbin/i2cdetect)"
  if sudo_shell "command -v i2cdetect >/dev/null 2>&1"; then
    sudo_shell "i2cdetect -y 1"
  elif sudo_shell "test -x /usr/sbin/i2cdetect"; then
    sudo_shell "/usr/sbin/i2cdetect -y 1"
  else
    echo "i2cdetect not found on this Pi."
  fi
} >"$REPORTS/i2cdetect_bus1.txt" 2>&1 || true

if sudo_shell "test -x /opt/loadcell-transmitter/.venv/bin/pip"; then
  capture_sudo "$REPORTS/venv_python_version.txt" "/opt/loadcell-transmitter/.venv/bin/python --version"
  capture_sudo "$REPORTS/venv_pip_freeze.txt" "/opt/loadcell-transmitter/.venv/bin/pip freeze"
fi

DB_PATH=""
if sudo_shell "test -f /var/lib/loadcell-transmitter/data/app.sqlite3"; then
  DB_PATH="/var/lib/loadcell-transmitter/data/app.sqlite3"
elif sudo_shell "test -f /var/lib/loadcell-transmitter/app.sqlite3"; then
  DB_PATH="/var/lib/loadcell-transmitter/app.sqlite3"
fi

if [ -n "$DB_PATH" ]; then
  echo "$DB_PATH" >"$REPORTS/sqlite_db_path.txt"
fi

if [ -n "$DB_PATH" ] && sudo_shell "command -v sqlite3 >/dev/null 2>&1"; then
  capture_sudo "$REPORTS/sqlite_integrity_check.txt" "sqlite3 '$DB_PATH' 'PRAGMA integrity_check;'"
  capture_sudo "$REPORTS/sqlite_pragmas.txt" "sqlite3 '$DB_PATH' 'PRAGMA journal_mode; PRAGMA synchronous; PRAGMA wal_autocheckpoint; PRAGMA foreign_keys; PRAGMA busy_timeout; PRAGMA user_version;'"
  capture_sudo "$REPORTS/sqlite_tables.txt" "sqlite3 '$DB_PATH' '.tables'"
  capture_sudo "$REPORTS/sqlite_schema.txt" "sqlite3 '$DB_PATH' '.schema'"

  # Capture the latest app config JSON (this is what the UI toggles map to).
  capture_sudo "$REPORTS/app_config_latest.json" "sqlite3 '$DB_PATH' 'SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1;' | python3 -c 'import json,sys; print(json.dumps(json.loads(sys.stdin.read()), indent=2, sort_keys=True))'"

  # Create a consistent DB snapshot (avoids churn from WAL/shm while service runs).
  capture_sudo "$REPORTS/sqlite_backup.txt" "sqlite3 '$DB_PATH' '.backup $ARTIFACTS/app.sqlite3.backup'"
fi

# Fallback: many production images don't have the sqlite3 CLI installed.
# Use Python stdlib sqlite3 to capture the same "DB settings" artifacts.
if [ -n "$DB_PATH" ] && ! command -v sqlite3 >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  {
    echo "### COMMAND: python3 sqlite snapshot fallback"
    python3 - "$DB_PATH" "$REPORTS" "$ARTIFACTS" <<'PY'
import json
import pathlib
import sqlite3
import sys

db_path = sys.argv[1]
reports_dir = pathlib.Path(sys.argv[2])
artifacts_dir = pathlib.Path(sys.argv[3])
reports_dir.mkdir(parents=True, exist_ok=True)
artifacts_dir.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path, timeout=30.0)
conn.row_factory = sqlite3.Row

def write_text(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="ascii", errors="replace")

def pragma_value(name: str):
    row = conn.execute(f"PRAGMA {name};").fetchone()
    return row[0] if row else None

integrity_rows = conn.execute("PRAGMA integrity_check;").fetchall()
write_text(reports_dir / "sqlite_integrity_check.txt", "\n".join([r[0] for r in integrity_rows]) + "\n")

pragmas = {
    "journal_mode": pragma_value("journal_mode"),
    "synchronous": pragma_value("synchronous"),
    "wal_autocheckpoint": pragma_value("wal_autocheckpoint"),
    "foreign_keys": pragma_value("foreign_keys"),
    "busy_timeout": pragma_value("busy_timeout"),
    "user_version": pragma_value("user_version"),
}
write_text(
    reports_dir / "sqlite_pragmas.txt",
    "".join([f"{k}={v}\n" for k, v in pragmas.items()]),
)

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
write_text(reports_dir / "sqlite_tables.txt", "\n".join(tables) + "\n")

schema_sql = [
    r[0]
    for r in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name;").fetchall()
    if r[0]
]
write_text(reports_dir / "sqlite_schema.txt", ";\n\n".join(schema_sql) + ";\n")

latest_row = conn.execute(
    "SELECT id, ts, config_json FROM config_versions ORDER BY id DESC LIMIT 1;"
).fetchone()
latest = {"id": None, "ts": None, "config": None}
if latest_row is not None:
    latest["id"] = int(latest_row["id"])
    latest["ts"] = latest_row["ts"]
    try:
        latest["config"] = json.loads(latest_row["config_json"] or "{}")
    except Exception:
        latest["config"] = {"_error": "Failed to parse config_json"}

write_text(reports_dir / "app_config_latest.json", json.dumps(latest, indent=2, sort_keys=True))

# Create a consistent DB snapshot (online backup API).
dest_path = artifacts_dir / "app.sqlite3.backup"
try:
    dest_path.unlink()
except FileNotFoundError:
    pass

dest_conn = sqlite3.connect(str(dest_path))
conn.backup(dest_conn)
dest_conn.close()

write_text(reports_dir / "sqlite_backup.txt", f"python_backup_dest={dest_path}\n")

conn.close()
print("python sqlite snapshot complete")
PY
  } >"$REPORTS/sqlite_snapshot_python.txt" 2>&1 || true
fi

capture_sudo "$REPORTS/find_opt_loadcell_transmitter.txt" "if [ -d /opt/loadcell-transmitter ]; then find /opt/loadcell-transmitter -xdev -printf '%M\t%u:%g\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS\t%p\n'; else echo '/opt/loadcell-transmitter missing'; fi"
capture_sudo "$REPORTS/find_var_lib_loadcell_transmitter.txt" "if [ -d /var/lib/loadcell-transmitter ]; then find /var/lib/loadcell-transmitter -xdev -printf '%M\t%u:%g\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS\t%p\n'; else echo '/var/lib/loadcell-transmitter missing'; fi"
capture_sudo "$REPORTS/sha256_opt_loadcell_transmitter.txt" "if [ -d /opt/loadcell-transmitter ]; then cd /opt/loadcell-transmitter && find . -type f -print0 | sort -z | xargs -0 -r sha256sum; else echo '/opt/loadcell-transmitter missing'; fi"
capture_sudo "$REPORTS/sha256_var_lib_loadcell_transmitter.txt" "if [ -d /var/lib/loadcell-transmitter ]; then cd /var/lib/loadcell-transmitter && find . -type f -print0 | sort -z | xargs -0 -r sha256sum; else echo '/var/lib/loadcell-transmitter missing'; fi"

if sudo_shell "test -d /opt/loadcell-transmitter"; then
  if [ "$INCLUDE_VENV" = "1" ]; then
    sudo_shell "tar --numeric-owner --xattrs --acls -czf '$ARTIFACTS/opt_loadcell_transmitter.tar.gz' -C / opt/loadcell-transmitter"
  else
    sudo_shell "tar --numeric-owner --xattrs --acls --exclude='opt/loadcell-transmitter/.venv' -czf '$ARTIFACTS/opt_loadcell_transmitter.tar.gz' -C / opt/loadcell-transmitter"
  fi
else
  echo "SKIPPED: /opt/loadcell-transmitter missing" >"$ARTIFACTS/opt_loadcell_transmitter.tar.gz.SKIPPED.txt"
fi

# NOTE: The live SQLite DB can churn (WAL/shm) while the service is running.
# We capture a consistent SQLite `.backup` above, and exclude the live sqlite
# files from the /var/lib tar so tar doesn't error out mid-stream.
if sudo_shell "test -d /var/lib/loadcell-transmitter"; then
  set +e
  sudo_shell "tar --numeric-owner --xattrs --acls --exclude='var/lib/loadcell-transmitter/data/app.sqlite3*' --exclude='var/lib/loadcell-transmitter/app.sqlite3*' -czf '$ARTIFACTS/var_lib_loadcell_transmitter.tar.gz' -C / var/lib/loadcell-transmitter"
  var_tar_status=$?
  set -e
  if [ "$var_tar_status" -ne 0 ]; then
    echo "WARN: tar exited $var_tar_status for var_lib_loadcell_transmitter.tar.gz" >"$ARTIFACTS/var_lib_loadcell_transmitter.tar.gz.WARN.txt"
  fi
else
  echo "SKIPPED: /var/lib/loadcell-transmitter missing" >"$ARTIFACTS/var_lib_loadcell_transmitter.tar.gz.SKIPPED.txt"
fi

create_tar "etc_loadcell_service.tar.gz" \
  "etc/systemd/system/loadcell-transmitter.service"

create_tar "etc_identity_network.tar.gz" \
  "etc/hostname" \
  "etc/hosts" \
  "etc/dhcpcd.conf" \
  "etc/network/interfaces" \
  "etc/ssh/sshd_config" \
  "etc/wpa_supplicant/wpa_supplicant.conf"

create_tar "boot_config.tar.gz" \
  "boot/config.txt" \
  "boot/firmware/config.txt"

create_tar "home_pi_kiosk_files.tar.gz" \
  "home/pi/kiosk.sh" \
  "home/pi/.config/systemd/user/kiosk.service" \
  "home/pi/Desktop/Scale HDMI.desktop" \
  "home/pi/.local/share/applications/scale-hdmi.desktop"

create_tar "home_pi_hoppers_legacy.tar.gz" \
  "home/pi/hoppers"

{
  echo "bundle_created_utc=$(date -u --iso-8601=seconds)"
  echo "stage_dir=$STAGE_DIR"
  echo "include_venv=$INCLUDE_VENV"
  echo "journal_lines=$JOURNAL_LINES"
  echo
  echo "[artifact_sizes]"
  (cd "$ARTIFACTS" && ls -lah)
} >"$REPORTS/manifest.txt"

CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
sudo_shell "chown -R '$CURRENT_USER:$CURRENT_GROUP' '$STAGE_DIR'" || true
rm -f /tmp/lcs_pull_baseline.sh || true
'@

$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
# IMPORTANT: $remoteScript comes from a PowerShell here-string (CRLF).
# If we decode it verbatim on Linux, the shebang becomes `#!/usr/bin/env bash\r`
# and the script will not execute. Strip CR to force LF line endings.
$launchCommand = "echo '$remoteScriptB64' | base64 -d | tr -d '\r' > /tmp/lcs_pull_baseline.sh && chmod +x /tmp/lcs_pull_baseline.sh && /tmp/lcs_pull_baseline.sh '$remoteStage' '$includeVenvFlag' '$JournalLines' '$passwordB64'"

Invoke-PlinkCommand -PlinkPath $plinkPath -Target $target -Command $launchCommand
Invoke-PscpDownload -PscpPath $pscpPath -Target $target -RemotePath $remoteStage -LocalPath $backupRootPath -Recursive

if (-not (Test-Path -LiteralPath $localStage)) {
  throw "Download completed but expected local folder was not found: $localStage"
}

$reportsDir = Join-Path $localStage "reports"
$artifactsDir = Join-Path $localStage "artifacts"
if (-not (Test-Path -LiteralPath $reportsDir)) {
  New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
}

$hashOutputPath = Join-Path $reportsDir "local_artifact_sha256.txt"
if (Test-Path -LiteralPath $artifactsDir) {
  $hashLines = New-Object System.Collections.Generic.List[string]
  Get-ChildItem -LiteralPath $artifactsDir -File | Sort-Object Name | ForEach-Object {
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    $hashLines.Add(("{0}  {1}" -f $hash.Hash.ToLowerInvariant(), $_.Name))
  }
  $hashLines | Set-Content -LiteralPath $hashOutputPath -Encoding ascii
}

$sessionMeta = @{
  capturedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
  piHost = $PiHost
  piUser = $PiUser
  localStage = $localStage
  includeVenv = (-not $SkipVenv)
  journalLines = $JournalLines
}
$sessionMeta | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportsDir "pull_session_meta.json") -Encoding ascii

if (-not $KeepRemoteStage) {
  try {
    Invoke-PlinkCommand -PlinkPath $plinkPath -Target $target -Command "rm -rf '$remoteStage' /tmp/lcs_pull_baseline.sh"
  }
  catch {
    Write-Warning "Remote cleanup failed: $($_.Exception.Message)"
  }
}

Write-Host ""
Write-Host "Baseline pull complete." -ForegroundColor Green
Write-Host "Backup folder: $localStage" -ForegroundColor Green
Write-Host "Artifacts:     $artifactsDir" -ForegroundColor Green
Write-Host "Reports:       $reportsDir" -ForegroundColor Green
Write-Host ""
Write-Host "Next: run scripts\restore_pi_from_baseline.ps1 against a fresh flashed Pi." -ForegroundColor Cyan
