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
rem uv laedt ein Paket nach dem anderen: Laedt es mehrere grosse gleichzeitig, bleiben die Downloads auf manchen
rem PCs stehen (bei Striker scipy und llvmlite bei 1,19 MB).
if exist "%~dp0python\python.exe" (
    set "UV_PYTHON=%~dp0python\python.exe"
    set "UV_PYTHON_DOWNLOADS=never"
    set "UV_PYTHON_INSTALL_DIR=%~dp0uv\python"
    set "UV_CONCURRENT_DOWNLOADS=1"
)
if "%~1"=="--einrichten" (
    title Vloid Songs: Bibliotheken laden
    echo Vloid Songs laedt die Bibliotheken. Beim ersten Mal dauert das einige Minuten.
    echo.
    "%UV%" sync --frozen --no-dev
    if errorlevel 1 (
        echo.
        echo Das Laden hat nicht geklappt. Bitte ein Bild von diesem Fenster schicken.
        timeout /t 600
        exit /b 1
    )
    rem Eine schon eingerichtete Bewertung (und die KI-Bilder) bekommen Pakete, die seit dem letzten Mal dazugekommen
    rem sind, z. B. requests.
    rem Klappt das nicht, laeuft die App trotzdem; unter Hilfe, Einrichten laesst es sich wiederholen.
    if exist "%~dp0tools\bewertung\venv\Scripts\python.exe" (
        echo.
        set "PATH=%~dp0uv;%PATH%"
        "%UV%" run --no-dev --frozen setup_bewertung.py --ergaenzen
    )
    if exist "%~dp0tools\bilder\venv\Scripts\python.exe" (
        echo.
        set "PATH=%~dp0uv;%PATH%"
        "%UV%" run --no-dev --frozen setup_bilder.py --ergaenzen
    )
    exit /b 0
)
"%UV%" run --no-dev vocaloid_generator\app.py %*
if errorlevel 1 pause
