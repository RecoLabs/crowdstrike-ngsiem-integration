@echo off
setlocal

echo [*] Removing scheduled tasks...

REM Delete PostureJob if exists
schtasks /Query /TN "PostureJob" >nul 2>&1
if %errorlevel%==0 (
    schtasks /Delete /TN "PostureJob" /F
    echo [✓] PostureJob removed.
) else (
    echo [!] PostureJob not found.
)

REM Delete AlertsJob if exists
schtasks /Query /TN "AlertsJob" >nul 2>&1
if %errorlevel%==0 (
    schtasks /Delete /TN "AlertsJob" /F
    echo [✓] AlertsJob removed.
) else (
    echo [!] AlertsJob not found.
)

echo [✅] Uninstallation complete.
endlocal
