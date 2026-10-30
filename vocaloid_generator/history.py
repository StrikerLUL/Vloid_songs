# history.py – Verlauf und Bibliothek: jeder fertige Song mit Seed und Einstellungen, zum Wiederhören,
# Wiederherstellen, Benennen, Notieren und Suchen
#
# Pro Song liegen im Ordner <Ausgabe>/verlauf zwei Dateien mit demselben Namen:
#   20261011-143000_J-Pop-Energy_123456.mp3   der fertige Song (ohne ffmpeg die WAV)
#   20261011-143000_J-Pop-Energy_123456.json  alle Einstellungen samt Seed, lesbar mit SongSettings.load;
#                                             unter "verlauf" Datum, Favorit, Name, Notiz, Album und Bewertung
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from settings import SongSettings

log = logging.getLogger(__name__)

FOLDER = "verlauf"
KEEP = 30                      # ältere Songs fallen heraus; Favoriten, benannte und Album-Songs bleiben immer
# Pfade gehören zum Rechner, nicht zum Song: beim Wiederherstellen bleiben die aktuellen
MACHINE_FIELDS = ("neutrino_pfad", "soundfont_pfad", "output_ordner", "vst_path", "reference_folder", "voicevox_url",
                  "cabinet_ir", "motif_folder", "reuse_steps", "log_file", "update_check", "setup_wizard",
                  "history_keep", "album_vary", "keep_projects", "video_background")
SORTS = {"neu": "Neueste zuerst", "bewertung": "Beste Note zuerst", "name": "Nach Name"}
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
    label: str = ""                    # eigener Name
    note: str = ""
    album: str = ""                    # aus „Album über Nacht“ (album.py)
    thumbs: dict = field(default_factory=dict)     # 1.5.0: {Aspekt (geschmack.ASPECTS): +1 oder -1}
    character: dict = field(default_factory=dict)  # 1.5.0: was der Song gewürfelt hat (pipeline.song_character)

    @property
    def title(self) -> str:
        s = self.settings
        rerolled = ", neu: " + ", ".join(sorted(s.variations)) if s.variations else ""
        named = f"„{self.label}“  " if self.label else ""
        return f"{named}{self.created:%d.%m. %H:%M}  {s.style}, {s.bpm} BPM, {s.key} {s.scale}, Seed {s.seed}{rerolled}"

    @property
    def kept(self) -> bool:
        """Favoriten, benannte Songs und Album-Songs fallen nie aus dem Verlauf."""
        return self.favorite or bool(self.label) or bool(self.album)

    @property
    def score(self) -> Optional[float]:
        """Die Note der Bewertung. Gespeichert sind ihre Teile (rating.Rating.to_dict), die Note selbst nicht."""
        if not self.rating:
            return None
        from rating import Rating
        found = Rating.from_dict(self.rating)
        return found.overall if found else self.rating.get("overall")

    def restore(self, current: Optional[SongSettings] = None) -> SongSettings:
        """Die Einstellungen dieses Songs; die Pfade (NEUTRINO, SoundFont, ...) bleiben die von current."""
        if current is None:
            return self.settings
        return self.settings.with_updates(**{f: getattr(current, f) for f in MACHINE_FIELDS})


def folder(output_dir: str) -> str:
    return os.path.join(output_dir, FOLDER)


def record(audio_path: str, settings: SongSettings, output_dir: str, keep: int = KEEP,
           character: Optional[dict] = None) -> Optional[Entry]:
    """Legt den Song im Verlauf ab. settings muss den benutzten Seed enthalten. keep=0 behält alle.
    character: was der Song gewürfelt hat (pipeline.song_character), für die Daumen. Fehler kosten nur den Eintrag."""
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
        meta = {"erstellt": now.isoformat(timespec="seconds"), "favorit": False}
        if character:
            meta["charakter"] = character
        _write(info, settings, meta)
    except OSError as e:
        log.warning("Song konnte nicht im Verlauf gespeichert werden: %s", e)
        return None
    _prune(output_dir, keep)
    log.info("Im Verlauf gespeichert: %s", audio)
    return Entry(name, audio, info, now.replace(microsecond=0), False, settings, character=character or {})


