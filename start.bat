@echo off
REM Start Nero on Windows. Double-click this file, or run it from PowerShell:  .\start.bat
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup needed. Running bootstrap...
    REM Prefer the 'py' launcher: it's on PATH even when the python.org
    REM installer's "Add to PATH" box was left unticked, so it avoids the
    REM Microsoft Store stub that a bare 'python' would open.
    where py >nul 2>nul && ( py -3 bootstrap.py ) || ( python bootstrap.py )
) else (
    ".venv\Scripts\python.exe" run.py
)

pause
