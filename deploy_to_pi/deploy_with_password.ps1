# Deploy updates to Pi
# This script will prompt for the Pi password once

$PI_USER = "pi"
$PI_HOST = if ($env:PI_HOST) { $env:PI_HOST } else { "172.16.190.25" }
$PI_PATH = "/opt/loadcell-transmitter"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploy ZERO Fix to Pi" -ForegroundColor Cyan  
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Target host: $PI_HOST" -ForegroundColor Cyan
Write-Host ""

# Get password from user
$password = Read-Host "Enter Pi password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Deploy files using plink and pscp
Write-Host "[1/9] Copying routes.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\app\routes.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/

Write-Host "[2/9] Copying acquisition.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\services\acquisition.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/services/

Write-Host "[3/9] Copying repo.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\db\repo.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/db/

Write-Host "[4/9] Copying zero_tracking.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\core\zero_tracking.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[5/9] Copying zeroing.py..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\core\zeroing.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[6/9] Copying dashboard.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\app\templates\dashboard.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[7/9] Copying settings.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\app\templates\settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[8/9] Copying scale_settings.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\app\templates\scale_settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[9/9] Copying calibration.html..." -ForegroundColor Yellow
echo y | pscp -pw $plainPassword ..\src\app\templates\calibration.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host ""
Write-Host "Restarting service..." -ForegroundColor Yellow
echo y | plink -pw $plainPassword ${PI_USER}@${PI_HOST} "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Go to http://${PI_HOST}:8080 and test!" -ForegroundColor Cyan
