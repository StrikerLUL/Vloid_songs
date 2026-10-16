# tags.py – ID3-Tags für die MP3s eines Songs (v6 Nr. 6): Titel, Stimme, Stil, Tempo, Tonart, Liedtext, Titelbild
#
# Damit zeigen Handy, Auto und Musik-Apps den Song mit Namen und Cover statt als „final_song.mp3“. Das Cover malt
# youtube.title_image (quadratisch), der Liedtext steht ohne Überschriften und Lesungen von Hand im Tag (USLT).
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)

COVER_SIZE = (800, 800)
APP = "Vloid Songs"
# Überschriften wie [Verse 2] und Lesungen von Hand wie 君[きみ]
_HEADER = re.compile(r"^\s*\[[^\]]*\]\s*$")
_READING = re.compile(r"[\[［][^\]］]*[\]］]")


def lyric_text(lyrics: str) -> str:
    """Der Liedtext zum Mitlesen: ohne Überschriften, ohne Lesungen von Hand, ohne Leerzeilen am Rand."""
    lines = [_READING.sub("", line).rstrip() for line in (lyrics or "").splitlines() if not _HEADER.match(line)]
    return "\n".join(lines).strip()


def key_name(key: str, scale: str) -> str:
    """Die Tonart, wie ID3 sie schreibt (TKEY): 'C', 'F#m'."""
    return key + ("m" if scale == "minor" else "")


def artist(settings) -> str:
    """Wer singt: die NEUTRINO-Stimme (mit Duett beide), sonst die App."""
    if settings is None or not settings.channels["vocals"].enabled or settings.vocal_engine != "NEUTRINO":
        return APP
    return f"{APP} feat. " + " & ".join(x for x in (settings.singer, settings.duet_singer) if x)


def write(mp3: str, result, title: str = "", version: str = "", cover: Optional[str] = None) -> Optional[str]:
    """Schreibt die Tags in mp3. result: pipeline.SongResult; version: Zusatz zum Titel ('Off Vocal'); cover: ein
    fertiges Titelbild (PNG), sonst wird eins gemalt. Rückgabe: das Titelbild (für die nächste MP3 desselben Songs);
    None, wenn es nicht ging (der Song bleibt, wie er ist)."""
    if not mp3 or not mp3.lower().endswith(".mp3") or not os.path.exists(mp3):
        return None
    try:
        from mutagen.id3 import APIC, COMM, ID3, TBPM, TCON, TIT2, TKEY, TPE1, TSSE, USLT, ID3NoHeaderError
    except ImportError:
        log.warning("mutagen fehlt, die MP3 bekommt keine Tags")
        return None
    import youtube
    from version import VERSION
    s = result.settings
    name = youtube.title_for(result, title)
    try:
        try:
            tags = ID3(mp3)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("APIC")
        tags.add(TIT2(encoding=3, text=f"{name} ({version})" if version else name))
        tags.add(TPE1(encoding=3, text=artist(s) if version != "Off Vocal" else APP))
        tags.add(TSSE(encoding=3, text=f"{APP} {VERSION}"))
        tags.add(COMM(encoding=3, lang="deu", desc="", text=f"Seed {result.seed}, komponiert mit {APP}"))
        if s is not None:
            tags.add(TCON(encoding=3, text=s.style))
            tags.add(TBPM(encoding=3, text=str(round(s.bpm))))
            tags.add(TKEY(encoding=3, text=key_name(s.key, s.scale)))
            text = lyric_text(s.lyrics) if s.channels["vocals"].enabled and version != "Off Vocal" else ""
            if text:
                from lyrics import _JAPANESE
                tags.add(USLT(encoding=3, lang="jpn" if _JAPANESE.search(text) else "eng", desc="", text=text))
        image = _cover(result, name, cover)
        if image:
            with open(image, "rb") as f:
                tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=f.read()))
        tags.save(mp3, v2_version=3)       # ID3v2.3: das lesen auch Windows und ältere Autoradios
    except Exception as e:  # noqa: BLE001 – ohne Tags ist der Song trotzdem fertig
        log.warning("Tags für %s nicht geschrieben: %s", os.path.basename(mp3), e)
        return None
    return image or ""


def _cover(result, title: str, cover: Optional[str]) -> Optional[str]:
    """Das Titelbild als PNG im Ausgabeordner (cover.png); write gibt es an die weiteren MP3s des Songs weiter."""
    if cover and os.path.exists(cover):
        return cover
    import youtube
    path = os.path.join(result.output_dir, "cover.png")
    s = result.settings
    try:
        youtube.title_image(path, title, " · ".join(youtube.details(result)), s.style if s else "", result.mix_wav,
                            size=COVER_SIZE)
    except Exception as e:  # noqa: BLE001
        log.warning("Kein Titelbild für die MP3: %s", e)
        return None
    return path
