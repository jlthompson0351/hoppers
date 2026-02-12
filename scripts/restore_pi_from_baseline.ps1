param(
  [Parameter(Mandatory = $true)][string]$BackupPath,
  [string]$PiHost = "172.16.190.25",
  [string]$PiUser = "pi",
  [SecureString]$PiPassword,
  [switch]$SkipAptInstall,
  [switch]$RestoreIdentityNetwork,
  [switch]$RestoreBootConfig,
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

function Invoke-PscpUpload {
  param(
    [Parameter(Mandatory = $true)][string]$PscpPath,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [switch]$Recursive
  )
  $pscpArgs = @("-batch", "-pw", $script:PlainPassword)
  if ($Recursive) {
    $pscpArgs += "-r"
  }
  $pscpArgs += @($LocalPath, "${Target}:$RemotePath")
  & $PscpPath @pscpArgs
  if ($LASTEXITCODE -ne 0) {
    throw "pscp upload failed with exit code $LASTEXITCODE."
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

$plinkPath = Get-ExecutablePath -Name "plink"
$pscpPath = Get-ExecutablePath -Name "pscp"

if (-not (Test-Path -LiteralPath $BackupPath)) {
  throw "BackupPath does not exist: $BackupPath"
}
$backupFullPath = (Resolve-Path -LiteralPath $BackupPath).Path
$artifactsPath = Join-Path $backupFullPath "artifacts"
if (-not (Test-Path -LiteralPath $artifactsPath)) {
  throw "Artifacts folder not found under backup path: $artifactsPath"
}

$requiredArtifacts = @(
  "opt_loadcell_transmitter.tar.gz",
  "var_lib_loadcell_transmitter.tar.gz",
  "etc_loadcell_service.tar.gz"
)
foreach ($artifact in $requiredArtifacts) {
  $artifactPath = Join-Path $artifactsPath $artifact
  if (-not (Test-Path -LiteralPath $artifactPath)) {
    throw "Required artifact missing: $artifactPath"
  }
}

if (-not $PiPassword) {
  $PiPassword = Read-Host "Enter Pi password for $PiUser@$PiHost" -AsSecureString
}
$script:PlainPassword = Get-PlainTextFromSecureString -SecureValue $PiPassword
$passwordB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script:PlainPassword))

$hostSlug = ($PiHost -replace "[^A-Za-z0-9\.-]", "_")
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$remoteStage = "/tmp/pi-restore-$hostSlug-$stamp"
$target = "$PiUser@$PiHost"
$skipAptFlag = if ($SkipAptInstall) { "1" } else { "0" }
$restoreIdentityFlag = if ($RestoreIdentityNetwork) { "1" } else { "0" }
$restoreBootFlag = if ($RestoreBootConfig) { "1" } else { "0" }

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "Restoring Pi from baseline backup" -ForegroundColor Cyan
Write-Host "Target: $target" -ForegroundColor Cyan
Write-Host "Backup: $backupFullPath" -ForegroundColor Cyan
Write-Host "Skip apt install: $($skipAptFlag -eq '1')" -ForegroundColor Cyan
Write-Host "Restore identity/network: $($restoreIdentityFlag -eq '1')" -ForegroundColor Cyan
Write-Host "Restore boot config: $($restoreBootFlag -eq '1')" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

$remoteScript = @'
#!/usr/bin/env bash
set -euo pipefail

STAGE_DIR="$1"
SKIP_APT="$2"
RESTORE_IDENTITY="$3"
RESTORE_BOOT="$4"
SUDO_PASS_B64="${5:-}"

ARTIFACTS="$STAGE_DIR/artifacts"
REPORTS="$STAGE_DIR/restore_reports"
mkdir -p "$REPORTS"

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

log_step() {
  local message="$1"
  echo "[$(date -u --iso-8601=seconds)] $message" | tee -a "$REPORTS/restore_steps.log"
}

if [ ! -d "$ARTIFACTS" ]; then
  echo "Artifacts folder not found: $ARTIFACTS" >&2
  exit 2
fi

log_step "Restore started."
capture_cmd "$REPORTS/date_utc_pre_restore.txt" "date -u --iso-8601=seconds"
capture_cmd "$REPORTS/uname_pre_restore.txt" "uname -a"
capture_cmd "$REPORTS/os_release_pre_restore.txt" "cat /etc/os-release"

if [ "$SKIP_APT" != "1" ]; then
  log_step "Installing OS prerequisites (apt)."
  capture_sudo "$REPORTS/apt_update.txt" "apt-get update"
  capture_sudo "$REPORTS/apt_install.txt" "apt-get install -y python3 python3-venv python3-pip python3-dev i2c-tools git sqlite3"
else
  log_step "Skipping apt install as requested."
fi

log_step "Restoring application code."
if [ -f "$ARTIFACTS/opt_loadcell_transmitter.tar.gz" ]; then
  capture_sudo "$REPORTS/restore_opt_code.txt" "rm -rf /opt/loadcell-transmitter && mkdir -p /opt && tar -xzf '$ARTIFACTS/opt_loadcell_transmitter.tar.gz' -C /"
else
  echo "Missing artifact: opt_loadcell_transmitter.tar.gz" >>"$REPORTS/restore_steps.log"
fi

if [ -f "$ARTIFACTS/home_pi_hoppers_legacy.tar.gz" ]; then
  log_step "Restoring legacy /home/pi/hoppers snapshot."
  capture_sudo "$REPORTS/restore_home_pi_hoppers_legacy.txt" "tar -xzf '$ARTIFACTS/home_pi_hoppers_legacy.tar.gz' -C /"
fi

log_step "Restoring runtime data."
if [ -f "$ARTIFACTS/var_lib_loadcell_transmitter.tar.gz" ]; then
  capture_sudo "$REPORTS/restore_var_data.txt" "rm -rf /var/lib/loadcell-transmitter && mkdir -p /var/lib/loadcell-transmitter && tar -xzf '$ARTIFACTS/var_lib_loadcell_transmitter.tar.gz' -C /"
else
  echo "Missing artifact: var_lib_loadcell_transmitter.tar.gz" >>"$REPORTS/restore_steps.log"
fi

log_step "Restoring service unit."
if [ -f "$ARTIFACTS/etc_loadcell_service.tar.gz" ]; then
  capture_sudo "$REPORTS/restore_service_unit.txt" "tar -xzf '$ARTIFACTS/etc_loadcell_service.tar.gz' -C /"
else
  echo "Missing artifact: etc_loadcell_service.tar.gz" >>"$REPORTS/restore_steps.log"
fi

if [ "$RESTORE_IDENTITY" = "1" ]; then
  log_step "Restoring identity/network config."
  if [ -f "$ARTIFACTS/etc_identity_network.tar.gz" ]; then
    capture_sudo "$REPORTS/restore_identity_network.txt" "tar -xzf '$ARTIFACTS/etc_identity_network.tar.gz' -C /"
  else
    echo "Identity/network artifact missing; skipped." >>"$REPORTS/restore_steps.log"
  fi
else
  log_step "Skipping identity/network restore."
fi

if [ "$RESTORE_BOOT" = "1" ]; then
  log_step "Restoring boot config files."
  if [ -f "$ARTIFACTS/boot_config.tar.gz" ]; then
    capture_sudo "$REPORTS/restore_boot_config.txt" "tar -xzf '$ARTIFACTS/boot_config.tar.gz' -C /"
  else
    echo "Boot config artifact missing; skipped." >>"$REPORTS/restore_steps.log"
  fi
else
  log_step "Skipping boot config restore."
fi

if [ -f "$ARTIFACTS/home_pi_kiosk_files.tar.gz" ]; then
  log_step "Restoring kiosk user files."
  capture_sudo "$REPORTS/restore_home_pi_kiosk_files.txt" "tar -xzf '$ARTIFACTS/home_pi_kiosk_files.tar.gz' -C /"
fi

capture_sudo "$REPORTS/chown_application_paths.txt" "chown -R pi:pi /opt/loadcell-transmitter /var/lib/loadcell-transmitter"

if [ -f /opt/loadcell-transmitter/scripts/install_pi.sh ]; then
  log_step "Rebuilding Python environment from requirements."
  capture_cmd "$REPORTS/rebuild_python_env.txt" "cd /opt/loadcell-transmitter && bash ./scripts/install_pi.sh"
else
  log_step "install_pi.sh missing; falling back to manual venv setup."
  capture_cmd "$REPORTS/rebuild_python_env_fallback.txt" "cd /opt/loadcell-transmitter && python3 -m venv .venv && ./.venv/bin/python -m pip install --upgrade pip && ./.venv/bin/pip install -r requirements.txt"
fi

log_step "Restarting and validating loadcell service."
capture_sudo "$REPORTS/systemctl_daemon_reload.txt" "systemctl daemon-reload"
capture_sudo "$REPORTS/systemctl_enable.txt" "systemctl enable loadcell-transmitter"
capture_sudo "$REPORTS/systemctl_restart.txt" "systemctl restart loadcell-transmitter"
sleep 3
capture_sudo "$REPORTS/systemctl_is_active.txt" "systemctl is-active loadcell-transmitter"
capture_sudo "$REPORTS/systemctl_status.txt" "systemctl status loadcell-transmitter --no-pager"
capture_sudo "$REPORTS/journal_after_restore.txt" "journalctl -u loadcell-transmitter -n 400 --no-pager"

if [ -f /home/pi/.config/systemd/user/kiosk.service ]; then
  log_step "Re-enabling kiosk user service."
  capture_sudo "$REPORTS/kiosk_enable_linger.txt" "loginctl enable-linger pi"
  capture_sudo "$REPORTS/kiosk_enable_service.txt" "sudo -u pi XDG_RUNTIME_DIR=/run/user/\$(id -u pi) systemctl --user daemon-reload && sudo -u pi XDG_RUNTIME_DIR=/run/user/\$(id -u pi) systemctl --user enable kiosk.service"
fi

{
  echo "### COMMAND (sudo): i2cdetect -y 1 (fallback to /usr/sbin/i2cdetect)"
  if sudo_shell "command -v i2cdetect >/dev/null 2>&1"; then
    sudo_shell "i2cdetect -y 1"
  elif sudo_shell "test -x /usr/sbin/i2cdetect"; then
    sudo_shell "/usr/sbin/i2cdetect -y 1"
  else
    echo "i2cdetect not found on this Pi."
  fi
} >"$REPORTS/i2cdetect_post_restore.txt" 2>&1 || true

capture_cmd "$REPORTS/date_utc_post_restore.txt" "date -u --iso-8601=seconds"
capture_cmd "$REPORTS/ip_addr_post_restore.txt" "ip -brief addr"

{
  echo "restore_completed_utc=$(date -u --iso-8601=seconds)"
  echo "skip_apt=$SKIP_APT"
  echo "restore_identity_network=$RESTORE_IDENTITY"
  echo "restore_boot_config=$RESTORE_BOOT"
} >"$REPORTS/restore_summary.txt"

CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
sudo_shell "chown -R '$CURRENT_USER:$CURRENT_GROUP' '$STAGE_DIR'" || true
rm -f /tmp/lcs_restore_from_baseline.sh || true
log_step "Restore completed."
'@

$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
$launchCommand = "echo '$remoteScriptB64' | base64 -d > /tmp/lcs_restore_from_baseline.sh && chmod +x /tmp/lcs_restore_from_baseline.sh && /tmp/lcs_restore_from_baseline.sh '$remoteStage' '$skipAptFlag' '$restoreIdentityFlag' '$restoreBootFlag' '$passwordB64'"

Invoke-PlinkCommand -PlinkPath $plinkPath -Target $target -Command "mkdir -p '$remoteStage'"
Invoke-PscpUpload -PscpPath $pscpPath -Target $target -LocalPath $artifactsPath -RemotePath $remoteStage -Recursive
Invoke-PlinkCommand -PlinkPath $plinkPath -Target $target -Command $launchCommand

$localRestoreReportsRoot = Join-Path $backupFullPath "restore-reports"
if (-not (Test-Path -LiteralPath $localRestoreReportsRoot)) {
  New-Item -ItemType Directory -Path $localRestoreReportsRoot -Force | Out-Null
}
Invoke-PscpDownload -PscpPath $pscpPath -Target $target -RemotePath "$remoteStage/restore_reports" -LocalPath $localRestoreReportsRoot -Recursive

if (-not $KeepRemoteStage) {
  try {
    Invoke-PlinkCommand -PlinkPath $plinkPath -Target $target -Command "rm -rf '$remoteStage' /tmp/lcs_restore_from_baseline.sh"
  }
  catch {
    Write-Warning "Remote cleanup failed: $($_.Exception.Message)"
  }
}

Write-Host ""
Write-Host "Restore complete." -ForegroundColor Green
Write-Host "Local restore reports: $localRestoreReportsRoot" -ForegroundColor Green
Write-Host ""
Write-Host "Immediate checks:" -ForegroundColor Cyan
Write-Host "1) Open: http://$PiHost`:8080" -ForegroundColor White
Write-Host "2) Verify service: plink -pw <pw> $PiUser@$PiHost `"sudo systemctl status loadcell-transmitter --no-pager`"" -ForegroundColor White
Write-Host "3) Verify boards online and weight updates in dashboard." -ForegroundColor White
