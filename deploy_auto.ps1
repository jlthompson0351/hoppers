$PW = "depor"
$PI_TARGET = "pi@172.16.190.25"
$DEST = "/opt/loadcell-transmitter"

Write-Host "Deploying..."

# Core logic
echo y | pscp -pw $PW src/core/throughput_cycle.py ${PI_TARGET}:${DEST}/src/core/
echo y | pscp -pw $PW src/core/zero_tracking.py ${PI_TARGET}:${DEST}/src/core/
echo y | pscp -pw $PW src/core/post_dump_rezero.py ${PI_TARGET}:${DEST}/src/core/
echo y | pscp -pw $PW src/core/zeroing.py ${PI_TARGET}:${DEST}/src/core/

# Services & DB
echo y | pscp -pw $PW src/services/acquisition.py ${PI_TARGET}:${DEST}/src/services/
echo y | pscp -pw $PW src/db/repo.py ${PI_TARGET}:${DEST}/src/db/

# App
echo y | pscp -pw $PW src/app/routes.py ${PI_TARGET}:${DEST}/src/app/
echo y | pscp -pw $PW src/app/templates/dashboard.html ${PI_TARGET}:${DEST}/src/app/templates/
echo y | pscp -pw $PW src/app/templates/hdmi.html ${PI_TARGET}:${DEST}/src/app/templates/hdmi.html
echo y | pscp -pw $PW src/app/templates/settings.html ${PI_TARGET}:${DEST}/src/app/templates/settings.html
echo y | pscp -pw $PW src/app/templates/scale_settings.html ${PI_TARGET}:${DEST}/src/app/templates/scale_settings.html
echo y | pscp -pw $PW src/app/templates/calibration.html ${PI_TARGET}:${DEST}/src/app/templates/calibration.html

Write-Host "Restarting service..."
echo y | plink -pw $PW $PI_TARGET "sudo systemctl restart loadcell-transmitter && sleep 2 && sudo systemctl status loadcell-transmitter"

Write-Host "Done."
