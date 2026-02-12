$PI_HOST = "pi@172.16.190.25"
$PI_PATH = "/opt/loadcell-transmitter"
$ROOT = "C:\Users\jthompson\Desktop\hoppers"
$PW = "depor"

Write-Host "Pushing Dynamic Label fix to Pi..."
pscp -pw $PW "$ROOT\src\app\templates\calibration.html" "${PI_HOST}:${PI_PATH}/src/app/templates/calibration.html"

Write-Host "Restarting service..."
plink -pw $PW $PI_HOST "sudo systemctl restart loadcell-transmitter"
Write-Host "Done! Please hard-refresh your browser."
