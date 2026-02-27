# Deploy updates to Pi
# This script will prompt for the Pi password once

$PI_USER = "pi"
$PI_HOST = if ($env:PI_HOST) { $env:PI_HOST } else { "172.16.190.25" }
$PI_PATH = "/opt/loadcell-transmitter"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploy Industrial Two-Layer Auto-Zero to Pi" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Target host: $PI_HOST" -ForegroundColor Cyan
Write-Host ""

# Get password from user
$password = Read-Host "Enter Pi password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Deploy files using plink and pscp
Write-Host "[1/12] Copying routes.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\routes.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/

Write-Host "[2/12] Copying acquisition.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\services\acquisition.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/services/

Write-Host "[3/12] Copying repo.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\db\repo.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/db/

Write-Host "[4/12] Copying zero_tracking.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\core\zero_tracking.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[5/12] Copying throughput_cycle.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\core\throughput_cycle.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[6/12] Copying post_dump_rezero.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\core\post_dump_rezero.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[7/12] Copying zeroing.py..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\core\zeroing.py ${PI_USER}@${PI_HOST}:${PI_PATH}/src/core/

Write-Host "[8/12] Copying dashboard.html..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\templates\dashboard.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[9/12] Copying hdmi.html..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\templates\hdmi.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[10/12] Copying settings.html..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\templates\settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[11/12] Copying scale_settings.html..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\templates\scale_settings.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host "[12/12] Copying calibration.html..." -ForegroundColor Yellow
Write-Output y | pscp -pw $plainPassword ..\src\app\templates\calibration.html ${PI_USER}@${PI_HOST}:${PI_PATH}/src/app/templates/

Write-Host ""
Write-Host "Restarting service..." -ForegroundColor Yellow
Write-Output y | plink -pw $plainPassword ${PI_USER}@${PI_HOST} "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Go to http://${PI_HOST}:8080 and test!" -ForegroundColor Cyan
