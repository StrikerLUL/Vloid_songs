# history.py – Verlauf: jeder fertige Song mit Seed und Einstellungen, zum Wiederhören und Wiederherstellen
#
# Pro Song liegen im Ordner <Ausgabe>/verlauf zwei Dateien mit demselben Namen:
#   20261011-143000_J-Pop-Energy_123456.mp3   der fertige Song (ohne ffmpeg die WAV)
#   20261011-143000_J-Pop-Energy_123456.json  alle Einstellungen samt Seed, lesbar mit SongSettings.load
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from settings import SongSettings

log = logging.getLogger(__name__)

FOLDER = "verlauf"
KEEP = 30                      # ältere Songs fallen heraus, Favoriten bleiben immer
# Pfade gehören zum Rechner, nicht zum Song: beim Wiederherstellen bleiben die aktuellen
MACHINE_FIELDS = ("neutrino_pfad", "soundfont_pfad", "output_ordner", "vst_path", "reference_folder", "voicevox_url",
                  "cabinet_ir", "motif_folder")
_STAMP = "%Y%m%d-%H%M%S"


@dataclass
class Entry:
    name: str
    audio: str
    info: str
    created: datetime
    favorite: bool
    settings: SongSettings
    rating: Optional[dict] = None      # Note der automatischen Bewertung (rating.Rating.to_dict)

    @property
    def title(self) -> str:
        s = self.settings
        rerolled = ", neu: " + ", ".join(sorted(s.variations)) if s.variations else ""
        return f"{self.created:%d.%m. %H:%M}  {s.style}, {s.bpm} BPM, {s.key} {s.scale}, Seed {s.seed}{rerolled}"

    def restore(self, current: Optional[SongSettings] = None) -> SongSettings:
        """Die Einstellungen dieses Songs; die Pfade (NEUTRINO, SoundFont, ...) bleiben die von current."""
        if current is None:
            return self.settings
        return self.settings.with_updates(**{f: getattr(current, f) for f in MACHINE_FIELDS})


def folder(output_dir: str) -> str:
    return os.path.join(output_dir, FOLDER)


def record(audio_path: str, settings: SongSettings, output_dir: str, keep: int = KEEP) -> Optional[Entry]:
    """Legt den Song im Verlauf ab. settings muss den benutzten Seed enthalten. Fehler kosten nur den Eintrag."""
    if not audio_path or not os.path.exists(audio_path):
        return None
    target = folder(output_dir)
    try:
        os.makedirs(target, exist_ok=True)
        now = datetime.now()
        name = _free_name(target, f"{now.strftime(_STAMP)}_{_slug(settings.style)}_{settings.seed}")
        audio = os.path.join(target, name + os.path.splitext(audio_path)[1].lower())
        shutil.copyfile(audio_path, audio)
        info = os.path.join(target, name + ".json")
        _write(info, settings, {"erstellt": now.isoformat(timespec="seconds"), "favorit": False})
    except OSError as e:
        log.warning("Song konnte nicht im Verlauf gespeichert werden: %s", e)
        return None
    _prune(output_dir, keep)
    log.info("Im Verlauf gespeichert: %s", audio)
    return Entry(name, audio, info, now.replace(microsecond=0), False, settings)


def entries(output_dir: str) -> list:
    """Alle Songs im Verlauf, der neueste zuerst."""
    target = folder(output_dir)
    if not os.path.isdir(target):
        return []
    found = []
    for file in sorted(os.listdir(target), reverse=True):
        if not file.endswith(".json"):
            continue
        entry = _read(os.path.join(target, file))
        if entry:
            found.append(entry)
    return found


def set_favorite(entry: Entry, favorite: bool) -> Entry:
    """Favoriten fallen nie aus dem Verlauf."""
    with open(entry.info, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("verlauf", {})["favorit"] = bool(favorite)
    with open(entry.info, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    entry.favorite = bool(favorite)
    return entry


def set_rating(audio: str, rating: dict) -> None:
    """Merkt sich die Note der automatischen Bewertung beim Song audio im Verlauf."""
    info = os.path.splitext(audio)[0] + ".json"
    try:
        with open(info, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("verlauf", {})["bewertung"] = rating
        with open(info, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except (OSError, ValueError) as e:
        log.warning("Bewertung nicht im Verlauf gespeichert: %s", e)


def delete(entry: Entry) -> None:
    for path in (entry.audio, entry.info):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _write(path: str, settings: SongSettings, meta: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**settings.model_dump(), "verlauf": meta}, f, indent=2, ensure_ascii=False)


def _read(info: str) -> Optional[Entry]:
    name = os.path.splitext(os.path.basename(info))[0]
    audio = next((os.path.join(os.path.dirname(info), name + ext) for ext in (".mp3", ".wav")
                  if os.path.exists(os.path.join(os.path.dirname(info), name + ext))), None)
    if audio is None:
        return None
    try:
        with open(info, "r", encoding="utf-8") as f:
            meta = json.load(f).get("verlauf", {})
        created = datetime.fromisoformat(meta["erstellt"]) if "erstellt" in meta else \
            datetime.strptime(name.split("_")[0], _STAMP)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        log.warning("Verlaufseintrag %s nicht lesbar: %s", info, e)
        return None
    rating = meta.get("bewertung") if isinstance(meta.get("bewertung"), dict) else None
    return Entry(name, audio, info, created, bool(meta.get("favorit")), SongSettings.load(info), rating)


def _prune(output_dir: str, keep: int) -> None:
    removable = [e for e in entries(output_dir) if not e.favorite]
    for entry in removable[keep:]:
        delete(entry)


def _free_name(target: str, name: str) -> str:
    candidate, n = name, 2
    while os.path.exists(os.path.join(target, candidate + ".json")):
        candidate, n = f"{name}-{n}", n + 1
    return candidate


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-") or "Song"
