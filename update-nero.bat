@echo off
REM ============================================================
REM  Update Nero — double-click this to grab the latest, then start.
REM  It lives in your project folder and always knows where it is,
REM  so it works no matter what directory you're in.
REM ============================================================
setlocal
cd /d "%~dp0"

echo === Updating Nero ===
git fetch origin
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
git reset --hard "origin/%BRANCH%"
echo.

echo === Freeing port 8080 (if something is holding it) ===
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
echo.

echo === Starting Nero — leave this window open ===
".venv\Scripts\python.exe" run.py

echo.
echo Nero stopped. Press any key to close.
pause >nul
