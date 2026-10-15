# config.py – Zentrale Einstellungen für den gesamten Generator
import logging
import os

# ── Sektionen: Länge in Takten und ob gesungen wird ─────────────────────────────
SECTION_CONFIG = {
    "Intro":     {"bars": 8,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 16, "has_vocals": True},
    "PreChorus": {"bars": 8,  "has_vocals": True},
    "Chorus":    {"bars": 16, "has_vocals": True},
    "Bridge":    {"bars": 8,  "has_vocals": True},
    "Drop":      {"bars": 2,  "has_vocals": False},
    "Solo":      {"bars": 8,  "has_vocals": False},   # Instrumental-Solo der Lead-Stimme über den Refrain-Akkorden
    "Outro":     {"bars": 8,  "has_vocals": False},
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
    """Was in datenordner.txt steht: "programmordner", ein Ordner oder "" (Standard)."""
    try:
        with open(DATA_CHOICE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def data_dir() -> str:
    if os.environ.get(DATA_ENV):
        return os.path.abspath(os.environ[DATA_ENV])
    choice = data_choice()
    if choice.lower() == PROGRAM_FOLDER:
        return BASE_DIR
    return os.path.abspath(choice) if choice else default_data_dir()


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
