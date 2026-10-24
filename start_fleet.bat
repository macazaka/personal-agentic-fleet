@echo off
REM Personal Agentic Fleet -- Silent Windows 10 & 11 Launcher with PowerShell 7 / 5.1 & Security Verification
SETLOCAL EnableDelayedExpansion
cd /d "%~dp0"

REM 1. Prefer modern PowerShell 7 (pwsh.exe) if installed, fallback to Windows PowerShell 5.1
set "PS_EXE=powershell.exe"
if exist "%LOCALAPPDATA%\Programs\PowerShell\7\pwsh.exe" (
    set "PS_EXE=%LOCALAPPDATA%\Programs\PowerShell\7\pwsh.exe"
) else (
    where pwsh >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "PS_EXE=pwsh"
)

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -Launch
exit /b %ERRORLEVEL%

