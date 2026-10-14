@echo off
rem Doppelklick startet die App. Beim ersten Start installiert uv alle Bibliotheken, das dauert etwas.
rem Mit dem Setup installiert liegt uv neben der App (Ordner uv), sonst muss es installiert sein.
cd /d "%~dp0"
set "UV=%~dp0uv\uv.exe"
if not exist "%UV%" set "UV=uv"
if "%UV%"=="uv" (
    where uv >nul 2>nul
    if errorlevel 1 (
        echo uv fehlt. Einmal in PowerShell ausfuehren: winget install astral-sh.uv
        echo Danach dieses Fenster schliessen und die Datei noch einmal starten.
        pause
        exit /b 1
    )
)
"%UV%" run --no-dev vocaloid_generator\app.py %*
if errorlevel 1 pause
