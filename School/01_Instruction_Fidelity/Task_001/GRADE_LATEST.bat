@echo off
set PYTHONDONTWRITEBYTECODE=1
python "%~dp0..\..\tooling\schoolctl.py" grade --task "%~dp0."
pause
