@echo off
setlocal
cd /d "%~dp0\.."
if not exist ".desktop-venv\Scripts\python.exe" (
  echo Creating isolated Python build environment...
  "D:\Anaconda\python.exe" -m venv .desktop-venv
  if errorlevel 1 exit /b 1
)
echo Preparing backend build dependencies...
".desktop-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-desktop.txt
if errorlevel 1 exit /b 1
echo Packaging Flask backend...
".desktop-venv\Scripts\python.exe" scripts\build_backend.py
exit /b %errorlevel%
