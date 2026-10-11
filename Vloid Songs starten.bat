@echo off
rem Doppelklick startet die App. Beim ersten Start installiert uv alle Bibliotheken, das dauert etwas.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo uv fehlt. Einmal in PowerShell ausfuehren: winget install astral-sh.uv
    echo Danach dieses Fenster schliessen und die Datei noch einmal starten.
    pause
    exit /b 1
)
uv run vocaloid_generator\app.py %*
if errorlevel 1 pause
