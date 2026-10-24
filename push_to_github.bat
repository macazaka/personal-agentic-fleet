@echo off
echo ===================================================
echo Pushing Personal Agentic Fleet to GitHub (macazaka)
echo ===================================================
cd /d "Z:\Hobbies - Code\0001 - Test"
"C:\Users\Pavan Kota\AppData\Local\Programs\Git\cmd\git.exe" push -u origin main
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo SUCCESS: Fleet has been pushed to GitHub!
    echo View repository at: https://github.com/macazaka/personal-agentic-fleet
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo PUSH FAILED: Please make sure you have:
    echo 1. Added your SSH Key to GitHub at https://github.com/settings/ssh/new
    echo 2. Created the empty repository 'fleet' at https://github.com/new
    echo ===================================================
)
pause

