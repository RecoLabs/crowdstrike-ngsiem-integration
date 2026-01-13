@echo off
setlocal enabledelayedexpansion

REM Step 1: Check for Python
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python is not installed. Please install Python 3 manually and re-run this script.
    exit /b 1
) else (
    echo [*] Python is already installed.
)

REM Step 2: Create virtual environment
if exist venv (
    echo [*] Removing old virtual environment...
    rmdir /s /q venv
)
echo [*] Creating virtual environment...
python -m venv venv

REM Step 3: Install Python packages
echo [*] Installing pip packages...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install pyyaml requests >nul

REM Step 4: Read cron expressions and extract minute frequency using Python
if not exist config.yaml (
    echo [!] config.yaml not found.
    exit /b 1
)

for /f "delims=" %%i in ('venv\Scripts\python -c "import yaml; print(yaml.safe_load(open('config.yaml')).get('posture', {}).get('cron', ''))"') do set POSTURE_CRON=%%i
for /f "delims=" %%i in ('venv\Scripts\python -c "import yaml; print(yaml.safe_load(open('config.yaml')).get('alerts', {}).get('cron', ''))"') do set ALERTS_CRON=%%i

if "%POSTURE_CRON%"=="" (
    echo [!] Posture cron value missing.
    exit /b 1
)
if "%ALERTS_CRON%"=="" (
    echo [!] Alerts cron value missing.
    exit /b 1
)

REM Extract */N from cron using Python
for /f %%i in ('venv\Scripts\python -c "import re; print(re.search(r'\*/(\d+)', r'%POSTURE_CRON%').group(1))"') do set POSTURE_FREQ=%%i
for /f %%i in ('venv\Scripts\python -c "import re; print(re.search(r'\*/(\d+)', r'%ALERTS_CRON%').group(1))"') do set ALERTS_FREQ=%%i

echo [*] Posture frequency: every %POSTURE_FREQ% minute(s)
echo [*] Alerts frequency:  every %ALERTS_FREQ% minute(s)

REM Step 5: Get current time and date for immediate start
for /f "tokens=2 delims==" %%i in ('"wmic os get LocalDateTime /value"') do set dt=%%i
set CURRENT_DATE=%dt:~6,2%/%dt:~4,2%/%dt:~0,4%
set CURRENT_TIME=%dt:~8,2%:%dt:~10,2%
echo [*] Using start time: %CURRENT_TIME% on %CURRENT_DATE%

REM Step 6: Schedule the tasks
echo [*] Scheduling tasks...
schtasks /Delete /TN "PostureJob" /F >nul 2>nul
schtasks /Delete /TN "AlertsJob" /F >nul 2>nul

set "PYTHON_EXEC=%cd%\venv\Scripts\python.exe"
set "POSTURE_SCRIPT=%cd%\posture.py"
set "ALERTS_SCRIPT=%cd%\alerts.py"

REM Step 7: Set scheduled tasks
set "PYTHON_EXEC=%cd%\venv\Scripts\pythonw.exe"
set "POSTURE_SCRIPT=%cd%\posture.py"
set "ALERTS_SCRIPT=%cd%\alerts.py"

schtasks /Create /SC MINUTE /MO %POSTURE_FREQ% /TN "PostureJob" ^
  /TR "\"%PYTHON_EXEC%\" \"%POSTURE_SCRIPT%\"" /F

schtasks /Create /SC MINUTE /MO %ALERTS_FREQ% /TN "AlertsJob" ^
  /TR "\"%PYTHON_EXEC%\" \"%ALERTS_SCRIPT%\"" /F


echo.
echo [✅] Successfully scheduled PostureJob and AlertsJob.
endlocal
