@echo off
rem Doppelklick startet die App. Beim ersten Start installiert uv alle Bibliotheken, das dauert etwas.
rem Mit dem Setup installiert liegt uv neben der App (Ordner uv), sonst muss es installiert sein.
rem "Vloid Songs starten.bat" --einrichten  installiert nur die Bibliotheken (macht die Setup.exe) und startet nichts.
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
rem Die Setup.exe bringt ihr eigenes Python mit (Ordner python). uv nimmt genau dieses, laedt kein anderes und schaut
rem nicht in AppData\Roaming\uv\python: Die Verknuepfungen, die uv dort anlegt, sperrt Windows manchmal
rem ("nicht vertrauenswuerdiger Bereitstellungspunkt", os error 448), und dann startet nichts.
if exist "%~dp0python\python.exe" (
    set "UV_PYTHON=%~dp0python\python.exe"
    set "UV_PYTHON_DOWNLOADS=never"
    set "UV_PYTHON_INSTALL_DIR=%~dp0uv\python"
)
if "%~1"=="--einrichten" (
    "%UV%" sync --frozen --no-dev
    if errorlevel 1 exit /b 1
    exit /b 0
)
"%UV%" run --no-dev vocaloid_generator\app.py %*
if errorlevel 1 pause
