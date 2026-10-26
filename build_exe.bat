@echo off
rem Construit TarkovCompanion.exe (un seul dossier, sans Python requis chez l'utilisateur).
rem Prérequis : Python 3.10+ installé. Lance ce fichier par double-clic depuis ce dossier.
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --windowed --name TarkovCompanion --icon assets\icon.ico ^
  --add-data "tarkov_companion\ui;tarkov_companion\ui" ^
  --add-data "tarkov_companion\data;tarkov_companion\data" ^
  main.py
echo.
echo Terminé : dist\TarkovCompanion\TarkovCompanion.exe
pause
