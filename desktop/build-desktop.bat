@echo off
setlocal
cd /d "%~dp0"
echo Installing Electron dependencies...
call npm install
if errorlevel 1 goto :failed
echo Building portable Windows desktop application...
call npm run dist:win
if errorlevel 1 goto :failed
echo.
echo Build complete. See the release folder.
pause
exit /b 0
:failed
echo.
echo Desktop build failed. Review the output above.
pause
exit /b 1
