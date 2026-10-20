# speicher.py – Platz auf der Festplatte (v6 Nr. 18)
#
# Wie viel jeder eingerichtete Baustein belegt (Einrichten › Entfernen gibt den Platz frei; neu einrichten geht
# jederzeit), wie groß Songs und aufgehobene Projekte sind, und Zwischenspeicher, die sich gefahrlos löschen lassen
# (sie entstehen beim nächsten Mal neu). NEUTRINO und eigene Dateien (Vorbilder, Motive, Vorlagen) löscht die App
# nie: die hat der Nutzer selbst hingelegt.
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Optional

import config

log = logging.getLogger(__name__)


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
    import drum_kit
    import grooves
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
            "begleitung": accompaniment.FOLDER, "ace_step": polish.FOLDER}


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
    found = [reference.CACHE, separation.CACHE, updates._cache_path(),
             os.path.join(config.DATA_DIR, fehlerbericht.FOLDER)]
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
