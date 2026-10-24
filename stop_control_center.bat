@echo off
setlocal
cd /d "%~dp0"

echo Stopping Personal Agentic Fleet Control Center...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7890 -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
if exist "fleet\data\fleet.pid" del /f /q "fleet\data\fleet.pid" >nul 2>&1
echo Done. Control Center stopped.
ping -n 3 127.0.0.1 >nul
