@echo off
REM Personal Agentic Fleet — Silent Windows Launcher with Python >=3.10 & Security Verification
SETLOCAL EnableDelayedExpansion
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -Launch
exit /b %ERRORLEVEL%
