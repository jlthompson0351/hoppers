# Deploy updates to Raspberry Pi
# Run this from: C:\Users\jthompson\Desktop\Scales\deploy_to_pi

$PI_IP = if ($env:PI_HOST) { $env:PI_HOST } else { "172.16.190.25" }
$PI_HOST = "pi@$PI_IP"
$PI_PATH = "/opt/loadcell-transmitter"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploying Industrial Two-Layer Auto-Zero to Pi" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Target host: $PI_IP" -ForegroundColor Cyan
Write-Host ""

# Copy files to Pi
Write-Host "[1/12] Copying routes.py..." -ForegroundColor Yellow
scp "..\src\app\routes.py" "${PI_HOST}:${PI_PATH}/src/app/routes.py"

Write-Host "[2/12] Copying acquisition.py..." -ForegroundColor Yellow
scp "..\src\services\acquisition.py" "${PI_HOST}:${PI_PATH}/src/services/acquisition.py"

Write-Host "[3/12] Copying repo.py..." -ForegroundColor Yellow
scp "..\src\db\repo.py" "${PI_HOST}:${PI_PATH}/src/db/repo.py"

Write-Host "[4/13] Copying zero_tracking.py..." -ForegroundColor Yellow
scp "..\src\core\zero_tracking.py" "${PI_HOST}:${PI_PATH}/src/core/zero_tracking.py"

Write-Host "[5/13] Copying throughput_cycle.py..." -ForegroundColor Yellow
scp "..\src\core\throughput_cycle.py" "${PI_HOST}:${PI_PATH}/src/core/throughput_cycle.py"

Write-Host "[6/13] Copying post_dump_rezero.py..." -ForegroundColor Yellow
scp "..\src\core\post_dump_rezero.py" "${PI_HOST}:${PI_PATH}/src/core/post_dump_rezero.py"

Write-Host "[7/13] Copying zeroing.py..." -ForegroundColor Yellow
scp "..\src\core\zeroing.py" "${PI_HOST}:${PI_PATH}/src/core/zeroing.py"

Write-Host "[8/13] Copying dashboard.html..." -ForegroundColor Yellow
scp "..\src\app\templates\dashboard.html" "${PI_HOST}:${PI_PATH}/src/app/templates/dashboard.html"

Write-Host "[9/13] Copying hdmi.html..." -ForegroundColor Yellow
scp "..\src\app\templates\hdmi.html" "${PI_HOST}:${PI_PATH}/src/app/templates/hdmi.html"

Write-Host "[10/13] Copying settings.html..." -ForegroundColor Yellow
scp "..\src\app\templates\settings.html" "${PI_HOST}:${PI_PATH}/src/app/templates/settings.html"

Write-Host "[11/13] Copying scale_settings.html..." -ForegroundColor Yellow
scp "..\src\app\templates\scale_settings.html" "${PI_HOST}:${PI_PATH}/src/app/templates/scale_settings.html"

Write-Host "[12/13] Copying calibration.html..." -ForegroundColor Yellow
scp "..\src\app\templates\calibration.html" "${PI_HOST}:${PI_PATH}/src/app/templates/calibration.html"

Write-Host "[13/13] Restarting service on Pi..." -ForegroundColor Yellow
ssh $PI_HOST "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Go to http://${PI_IP}:8080" -ForegroundColor White
Write-Host "2. Hard refresh (Ctrl+Shift+R)" -ForegroundColor White
Write-Host "3. Confirm Post-Dump Re-Zero settings exist" -ForegroundColor White
Write-Host "4. Test AZT + Post-Dump behavior" -ForegroundColor White
