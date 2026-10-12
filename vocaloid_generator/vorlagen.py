# vorlagen.py – Eigene Vorlagen: Lieblings-Einstellungen unter einem Namen speichern und wieder laden
#
# Eine Vorlage hält den Klang eines Songs (Stil, Tempo, Tonart, Ablauf, Band, Gesang, Mix, Vorbild-Song),
# aber keinen Liedtext, keinen Seed und keine Pfade dieses Rechners.
import json
import logging
import os
import re

import config
from settings import SongSettings

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.BASE_DIR, "vorlagen")
NOT_IN_TEMPLATE = ("seed", "variations", "lyrics", "neutrino_pfad", "soundfont_pfad", "output_ordner", "vst_path",
                   "cabinet_ir", "melody_midi", "melody_midi_section")


def names(folder: str = None) -> list:
    folder = folder or FOLDER
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith(".json"))


def save(name: str, settings: SongSettings, folder: str = None) -> str:
    folder = folder or FOLDER
    clean = _clean(name)
    if not clean:
        raise ValueError("Die Vorlage braucht einen Namen.")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, clean + ".json")
    data = settings.model_dump(exclude=set(NOT_IN_TEMPLATE))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Vorlage gespeichert: %s", path)
    return clean


def apply(name: str, settings: SongSettings, folder: str = None) -> SongSettings:
    """Die Einstellungen mit den Werten der Vorlage; Text, Seed und Pfade bleiben."""
    path = os.path.join(folder or FOLDER, _clean(name) + ".json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    template = {k: v for k, v in data.items() if k in SongSettings.model_fields and k not in NOT_IN_TEMPLATE}
    merged = SongSettings.load(path).model_dump(include=set(template))
    return settings.with_updates(**merged)


def delete(name: str, folder: str = None) -> None:
    try:
        os.remove(os.path.join(folder or FOLDER, _clean(name) + ".json"))
    except FileNotFoundError:
        pass


def _clean(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (name or "")).strip().strip(".")