def entries(output_dir: str) -> list:
    """Alle Songs im Verlauf, der neueste zuerst; auch die von vor 1.6.0 aus dem Ausgabeordner in OneDrive, wenn die
    App jetzt außerhalb arbeitet (speicher.earlier)."""
    import speicher
    files = []
    for target in [folder(output_dir)] + [folder(old) for old in speicher.earlier(output_dir)]:
        if os.path.isdir(target):
            files += [os.path.join(target, f) for f in os.listdir(target) if f.endswith(".json")]
    found = []
    for path in sorted(files, key=os.path.basename, reverse=True):
        entry = _read(path)
        if entry:
            found.append(entry)
    return found


def set_favorite(entry: Entry, favorite: bool) -> Entry:
    """Favoriten fallen nie aus dem Verlauf."""
    _update(entry.info, favorit=bool(favorite))
    entry.favorite = bool(favorite)
    return entry


def set_thumb(entry: Entry, aspect: str, vote: int) -> Entry:
    """Daumen hoch (+1), runter (-1) oder keiner (0) für Klang, Melodie, Stimme oder Groove (geschmack.py)."""
    thumbs = {k: v for k, v in (entry.thumbs or {}).items() if k != aspect}
    if vote:
        thumbs[aspect] = 1 if vote > 0 else -1
    _update(entry.info, daumen=thumbs)
    entry.thumbs = thumbs
    return entry


def set_details(entry: Entry, label: Optional[str] = None, note: Optional[str] = None) -> Entry:
    """Name und Notiz eines Songs; ein Song mit Namen fällt nie aus dem Verlauf."""
    changes = {}
    if label is not None:
        changes["name"] = entry.label = label.strip()
    if note is not None:
        changes["notiz"] = entry.note = note.strip()
    _update(entry.info, **changes)
    return entry


def set_rating(audio: str, rating: dict) -> None:
    """Merkt sich die Note der automatischen Bewertung beim Song audio im Verlauf."""
    try:
        _update(_info(audio), bewertung=rating)
    except (OSError, ValueError) as e:
        log.warning("Bewertung nicht im Verlauf gespeichert: %s", e)


def set_album(audio: str, album: str) -> None:
    try:
        _update(_info(audio), album=album)
    except (OSError, ValueError) as e:
        log.warning("Album nicht im Verlauf gespeichert: %s", e)


def find(entries: list, text: str = "", favorites: bool = False, sort: str = "neu") -> list:
    """Suche in Name, Notiz, Album, Stil, Tonart, Tempo, Seed und Datum; jedes Wort muss vorkommen."""
    words = text.lower().split()
    found = [e for e in entries if (e.favorite or not favorites) and all(w in _haystack(e) for w in words)]
    if sort == "bewertung":
        found.sort(key=lambda e: (e.score is None, -(e.score or 0.0)))
    elif sort == "name":
        found.sort(key=lambda e: (not e.label, (e.label or e.settings.style).lower()))
    return found


def _haystack(e: Entry) -> str:
    s = e.settings
    return " ".join([e.label, e.note, e.album, s.style, s.key, s.scale, f"{s.bpm} bpm", f"seed {s.seed}", str(s.seed),
                     f"{e.created:%d.%m.%Y %H:%M}"]).lower()


def _info(audio: str) -> str:
    return os.path.splitext(audio)[0] + ".json"


def _update(info: str, **meta) -> None:
    with open(info, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("verlauf", {}).update(meta)
    with open(info + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(info + ".tmp", info)


def delete(entry: Entry) -> None:
    import project
    for path in (entry.audio, entry.info):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    project.delete(entry.audio)          # der aufgehobene Gesang (Projektordner) gehört dazu


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
    thumbs = meta.get("daumen") if isinstance(meta.get("daumen"), dict) else {}
    character = meta.get("charakter") if isinstance(meta.get("charakter"), dict) else {}
    return Entry(name, audio, info, created, bool(meta.get("favorit")), SongSettings.load(info), rating,
                 str(meta.get("name") or ""), str(meta.get("notiz") or ""), str(meta.get("album") or ""),
                 thumbs, character)


def _prune(output_dir: str, keep: int) -> None:
    if keep <= 0:
        return
    removable = [e for e in entries(output_dir) if not e.kept]
    for entry in removable[keep:]:
        if entry.thumbs:
            import geschmack
            geschmack.archive(output_dir, entry)        # der Geschmack bleibt, auch wenn der Song geht
        delete(entry)


def _free_name(target: str, name: str) -> str:
    candidate, n = name, 2
    while os.path.exists(os.path.join(target, candidate + ".json")):
        candidate, n = f"{name}-{n}", n + 1
    return candidate


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-") or "Song"
