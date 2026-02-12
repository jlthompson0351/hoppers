# Deploy updates to Raspberry Pi
# Run this from: C:\Users\jthompson\Desktop\Scales\deploy_to_pi

$PI_IP = if ($env:PI_HOST) { $env:PI_HOST } else { "172.16.190.25" }
$PI_HOST = "pi@$PI_IP"
$PI_PATH = "/opt/loadcell-transmitter"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploying ZERO vs TARE Fix to Pi" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Target host: $PI_IP" -ForegroundColor Cyan
Write-Host ""

# Copy files to Pi
Write-Host "[1/10] Copying routes.py..." -ForegroundColor Yellow
scp "..\src\app\routes.py" "${PI_HOST}:${PI_PATH}/src/app/routes.py"

Write-Host "[2/10] Copying acquisition.py..." -ForegroundColor Yellow
scp "..\src\services\acquisition.py" "${PI_HOST}:${PI_PATH}/src/services/acquisition.py"

Write-Host "[3/10] Copying repo.py..." -ForegroundColor Yellow
scp "..\src\db\repo.py" "${PI_HOST}:${PI_PATH}/src/db/repo.py"

Write-Host "[4/10] Copying zero_tracking.py..." -ForegroundColor Yellow
scp "..\src\core\zero_tracking.py" "${PI_HOST}:${PI_PATH}/src/core/zero_tracking.py"

Write-Host "[5/10] Copying zeroing.py..." -ForegroundColor Yellow
scp "..\src\core\zeroing.py" "${PI_HOST}:${PI_PATH}/src/core/zeroing.py"

Write-Host "[6/10] Copying dashboard.html..." -ForegroundColor Yellow
scp "..\src\app\templates\dashboard.html" "${PI_HOST}:${PI_PATH}/src/app/templates/dashboard.html"

Write-Host "[7/10] Copying settings.html..." -ForegroundColor Yellow
scp "..\src\app\templates\settings.html" "${PI_HOST}:${PI_PATH}/src/app/templates/settings.html"

Write-Host "[8/10] Copying scale_settings.html..." -ForegroundColor Yellow
scp "..\src\app\templates\scale_settings.html" "${PI_HOST}:${PI_PATH}/src/app/templates/scale_settings.html"

Write-Host "[9/10] Copying calibration.html..." -ForegroundColor Yellow
scp "..\src\app\templates\calibration.html" "${PI_HOST}:${PI_PATH}/src/app/templates/calibration.html"

Write-Host "[10/10] Restarting service on Pi..." -ForegroundColor Yellow
ssh $PI_HOST "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Go to http://${PI_IP}:8080" -ForegroundColor White
Write-Host "2. Hard refresh (Ctrl+Shift+R)" -ForegroundColor White
Write-Host "3. Test the ZERO button!" -ForegroundColor White
