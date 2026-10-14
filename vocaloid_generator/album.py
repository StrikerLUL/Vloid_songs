# album.py – Album über Nacht: viele Songs am Stück, morgens nach Note sortiert in einem eigenen Ordner
#
# Abends „10 Songs, Stile Rock und Ballade“ starten. Jeder Song bekommt einen neuen Seed, die typischen Werte
# seines Stils und (Schalter album_vary) eine eigene Tonart und ein leicht anderes Tempo. Liegt ein Ordner mit
# Liedtexten bereit (eine .txt pro Song), singt jeder Song seinen eigenen Text. Alle Songs landen im Verlauf (dort
# bleiben sie, auch wenn er voll ist) und als nummerierte MP3s mit Wiedergabeliste und Titelliste unter
# <Ausgabe>/Alben/<Datum> <Name>. Ist die Bewertung eingerichtet, steht der beste Song vorn.
# Ein Fehler in einem Song kostet nur diesen Song; Abbrechen behält die fertigen.
import logging
import os
import random
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import cancel
import history
from settings import KEYS, SongSettings

log = logging.getLogger(__name__)

FOLDER = "Alben"
MAX_SONGS = 30
TEMPO_SPREAD = 0.05                 # mit album_vary: Tempo bis zu so viel schneller oder langsamer
PLAYLIST = "Album.m3u8"
TRACKLIST = "Titelliste.txt"

ProgressFn = Callable[[float, str], None]


@dataclass
class Album:
    name: str
    folder: str
    results: list = field(default_factory=list)      # pipeline.SongResult, in der Reihenfolge des Albums
    files: list = field(default_factory=list)        # die MP3s im Album-Ordner, gleiche Reihenfolge
    failed: int = 0
    cancelled: bool = False

    def describe(self) -> str:
        text = f"{len(self.files)} Songs in {self.folder}"
        if self.failed:
            text += f", {self.failed} fehlgeschlagen (Details im Protokoll)"
        if self.cancelled:
            text += ", abgebrochen"
        return text


def lyric_files(folder: str) -> list:
    """Die Liedtexte im Ordner: jede .txt ist ein Song, nach Dateiname sortiert."""
    if not folder or not os.path.isdir(folder):
        return []
    texts = []
    for name in sorted(os.listdir(folder), key=str.lower):
        if name.lower().endswith(".txt"):
            with open(os.path.join(folder, name), encoding="utf-8-sig", errors="replace") as f:
                text = f.read().strip()
            if text:
                texts.append(text)
    return texts


def plan(settings: SongSettings, count: int, styles: list, lyrics: list = (), seed: Optional[int] = None) -> list:
    """Die Einstellungen für jeden Song des Albums: Stile reihum, je ein neuer Seed beim Erzeugen."""
    from preset_manager import preset_settings
    if not 1 <= count <= MAX_SONGS:
        raise ValueError(f"Ein Album hat 1 bis {MAX_SONGS} Songs.")
    styles = list(styles) or [settings.style]
    rng = random.Random(seed)
    songs = []
    for i in range(count):
        style = styles[i % len(styles)]
        s = preset_settings(style, settings) or settings.with_updates(style=style)
        changes = {"seed": None, "variations": {}, "melody_edits": {}, "melody_lengths": {}, "draft": False}
        if settings.album_vary:
            changes["key"] = rng.choice(KEYS)
            changes["bpm"] = max(40, min(260, round(s.bpm * rng.uniform(1 - TEMPO_SPREAD, 1 + TEMPO_SPREAD))))
        if lyrics:
            changes["lyrics"] = lyrics[i % len(lyrics)]
        songs.append(s.with_updates(**changes))
    return songs


