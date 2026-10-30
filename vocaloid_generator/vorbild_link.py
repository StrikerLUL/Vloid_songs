# vorbild_link.py – Ein Video-Link als Vorbild (1.6.0)
#
# Statt einer Datei ein Link (YouTube, Niconico, SoundCloud, Bilibili …): yt-dlp lädt nur den Ton in einen
# temporären Ordner, die App misst Tempo, Tonart und Klang (reference.py) sowie Ablauf und Akkorde (vorbild_ablauf.py),
# danach ist der Ton wieder gelöscht. Es bleiben nur diese Zahlen, in vorbild_links.json im Datenordner. Weil die
# Aufnahme danach fehlt, bestimmt ein Link Tempo, Tonart, Stil, Ablauf und Akkorde, aber nicht das Mastering (dafür
# braucht matchering die Aufnahme selbst: dann die Datei als Vorbild nehmen).
# Nur mit dem Schalter „Video-Links als Vorbild“ (video_links, aus): YouTube erlaubt das Herunterladen in seinen
# Nutzungsbedingungen nur, wo es selbst einen Knopf dafür anbietet. Gedacht ist es für eigene Videos und solche, deren
# Rechteinhaber zustimmt; die App fragt deshalb vor dem ersten Laden.
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable, Optional

import config
import reference
import vorbild_ablauf

log = logging.getLogger(__name__)

FILE = "vorbild_links.json"
LONGEST = 15 * 60               # längere Videos lädt die App nicht (Mixe, Livestreams)
_URL = re.compile(r"^https?://[^\s/]+\.[^\s/]+(/\S*)?$")


@dataclass
class Messung:
    url: str
    title: str
    bpm: int
    key: str
    scale: str
    style: str
    template: Optional[dict] = None             # vorbild_ablauf.Template als dict; None, wenn kein Ablauf erkannt
    date: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def structure(self) -> Optional[vorbild_ablauf.Template]:
        if not self.template:
            return None
        return vorbild_ablauf.Template(**{**self.template,
                                          "parts": [vorbild_ablauf.Part(**p) for p in self.template["parts"]]})

    def describe(self) -> str:
        mode = "Dur" if self.scale == "major" else "Moll"
        found = self.structure()
        parts = " · ".join(f"{p.kind} {p.bars}" for p in found.parts) if found else "Ablauf nicht erkannt"
        return f"{self.bpm} BPM, {self.key} {mode}, klingt nach {self.style}; {parts}"


def valid(url: str) -> bool:
    return bool(_URL.match((url or "").strip()))


def path() -> str:
    return os.path.join(config.DATA_DIR, FILE)


def load() -> list:
    """[Messung], die neueste zuerst."""
    try:
        with open(path(), encoding="utf-8") as f:
            return [Messung(**m) for m in json.load(f).get("links", [])]
    except (OSError, ValueError, TypeError):
        return []


def _save(found: list) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    temp = path() + ".neu"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump({"links": [asdict(m) for m in found]}, f, ensure_ascii=False, indent=1)
    os.replace(temp, path())


def forget(url: str) -> None:
    _save([m for m in load() if m.url != url])


def available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def _download(url: str, folder: str, progress: Optional[Callable[[float, str], None]] = None) -> tuple:
    """(Pfad der Tondatei, Titel): yt-dlp lädt nur den Ton, mit ffmpeg gleich als WAV."""
    import yt_dlp
    from yt_dlp.utils import match_filter_func

    from karaoke import find_ffmpeg

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading" and d.get("total_bytes"):
            progress(0.6 * d.get("downloaded_bytes", 0) / d["total_bytes"], "Lade den Ton des Videos...")

    options = {"format": "bestaudio/best", "outtmpl": os.path.join(folder, "ton.%(ext)s"), "noplaylist": True,
               "quiet": True, "no_warnings": True, "noprogress": True, "progress_hooks": [hook],
               "match_filter": match_filter_func(f"duration <=? {LONGEST}")}
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        options.update(ffmpeg_location=ffmpeg, postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}])
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True) or {}
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("ton."))
    if not files:
        raise ValueError("Das Video gab keinen Ton her (zu lang, privat oder nur für Mitglieder?)")
    return files[-1], info.get("title") or url


def measure(url: str, progress: Optional[Callable[[float, str], None]] = None, again: bool = False) -> Messung:
    """Misst das Vorbild hinter dem Link; schon gemessene Links kommen aus vorbild_links.json (again: neu messen).
    Der Ton liegt nur während der Messung in einem temporären Ordner."""
    url = url.strip()
    if not valid(url):
        raise ValueError("Das ist kein Link (er beginnt mit https://)")
    known = load()
    if not again:
        found = next((m for m in known if m.url == url), None)
        if found:
            return found
    folder = tempfile.mkdtemp(prefix="vloid-vorbild-")
    try:
        audio, title = _download(url, folder, progress)
        if progress:
            progress(0.7, "Messe Tempo, Tonart, Ablauf und Akkorde...")
        sound = reference.analyse(audio, use_cache=False)
        try:
            template = asdict(vorbild_ablauf.measure(audio, use_cache=False))
            template["path"] = url
        except Exception as e:              # zu kurz oder keine Schläge: Tempo und Tonart gibt es trotzdem
            log.warning("Ablauf von %s nicht messbar: %s", url, e)
            template = None
    finally:
        shutil.rmtree(folder, ignore_errors=True)        # der Ton bleibt nicht liegen
    # Tempo und Tonart aus der Messung des ganzen Songs, wenn es sie gibt (genauer als die ersten Minuten)
    bpm, key, scale = (template["bpm"], template["key"], template["scale"]) if template else \
        (int(round(sound.bpm)), sound.key, sound.scale)
    style = reference.suggest_style(bpm, scale, sound.brightness, sound.drums)
    found = Messung(url, title, bpm, key, scale, style, template)
    _save([found] + [m for m in known if m.url != url])
    log.info("Vorbild aus dem Link %s gemessen (der Ton ist wieder gelöscht): %s", url, found.describe())
    return found
