# Deploy ZERO vs TARE Fix to Pi
# This script will prompt for the Pi password once

$PI_USER = "pi"
$PI_HOST = "172.16.190.15"
$PI_PATH = "/home/pi/hoppers"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploy ZERO Fix to Pi" -ForegroundColor Cyan  
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Get password from user
$password = Read-Host "Enter Pi password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Deploy files using plink and pscp
Write-Host "[1/6] Copying routes.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword routes.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/

Write-Host "[2/6] Copying acquisition.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword acquisition.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/services/

Write-Host "[3/6] Copying repo.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword repo.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/db/

Write-Host "[4/6] Copying dashboard.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword dashboard.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[5/6] Copying settings.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[6/6] Copying scale_settings.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword scale_settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host ""
Write-Host "Restarting service..." -ForegroundColor Yellow
echo y | plink -pw $plainPassword ${PI_USER}@${PI_HOST} "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Go to http://172.16.190.15:8080 and test!" -ForegroundColor Cyan
