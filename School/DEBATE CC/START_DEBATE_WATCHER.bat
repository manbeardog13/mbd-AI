@echo off
setlocal
title Nero School - Debate CC watcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_debate.ps1"
endlocal
