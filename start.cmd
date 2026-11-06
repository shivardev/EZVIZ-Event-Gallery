@echo off
cd /d "%~dp0"
if not exist ".env" (
  echo Missing .env file.
  echo Copy .env.example to .env and enter the EZVIZ verification code.
  pause
  exit /b 1
)
start "EZVIZ Motion GIF Worker" /b "%~dp0runtime\Scripts\python.exe" "%~dp0motion_gif.py"
"%~dp0runtime\Scripts\python.exe" "%~dp0app.py"
