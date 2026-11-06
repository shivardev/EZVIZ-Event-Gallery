@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator permission...
  powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
EZVIZMotion.exe stop
EZVIZMotion.exe uninstall
EZVIZDashboard.exe stop
EZVIZDashboard.exe uninstall
echo Services removed. Project files and event media were preserved.
pause

