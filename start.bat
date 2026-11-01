@echo off
setlocal
cd /d "%~dp0"
echo Starting Course Project Review Platform...
echo Open http://127.0.0.1:5000 in your browser.
start "" http://127.0.0.1:5000
"D:\Anaconda\python.exe" backend\app.py
if errorlevel 1 (
  echo.
  echo Start failed. Install dependencies with:
  echo D:\Anaconda\python.exe -m pip install -r backend\requirements.txt
  pause
)
