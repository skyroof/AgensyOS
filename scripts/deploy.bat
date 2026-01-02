@echo off
REM ============================================================
REM MAX Diagnostic Bot — Deploy Script
REM ============================================================
REM Использование: scripts\deploy.bat "commit message"
REM ============================================================

setlocal

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
ssh root@89.169.47.138 "cd /root/bot && git pull && docker compose down && docker compose up -d --build && docker compose exec -T bot python scripts/add_maxvisual200.py && docker logs diagnostic-bot --tail 20"

echo.
echo ✅ Deploy complete!
pause

