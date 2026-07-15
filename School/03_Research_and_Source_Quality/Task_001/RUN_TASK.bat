@echo off
set PYTHONDONTWRITEBYTECODE=1
python "%~dp0..\..\tooling\schoolctl.py" prepare --task "%~dp0."
pause
