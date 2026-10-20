# config.py – Zentrale Einstellungen für den gesamten Generator
import logging
import os
import shutil

# ── Sektionen: Länge in Takten und ob gesungen wird ─────────────────────────────
SECTION_CONFIG = {
    "Intro":     {"bars": 8,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 16, "has_vocals": True},
    "PreChorus": {"bars": 8,  "has_vocals": True},
    "Chorus":    {"bars": 16, "has_vocals": True},
    "Bridge":    {"bars": 8,  "has_vocals": True},
    "Rap":       {"bars": 8,  "has_vocals": True},    # gesprochen von der VOICEVOX-Sprechstimme (rap.py)
    "Spoken":    {"bars": 4,  "has_vocals": True},    # „Sprechen“: eine Zeile frei gesprochen (spoken.py, 1.3.0 G7)
    "Drop":      {"bars": 2,  "has_vocals": False},
    "Solo":      {"bars": 8,  "has_vocals": False},   # Instrumental-Solo der Lead-Stimme über den Refrain-Akkorden
    "Outro":     {"bars": 8,  "has_vocals": False},
    "Interlude": {"bars": 4,  "has_vocals": False},   # Zwischenspiel: die Band wie im Intro, mit dem Intro-Riff
}

# ── Dateipfade ────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT       = os.path.dirname(BASE_DIR)
SOUNDFONT_PFAD  = os.path.join(BASE_DIR, "soundfont.sf2")
# Python, das die Setup.exe mitbringt. „Vloid Songs starten.bat“ lässt uv nur dieses nehmen.
BUNDLED_PYTHON  = os.path.join(REPO_ROOT, "python", "python.exe")


def venv_python(version: str = "3.12") -> str:
    """Python für die eigenen Umgebungen der Modelle (tools/…): das mitgebrachte, ohne Setup.exe sucht uv version."""
    return BUNDLED_PYTHON if os.path.isfile(BUNDLED_PYTHON) else version


# ── Modelle von Hugging Face (Bewertung, KI-Begleitung, Klang-Veredler) ───────
# huggingface_hub legt jede Modelldatei sonst als Verknüpfung (Symlink) auf einen Speicher daneben an. Manche Windows-PCs
# folgen solchen Verknüpfungen nicht (wie den Junctions von uv, os error 448): dann scheitert schon das Öffnen von
# config.json mit „[Errno 22] Invalid argument“. Deshalb legt huggingface_hub in den eigenen Umgebungen echte Dateien
# an; neue Fassungen lesen dafür HF_HUB_DISABLE_SYMLINKS, ältere stellen die Worker selbst um.
def hf_environment(home: str) -> dict:
    """Umgebungsvariablen für Modelle in home: echte Dateien statt Verknüpfungen, ohne Warnung deswegen."""
    return {"HF_HOME": home, "HF_HUB_DISABLE_SYMLINKS": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}


def _link_target(path: str) -> str:
    """Wohin eine Verknüpfung am Ende zeigt, ohne ihr zu folgen (das klappt ja gerade nicht)."""
    for _ in range(8):
        if not os.path.islink(path):
            break
        path = os.path.normpath(os.path.join(os.path.dirname(path), os.readlink(path)))
    return path


def hf_without_links(home: str) -> int:
    """
    Ersetzt die Verknüpfungen, die frühere Fassungen in home angelegt haben, durch die Dateien selbst. Verschoben, nicht
    kopiert, damit kein Platz verloren geht und nichts neu geladen werden muss. Gibt zurück, wie viele es waren.
    """
    links = []
    for root, _dirs, names in os.walk(os.path.join(home, "hub")):
        links += [os.path.join(root, name) for name in names if os.path.islink(os.path.join(root, name))]
    files = [p for p in links if f"{os.sep}snapshots{os.sep}" in p]      # die Dateien, die das Modell öffnet
    moved = {}
    for path in files:
        try:
            target = _link_target(path)
            os.remove(path)
            if target in moved:                     # zwei Fassungen teilen sich eine Datei
                shutil.copyfile(moved[target], path)
            elif os.path.isfile(target):
                os.replace(target, path)
                moved[target] = path
        except OSError as e:                        # dann holt huggingface_hub die Datei neu
            logging.getLogger(__name__).warning("Modelldatei %s nicht ersetzt: %s", path, e)
    for path in set(links) - set(files):            # die Verweise im Speicher daneben zeigen jetzt ins Leere
        remove_file(path)
    replaced = sum(os.path.isfile(p) and not os.path.islink(p) for p in files)
    if replaced:
        logging.getLogger(__name__).info("%s: %d Verknüpfungen durch echte Dateien ersetzt", home, replaced)
    return replaced


# ── Deine Daten ───────────────────────────────────────────────────────────────
# Songs, Einstellungen, Vorlagen, Vorbilder, Motive und Protokolle liegen in einem eigenen Ordner, den Updates nie
# anfassen: Standard Dokumente\Vloid Songs. Steht in datenordner.txt (im Programmordner) "programmordner", bleiben sie
# wie früher in vocaloid_generator; ein anderer Ordner dort geht auch. Die Umgebungsvariable VLOID_DATEN geht vor.
DATA_ENV        = "VLOID_DATEN"
DATA_CHOICE     = os.path.join(REPO_ROOT, "datenordner.txt")
PROGRAM_FOLDER  = "programmordner"
DATA_NAME       = "Vloid Songs"


def documents_dir() -> str:
    """Der Ordner Dokumente, auch wenn Windows ihn verschoben hat (z. B. nach OneDrive)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # 5 = Dokumente
                return buf.value
        except Exception:  # noqa: BLE001 – dann der übliche Ort
            pass
    home = os.path.expanduser("~")
    documents = os.path.join(home, "Documents")
    return documents if os.path.isdir(documents) else home


def default_data_dir() -> str:
    return os.path.join(documents_dir(), DATA_NAME)


def data_choice() -> str:
    """Was in datenordner.txt steht: "programmordner", ein Ordner oder "" (Standard). Der Windows-Editor schreibt
    manchmal ein unsichtbares Zeichen (BOM) an den Anfang; das zählt nicht mit."""
    try:
        with open(DATA_CHOICE, encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return ""


def data_dir() -> str:
    if os.environ.get(DATA_ENV):
        return os.path.abspath(os.environ[DATA_ENV])
    choice = data_choice()
    if choice.lower() == PROGRAM_FOLDER:
        return BASE_DIR
    # ein Ordner ohne Laufwerk gilt neben datenordner.txt, nicht dort, wo die App gerade gestartet wurde
    return os.path.abspath(os.path.join(REPO_ROOT, choice)) if choice else default_data_dir()


DATA_DIR        = data_dir()
OUTPUT_ORDNER   = os.path.join(DATA_DIR, "Songs")
LOG_DIR         = os.path.join(DATA_DIR, "Protokolle")

# ── VOCAL ENGINE ───────────────────────────────────────────────────────────────
# Standard: der Ordner, den setup_neutrino.py im Projektordner anlegt
NEUTRINO_PFAD       = os.path.join(REPO_ROOT, "NEUTRINO-windows-v3.1", "NEUTRINO")


def remove_file(path: str) -> None:
    """Die Datei löschen, wenn es sie gibt; ein Fehler steht nur im Protokoll."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        logging.getLogger(__name__).warning("Konnte %s nicht löschen: %s", path, e)
