@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python n'est pas installe. Telecharge-le sur https://www.python.org/downloads/ ^(coche "Add python.exe to PATH"^).
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Premiere installation, un instant...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo Echec de l'installation des dependances.
    pause
    exit /b 1
  )
)
start "" ".venv\Scripts\pythonw.exe" main.py %*
