@echo off
echo [1/2] Installiere Pakete...
python -m pip install flask flask-cors pandas -q

echo [2/2] Starte Server und Karte...
:: Startet den Server minimiert in einem neuen Fenster
start /min "KasselServer" python server.py

:: Wartet 3 Sekunden, damit der Server bereit ist
timeout /t 3 /nobreak >nul

:: Öffnet die Karte
start index.html

echo.
echo ============================================
echo   DER RADAR LAEUFT JETZT!
echo   Dieses Fenster offen lassen.
echo ============================================
pause