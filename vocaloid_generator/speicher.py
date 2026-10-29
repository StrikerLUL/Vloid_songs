# speicher.py – Platz auf der Festplatte (v6 Nr. 18)
#
# Wie viel jeder eingerichtete Baustein belegt (Einrichten › Entfernen gibt den Platz frei; neu einrichten geht
# jederzeit), wie groß Songs und aufgehobene Projekte sind, und Zwischenspeicher, die sich gefahrlos löschen lassen
# (sie entstehen beim nächsten Mal neu). NEUTRINO und eigene Dateien (Vorbilder, Motive, Vorlagen) löscht die App
# nie: die hat der Nutzer selbst hingelegt.
#
# 1.6.0: Liegt der Ausgabeordner in OneDrive (Windows schiebt Dokumente gern dorthin) oder einem anderen Sync-Ordner,
# arbeitet die App in einem Ordner auf diesem Rechner (outside_cloud): Spuren, Zwischenspeicher, der Gesang zum
# Wiederverwenden, der Verlauf und die Projekte. Sie werden bei jedem Lauf neu geschrieben, sind schnell ein paar GB
# groß und OneDrive lädt sie sonst ständig hoch (oder lagert sie in die Cloud aus, dann fehlen sie beim Lesen). Der
# alte Verlauf bleibt, wo er ist, und erscheint weiter (earlier); jede fertige MP3 kommt zusätzlich in den Sync-Ordner
# (cloud_copy, Unterordner MP3), damit sie wie bisher aufs Handy kommt. low_space warnt unter 5 GB freiem Platz.
import logging
import os
import re
import shutil
from dataclasses import dataclass
from typing import Optional

import config

log = logging.getLogger(__name__)

LOW_GB = 5.0                # weniger frei: Warnung vor dem Erzeugen und im Systemcheck
LOCAL_ENV = "VLOID_ARBEIT"  # ein anderer Ort für die Arbeitsdateien als %LOCALAPPDATA%\Vloid Songs
CLOUD_ENV = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")     # setzt Windows, wenn OneDrive eingerichtet ist
_CLOUD = re.compile(r"^(OneDrive( - .+)?|Dropbox|iCloudDrive|iCloud Drive|Google Drive|GoogleDrive)$", re.IGNORECASE)
SHARED = "MP3"              # Unterordner im Sync-Ordner für die fertigen MP3s
_earlier: dict = {}         # Arbeitsordner → Ausgabeordner im Sync-Ordner, aus dem er übernommen hat


@dataclass
class Usage:
    key: str
    name: str
    path: str
    bytes: int


def _folders() -> dict:
    """Baustein (einrichten.COMPONENTS) → sein Ordner unter tools."""
    import accompaniment
    import airwindows
    import amp_models
    import band_library
    import bilder
    import drum_kit
    import grooves
    import hoercheck
    import polish
    import rating
    import renderer
    import sample_library
    import separation
    import sound_library
    import surge_sounds
    return {"fluidsynth": os.path.dirname(renderer.FLUIDSYNTH_DIR), "soundfonts": sound_library.FOLDER,
            "samples": sample_library.FOLDER, "band": band_library.FOLDER, "drums": drum_kit.FOLDER,
            "grooves": grooves.FOLDER, "airwindows": airwindows.FOLDER, "surge": surge_sounds.FOLDER,
            "nam": amp_models.FOLDER, "rating": rating.FOLDER, "demucs": separation.FOLDER,
            "begleitung": accompaniment.FOLDER, "ace_step": polish.FOLDER, "bilder": bilder.FOLDER,
            "hoercheck": hoercheck.FOLDER}


