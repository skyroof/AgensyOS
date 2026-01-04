@echo off
echo ========================================================
echo 🔍 Running Syntax Check...
echo ========================================================

python -m compileall -q src/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ SYNTAX ERROR FOUND!
    echo Please fix the errors above before deploying.
    exit /b 1
)

echo.
echo ✅ Syntax check passed! No obvious errors.
echo ========================================================
