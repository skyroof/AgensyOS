@echo off
REM ============================================================
REM MAX Diagnostic Bot — Deploy Script
REM ============================================================
REM Использование: scripts\deploy.bat "commit message"
REM ============================================================

setlocal

REM === STEP 0: SYNTAX CHECK ===
call scripts\check_syntax.bat
if %ERRORLEVEL% NEQ 0 (
    echo ⛔ Deploy cancelled due to syntax errors.
    exit /b 1
)

if "%~1"=="" (
    set /p COMMIT_MSG="Commit message: "
) else (
    set COMMIT_MSG=%~1
)

echo.
echo [1/4] Adding files...
git add -A

echo [2/4] Committing: %COMMIT_MSG%
git commit -m "%COMMIT_MSG%"

echo [3/4] Pushing to GitHub...
git push origin main

echo [4/4] Deploying to server...
ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 root@89.169.47.138 "cd /root/bot && git pull && chmod +x deploy.sh && ./deploy.sh"

echo.
echo ✅ Deploy complete!

