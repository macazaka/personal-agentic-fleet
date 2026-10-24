@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_autostart.ps1" -Action enable
ping -n 4 127.0.0.1 >nul
