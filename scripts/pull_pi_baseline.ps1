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
  sudo_shell "tar --numeric-owner --xattrs --acls -czf '$ARTIFACTS/$archive_name' -C /$rel_list"
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

if sudo_shell "command -v sqlite3 >/dev/null 2>&1"; then
  if sudo_shell "test -f /var/lib/loadcell-transmitter/data/app.sqlite3"; then
    capture_sudo "$REPORTS/sqlite_integrity_check.txt" "sqlite3 /var/lib/loadcell-transmitter/data/app.sqlite3 'PRAGMA integrity_check;'"
  elif sudo_shell "test -f /var/lib/loadcell-transmitter/app.sqlite3"; then
    capture_sudo "$REPORTS/sqlite_integrity_check.txt" "sqlite3 /var/lib/loadcell-transmitter/app.sqlite3 'PRAGMA integrity_check;'"
  fi
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

create_tar "var_lib_loadcell_transmitter.tar.gz" \
  "var/lib/loadcell-transmitter"

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
$launchCommand = "echo '$remoteScriptB64' | base64 -d > /tmp/lcs_pull_baseline.sh && chmod +x /tmp/lcs_pull_baseline.sh && /tmp/lcs_pull_baseline.sh '$remoteStage' '$includeVenvFlag' '$JournalLines' '$passwordB64'"

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
