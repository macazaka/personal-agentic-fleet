@echo off
setlocal
cd /d "%~dp0"

echo Starting Personal Agentic Fleet Control Center in background...
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%~dp0fleet\app.py"
) else (
    start "" pythonw "%~dp0fleet\app.py"
)

echo Control Center running at http://127.0.0.1:7890
ping -n 3 127.0.0.1 >nul
