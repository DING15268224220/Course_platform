@echo off
setlocal
set "LAUNCHER=%~dp0tools\launcher.ps1"

if not exist "%LAUNCHER%" (
  echo Launcher file is missing: %LAUNCHER%
  pause
  exit /b 1
)

where pwsh.exe >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" %*
) else (
  pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" %*
)

if errorlevel 1 (
  echo.
  echo The launcher stopped because an operation failed.
  pause
)
endlocal
