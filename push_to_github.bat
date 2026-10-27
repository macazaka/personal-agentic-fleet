@echo off
echo ===================================================
echo Autonomous Auto-Fix & GitHub Upload (Zero Intervention)
echo ===================================================
cd /d "%~dp0"
python -m fleet.tools.auto_fixer --stage
git diff --cached --quiet
if %ERRORLEVEL% NEQ 0 (
    git commit -m "chore(autofix): automatically resolve VSCode and CodeQL diagnostics"
)
git push -u origin main
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo SUCCESS: Fleet has been automatically verified and pushed to GitHub!
    echo View repository at: https://github.com/macazaka/personal-agentic-fleet
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo PUSH FAILED: Check network or repository permissions.
    echo ===================================================
    exit /b 1
)
