@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator permission...
  powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
EZVIZDashboard.exe install
if errorlevel 1 goto :failed
EZVIZMotion.exe install
if errorlevel 1 goto :failed
EZVIZDashboard.exe start
EZVIZMotion.exe start
echo.
echo Services installed and started successfully.
echo Open services.msc to Start, Stop, or Restart them.
pause
exit /b 0
:failed
echo.
echo Service installation failed. Review the message above.
pause
exit /b 1