def make(settings: SongSettings, count: int, styles: list, lyrics_folder: str = "",
         progress: Optional[ProgressFn] = None, name: str = "") -> Album:
    """Erzeugt das Album. Wirft ValueError bei unmöglichen Wünschen, sonst nie: fehlgeschlagene Songs zählen mit."""
    import pipeline
    import rating
    report = progress or (lambda fraction, message: None)
    songs = plan(settings, count, styles, lyric_files(lyrics_folder))
    now = datetime.now()
    name = name.strip() or f"Nacht {now:%d.%m.%Y}"
    folder = free_folder(os.path.join(settings.output_dir(), FOLDER), f"{now:%Y-%m-%d %H-%M} {safe_name(name)}")
    os.makedirs(folder, exist_ok=True)
    album = Album(name, folder)
    judge = settings.auto_rating and count > 1 and rating.available()
    share = 0.95 if judge else 1.0
    clips, finished = [], []
    with tempfile.TemporaryDirectory() as clip_folder:
        for i, song in enumerate(songs):
            def step(fraction, message, i=i, song=song):
                report((i + fraction) / count * share, f"Album {i + 1}/{count} ({song.style}): {message}")
            try:
                cancel.check()
                result = pipeline.generate_song(song, progress=step)
            except cancel.Cancelled:
                album.cancelled = True
                break
            except Exception as e:  # noqa: BLE001 – über Nacht zählt der nächste Song, der Fehler kommt ins Protokoll
                log.exception("Album-Song %d (%s) fehlgeschlagen: %s", i + 1, song.style, e)
                album.failed += 1
                continue
            if result.history:
                history.set_album(result.history, name)
            # jetzt kopieren: der nächste Song überschreibt die Dateien im Ausgabeordner
            source = result.history or result.audio
            staged = os.path.join(folder, f".{i + 1}{os.path.splitext(source)[1].lower()}")
            shutil.copyfile(source, staged)
            finished.append((result, staged))
            if judge and result.mix_wav:
                clips.append((result, rating.excerpt(result.mix_wav, os.path.join(clip_folder, f"{i + 1}.wav"))))
        if clips and not album.cancelled:
            report(0.96, "Album: bewerte die Songs...")
            pipeline._rate(clips)
    ranked = sorted(finished, key=lambda f: -f[0].rating.overall) if all(r.rating for r, _ in finished) else finished
    for nr, (result, staged) in enumerate(ranked, 1):
        target = os.path.join(folder, f"{nr:02d} {safe_name(_title(result))}{os.path.splitext(staged)[1]}")
        os.replace(staged, target)
        album.results.append(result)
        album.files.append(target)
    _write_lists(album)
    report(1.0, f"Album fertig: {album.describe()}")
    log.info("Album „%s“: %s", name, album.describe())
    return album


def _title(result) -> str:
    s = result.settings
    return f"{s.style} {s.key} {s.scale} {s.bpm} BPM (Seed {result.seed})" if s else f"Seed {result.seed}"


def _write_lists(album: Album) -> None:
    with open(os.path.join(album.folder, PLAYLIST), "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for path in album.files:
            f.write(f"#EXTINF:-1,{os.path.splitext(os.path.basename(path))[0][3:]}\n{os.path.basename(path)}\n")
    with open(os.path.join(album.folder, TRACKLIST), "w", encoding="utf-8") as f:
        f.write(f"{album.name}\n\n")
        for nr, result in enumerate(album.results, 1):
            note = f"  Note {result.rating.overall:.1f}" if result.rating else ""
            f.write(f"{nr:2d}. {_title(result)}{note}\n")
        if album.failed:
            f.write(f"\n{album.failed} Songs sind fehlgeschlagen (Details im Protokoll).\n")
        f.write("\nJeder Song liegt auch im Verlauf; ↺ dort holt seine Einstellungen samt Seed zurück.\n")


def safe_name(text: str, fallback: str = "Album") -> str:
    """Ein Datei- oder Ordnername, den Windows annimmt."""
    cleaned = "".join("-" if c in '<>:"/\\|?*' else c for c in text).strip(" .")
    return cleaned[:80] or fallback


def free_folder(parent: str, name: str) -> str:
    candidate, n = os.path.join(parent, name), 2
    while os.path.exists(candidate):
        candidate, n = os.path.join(parent, f"{name} ({n})"), n + 1
    return candidate
