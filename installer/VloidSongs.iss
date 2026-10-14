; VloidSongs.iss – Setup.exe für Vloid Songs (Inno Setup 6)
;
; Installiert ohne Administratorrechte nach %LOCALAPPDATA%\Programs\Vloid Songs, legt Startmenü- und auf Wunsch
; Desktop-Verknüpfung an und lädt mit dem mitgelieferten uv Python und alle Bibliotheken. Deine Songs und
; Einstellungen liegen in Dokumente\Vloid Songs; Setup, Updates und Deinstallieren fassen sie nicht an.
;
; Bauen (macht .github/workflows/installer.yml):  iscc /DAppVersion=1.0.0 installer\VloidSongs.iss
; Vorher muss uv.exe in installer\uv liegen.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3A1C52-9B7E-4D2A-A8E1-5C0D7B9F4E21}
AppName=Vloid Songs
AppVersion={#AppVersion}
AppVerName=Vloid Songs {#AppVersion}
AppPublisher=StrikerLUL
AppPublisherURL=https://github.com/StrikerLUL/Vloid_songs
DefaultDirName={localappdata}\Programs\Vloid Songs
DefaultGroupName=Vloid Songs
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=VloidSongs-Setup-{#AppVersion}
SetupIconFile=vloid.ico
UninstallDisplayIcon={app}\installer\vloid.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop"; GroupDescription: "Verknüpfungen:"

[Files]
Source: "..\vocaloid_generator\*"; DestDir: "{app}\vocaloid_generator"; Excludes: "__pycache__,*.pyc,tests,output,Songs,Vorlagen,Vorbilder,Motive,Protokolle,Fehlerberichte,Systemcheck,user_settings.json,Einstellungen.json,vorbild_messungen.json,*.wav"; Flags: recursesubdirs ignoreversion
Source: "..\setup_*.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\uv.lock"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\*.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Vloid Songs starten.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "vloid.ico"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "uv\*.exe"; DestDir: "{app}\uv"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Vloid Songs"; Filename: "{app}\Vloid Songs starten.bat"; WorkingDir: "{app}"; IconFilename: "{app}\installer\vloid.ico"; Flags: runminimized
Name: "{autodesktop}\Vloid Songs"; Filename: "{app}\Vloid Songs starten.bat"; WorkingDir: "{app}"; IconFilename: "{app}\installer\vloid.ico"; Flags: runminimized; Tasks: desktopicon

[Run]
; Python und alle Bibliotheken; beim Update nur, was sich geändert hat
Filename: "{app}\uv\uv.exe"; Parameters: "sync --frozen --no-dev --python 3.12"; WorkingDir: "{app}"; StatusMsg: "Lade Python und die Bibliotheken (beim ersten Mal einige Minuten)..."; Flags: runhidden
Filename: "{app}\Vloid Songs starten.bat"; WorkingDir: "{app}"; Description: "Vloid Songs jetzt starten"; Flags: postinstall nowait skipifsilent shellexec runminimized
; Nach einem Update aus der App (still, mit /NEUSTART=1) startet die App von selbst wieder
Filename: "{app}\Vloid Songs starten.bat"; WorkingDir: "{app}"; Flags: nowait shellexec runminimized; Check: RestartWanted

[UninstallDelete]
; Was die App im Programmordner geladen hat; deine Songs in Dokumente\Vloid Songs bleiben
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\vocaloid_generator\__pycache__"
Type: filesandordirs; Name: "{app}\vocaloid_generator\gui\__pycache__"

[Code]
function RestartWanted: Boolean;
begin
  Result := ExpandConstant('{param:NEUSTART|0}') = '1';
end;
