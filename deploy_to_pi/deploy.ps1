# Deploy ZERO vs TARE fix to Raspberry Pi
# Run this from: C:\Users\jthompson\Desktop\hoppers\deploy_to_pi

$PI_HOST = "pi@172.16.190.15"
$PI_PATH = "/home/pi/hoppers"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploying ZERO vs TARE Fix to Pi" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Copy files to Pi
Write-Host "[1/7] Copying routes.py..." -ForegroundColor Yellow
scp routes.py "${PI_HOST}:${PI_PATH}/src/app/routes.py"

Write-Host "[2/7] Copying acquisition.py..." -ForegroundColor Yellow
scp acquisition.py "${PI_HOST}:${PI_PATH}/src/services/acquisition.py"

Write-Host "[3/7] Copying repo.py..." -ForegroundColor Yellow
scp repo.py "${PI_HOST}:${PI_PATH}/src/db/repo.py"

Write-Host "[4/7] Copying dashboard.html..." -ForegroundColor Yellow
scp dashboard.html "${PI_HOST}:${PI_PATH}/src/app/templates/dashboard.html"

Write-Host "[5/7] Copying settings.html..." -ForegroundColor Yellow
scp settings.html "${PI_HOST}:${PI_PATH}/src/app/templates/settings.html"

Write-Host "[6/7] Copying scale_settings.html..." -ForegroundColor Yellow
scp scale_settings.html "${PI_HOST}:${PI_PATH}/src/app/templates/scale_settings.html"

Write-Host "[7/7] Restarting service on Pi..." -ForegroundColor Yellow
ssh $PI_HOST "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Go to http://172.16.190.15:8080" -ForegroundColor White
Write-Host "2. Hard refresh (Ctrl+Shift+R)" -ForegroundColor White
Write-Host "3. Test the ZERO button!" -ForegroundColor White
