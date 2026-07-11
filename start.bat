@echo off
REM Start Nero on Windows. Double-click this file, or run it from PowerShell:  .\start.bat
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup needed. Running bootstrap...
    python bootstrap.py
) else (
    ".venv\Scripts\python.exe" run.py
)

pause
