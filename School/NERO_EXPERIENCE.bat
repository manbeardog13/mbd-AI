@echo off
setlocal
title Nero Experience - Live Evidence Dashboard
set "PYTHONDONTWRITEBYTECODE=1"
python "%~dp0tooling\schoolctl.py" dashboard --watch --interval 2
if errorlevel 1 (
  echo.
  echo Unable to open the dashboard. Verify that Python is available.
  pause
)
endlocal
