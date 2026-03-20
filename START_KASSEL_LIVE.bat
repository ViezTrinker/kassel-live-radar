@echo off
title Kassel Radar Local Server
echo [1/3] Bereinige alte Verbindungen...
taskkill /f /im python.exe /t >nul 2>&1

echo [2/3] Starte Python Server im Hintergrund...
cd /d "%~dp0"
:: Startet Python in einem eigenen Prozess, damit die Batch weiterläuft
start /b python server.py

echo [3/3] Warte kurz auf Daten-Initialisierung...
timeout /t 3 /nobreak >nul

echo [FERTIG] Oeffne Radar im Browser...
start http://localhost:5000

:: Hält das Fenster offen, falls Python Fehlermeldungen ausgibt
echo Server läuft. Fenster nicht schliessen!
pause