def size(path: str) -> int:
    """Bytes in einer Datei oder einem Ordner; Verknüpfungen (Junctions von uv) zählen nicht doppelt."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in files:
            full = os.path.join(root, name)
            try:
                if not os.path.islink(full):
                    total += os.path.getsize(full)
            except OSError:
                pass
    return total


def components() -> list:
    """[Usage] der eingerichteten Bausteine, deren Ordner da ist."""
    import einrichten
    folders = _folders()
    return [Usage(c.key, c.name, folders[c.key], size(folders[c.key])) for c in einrichten.components()
            if c.key in folders and os.path.isdir(folders[c.key])]


def remove(key: str) -> int:
    """Den Ordner eines Bausteins löschen; Rückgabe: freigegebene Bytes. Nur Ordner unter tools."""
    import einrichten
    path = _folders().get(key)
    tools = os.path.join(config.REPO_ROOT, "tools")
    if not path or not os.path.isdir(path):
        return 0
    if os.path.commonpath([os.path.abspath(path), os.path.abspath(tools)]) != os.path.abspath(tools):
        raise ValueError(f"{path} liegt nicht im Ordner tools, die App löscht ihn nicht")
    freed = size(path)
    shutil.rmtree(path, ignore_errors=True)
    einrichten._refresh_caches()
    log.info("Entfernt: %s (%s)", key, describe(freed))
    return freed


def caches() -> list:
    """[Pfad] der Zwischenspeicher: Messungen der Vorbilder, Update-Abfrage, alte Protokolle und Fehlerberichte."""
    import fehlerbericht
    import reference
    import separation
    import updates
    import vorbild_ablauf
    from singing import TAKE_CACHE
    found = [reference.CACHE, vorbild_ablauf.CACHE, separation.CACHE, updates._cache_path(),
             os.path.join(config.DATA_DIR, fehlerbericht.FOLDER)]
    found += [os.path.join(old, TAKE_CACHE) for old in _earlier.values()]   # alter Gesang in OneDrive (1.6.0)
    if os.path.isdir(config.LOG_DIR):
        current = {"vloid_songs.log", "einrichten.log"}
        found += [os.path.join(config.LOG_DIR, n) for n in os.listdir(config.LOG_DIR) if n not in current]
    return [p for p in found if os.path.exists(p)]


def clear_caches() -> int:
    """Zwischenspeicher löschen; Rückgabe: freigegebene Bytes."""
    freed = 0
    for path in caches():
        freed += size(path)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    return freed


def songs(output_dir: str) -> tuple:
    """(Bytes aller Songs im Ausgabeordner, Bytes der aufgehobenen Projekte im Verlauf, Zahl der Projekte)."""
    import history
    import project
    total = size(output_dir) if os.path.isdir(output_dir) else 0
    kept = [e for e in history.entries(output_dir) if project.available(e.audio)]
    return total, sum(project.size(e.audio) for e in kept), len(kept)


def drop_projects(output_dir: str, keep_favorites: bool = True) -> int:
    """Die aufgehobenen Projekte (Gesang zum Wieder-Öffnen) löschen; die Songs bleiben im Verlauf. Favoriten,
    benannte und Album-Songs behalten ihr Projekt (keep_favorites). Rückgabe: Bytes."""
    import history
    import project
    freed = 0
    for entry in history.entries(output_dir):
        if keep_favorites and entry.kept:
            continue
        if project.available(entry.audio):
            freed += project.size(entry.audio)
            project.delete(entry.audio)
    return freed


def describe(n: Optional[int]) -> str:
    """„1,2 GB“, „350 MB“, „12 KB“."""
    if n is None:
        return "…"
    for unit, factor in (("GB", 1e9), ("MB", 1e6)):
        if n >= factor:
            text = f"{n / factor:.1f}" if n < 10 * factor else f"{n / factor:.0f}"
            return text.replace(".", ",") + " " + unit
    return f"{max(1, round(n / 1e3))} KB" if n else "0 KB"


# ── 1.6.0: außerhalb von OneDrive arbeiten, Platz-Warnung ──────────────────────────────────────────────────────────
def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([_key(path), _key(root)]) == _key(root)
    except ValueError:                  # andere Laufwerke
        return False


def cloud(path: str) -> str:
    """Der Sync-Dienst, in dessen Ordner path liegt („OneDrive“, „Dropbox“, …); „“, wenn keiner."""
    if not path:
        return ""
    for var in CLOUD_ENV:
        root = os.environ.get(var)
        if root and _inside(path, root):
            return "OneDrive"
    for part in re.split(r"[\\/]", os.path.abspath(path)):
        if _CLOUD.match(part):
            return part.split(" - ")[0]
    return ""


def local_root() -> str:
    """Wo die Arbeitsdateien auf diesem Rechner liegen: %LOCALAPPDATA%\\Vloid Songs (Linux: ~/.local/share)."""
    if os.environ.get(LOCAL_ENV):
        return os.path.abspath(os.environ[LOCAL_ENV])
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME")
    return os.path.join(base or os.path.join(os.path.expanduser("~"), ".local", "share"), config.DATA_NAME)


def outside_cloud(target: str) -> str:
    """Der Ordner, in dem die App für den Ausgabeordner target arbeitet: target selbst, oder liegt er in einem
    Sync-Ordner, <local_root>/<Name von target>. Geht der nicht anzulegen, bleibt es bei target."""
    if not cloud(target):
        return target
    local = os.path.join(local_root(), os.path.basename(os.path.normpath(target)) or "Songs")
    if cloud(local) or _key(local) == _key(target):
        return target
    if _key(local) not in _earlier:
        try:
            os.makedirs(local, exist_ok=True)
        except OSError as e:
            log.warning("Arbeitsordner %s geht nicht anzulegen (%s), die App arbeitet in %s", local, e, target)
            return target
        log.info("%s liegt in %s: Spuren, Zwischenspeicher, Verlauf und Projekte kommen nach %s", target,
                 cloud(target), local)
    _earlier[_key(local)] = target
    return local


def work_dir(settings, target: str) -> str:
    """settings.output_dir: mit „Arbeitsdateien außerhalb von OneDrive“ (local_cache) outside_cloud, sonst target."""
    return outside_cloud(target) if settings.local_cache else target


def earlier(output_dir: str) -> list:
    """[Ausgabeordner im Sync-Ordner], deren Verlauf zu diesem Arbeitsordner gehört (Songs von vor 1.6.0)."""
    found = _earlier.get(_key(output_dir))
    return [found] if found and os.path.isdir(found) else []


def cloud_copy(output_dir: str, audio: str) -> Optional[str]:
    """Die fertige MP3 auch in den Sync-Ordner (<Ausgabeordner>/MP3); Rückgabe: ihr Pfad, None ohne Sync-Ordner."""
    target = _earlier.get(_key(output_dir))
    if not target or not audio or not os.path.isfile(audio):
        return None
    dest = os.path.join(target, SHARED, os.path.basename(audio))
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(audio, dest)
    except OSError as e:
        log.warning("MP3 nicht in %s kopiert: %s", target, e)
        return None
    return dest


def free(path: str) -> Optional[int]:
    """Freie Bytes auf dem Laufwerk von path (auch wenn path noch nicht da ist); None, wenn unbekannt."""
    probe = os.path.abspath(path)
    while probe and not os.path.exists(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def low_space(path: str) -> str:
    """Eine Warnung, wenn auf dem Laufwerk von path weniger als LOW_GB frei sind; sonst „“."""
    left = free(path)
    if left is None or left >= LOW_GB * 1e9:
        return ""
    return (f"Nur noch {describe(left)} frei: ein Song mit allen Spuren braucht bis zu 1 GB, NEUTRINO und die "
            "Modelle mehr. Unter Hilfe › Einrichten (Speicherplatz) lässt sich Platz freigeben.")


def where(settings) -> str:
    """Wo die Arbeit liegt, wenn der Ausgabeordner in einem Sync-Ordner ist; sonst „“."""
    target = settings.output_dir()
    found = earlier(target) or ([_earlier[_key(target)]] if _key(target) in _earlier else [])
    if found:
        return (f"Der Ausgabeordner {found[0]} liegt in {cloud(found[0])}: Spuren, Zwischenspeicher, Verlauf und "
                f"Projekte liegen deshalb in {target}, die fertigen MP3s zusätzlich in "
                f"{os.path.join(found[0], SHARED)}.")
    if cloud(target):
        return (f"Der Ausgabeordner liegt in {cloud(target)}, der jede Spur hochlädt. „Arbeitsdateien außerhalb von "
                "OneDrive“ (Pfade › App) legt sie auf diesen Rechner.")
    return ""
