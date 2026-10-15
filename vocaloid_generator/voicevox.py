# voicevox.py – Singen mit VOICEVOX (kostenlos, https://voicevox.hiroshiba.jp, Singstimmen ab Version 0.16).
# Die VOICEVOX-App oder die Engine läuft im Hintergrund; wir schicken ihr die Noten über ihre Schnittstelle
# (Standard http://127.0.0.1:50021) und bekommen den Gesang als WAV zurück. Tonhöhe und Lautstärke rechnet
# dabei eine Lehrer-Stimme aus, gesungen wird mit der gewählten Stimme. Die Sprechstimmen sprechen den Rap-Teil
# (rap.py).
import io
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

URL = "http://127.0.0.1:50021"
FRAME_RATE = 93.75           # Rahmen pro Sekunde beim Singen (24000 Hz / 256)
TEACHER = 6000               # Lehrer-Stimme, wenn die Engine keine nennt
PAD_FRAMES = 12              # VOICEVOX will vor dem ersten Ton eine Pause; sie wird danach abgeschnitten
SING_TYPES = ("frame_decode", "sing")
TEACHER_TYPES = ("singing_teacher", "sing")
MAX_RETRIES = 8
_KANA = re.compile(r"^[ぁ-ゖァ-ヺー]+$")
_INVALID = re.compile(r"lyricが不正です:\s*(\S+)")
# Lokale Engine: nie über einen Proxy
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

PitchFn = Callable[[np.ndarray, float, float], np.ndarray]


class VoicevoxError(RuntimeError):
    """VOICEVOX hat die Anfrage abgelehnt."""


def _request(url: str, path: str, params: dict = None, body=None, timeout: float = 10.0) -> bytes:
    full = url.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(full, data=data, method="GET" if data is None else "POST",
                                     headers={"Content-Type": "application/json"} if data else {})
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            text = str(json.loads(text).get("detail", text))
        except (ValueError, AttributeError):
            pass
        raise VoicevoxError(f"{path}: {e.code} {text[-300:]}") from e
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(f"VOICEVOX läuft nicht unter {url} ({e})") from e


def running(url: str = URL, timeout: float = 0.5) -> bool:
    """Ob VOICEVOX unter url antwortet (kurz gefragt, damit ein fehlendes VOICEVOX nichts aufhält)."""
    try:
        _request(url, "/version", timeout=timeout)
        return True
    except (ConnectionError, VoicevoxError):
        return False


def _styles(url: str, timeout: float) -> list:
    """[(Stil-ID, Name, Typ)] aller Stimmen, die singen können."""
    data = json.loads(_request(url, "/singers", timeout=timeout))
    return [(style["id"], f'{speaker["name"]} ({style["name"]})', style.get("type", "sing"))
            for speaker in data for style in speaker.get("styles", [])]


def singers(url: str = URL, timeout: float = 2.0) -> dict:
    """{Stil-ID: "Name (Stil)"} der Singstimmen. Leer, wenn VOICEVOX nicht läuft."""
    if not running(url):
        return {}
    try:
        return {sid: name for sid, name, kind in _styles(url, timeout) if kind in SING_TYPES}
    except (ConnectionError, VoicevoxError, ValueError, KeyError, TypeError) as e:
        log.debug("Keine VOICEVOX-Stimmen: %s", e)
        return {}


def pick_singer(url: str, wanted: int = 0) -> tuple:
    """(Stil-ID, Name) der gewünschten Singstimme, sonst der ersten. Wirft ConnectionError ohne VOICEVOX."""
    if not running(url):
        raise ConnectionError(f"VOICEVOX läuft nicht unter {url}")
    found = {sid: name for sid, name, kind in _styles(url, 3.0) if kind in SING_TYPES}
    if not found:
        raise VoicevoxError("VOICEVOX hat keine Singstimmen (die gibt es ab Version 0.16)")
    if wanted in found:
        return wanted, found[wanted]
    first = next(iter(found))
    if wanted:
        log.warning("VOICEVOX-Stimme %s gibt es nicht, singe mit %s", wanted, found[first])
    return first, found[first]


def talkers(url: str = URL, timeout: float = 2.0) -> dict:
    """{Stil-ID: "Name (Stil)"} der Sprechstimmen (für den Rap-Teil, rap.py). Leer, wenn VOICEVOX nicht läuft."""
    if not running(url):
        return {}
    try:
        data = json.loads(_request(url, "/speakers", timeout=timeout))
        return {style["id"]: f'{speaker["name"]} ({style["name"]})' for speaker in data
                for style in speaker.get("styles", []) if style.get("type", "talk") == "talk"}
    except (ConnectionError, VoicevoxError, ValueError, KeyError, TypeError) as e:
        log.debug("Keine VOICEVOX-Sprechstimmen: %s", e)
        return {}


def pick_talker(url: str, wanted: int = 0) -> tuple:
    """(Stil-ID, Name) der gewünschten Sprechstimme, sonst der ersten. Wirft ConnectionError ohne VOICEVOX."""
    if not running(url):
        raise ConnectionError(f"VOICEVOX läuft nicht unter {url}")
    found = talkers(url, 3.0)
    if not found:
        raise VoicevoxError("VOICEVOX hat keine Sprechstimmen")
    if wanted in found:
        return wanted, found[wanted]
    first = next(iter(found))
    if wanted:
        log.warning("VOICEVOX-Sprechstimme %s gibt es nicht, es spricht %s", wanted, found[first])
    return first, found[first]


def others(url: str, singer: int, count: int = 2) -> list:
    """Bis zu count andere Sänger (andere Figuren, nicht nur ein anderer Stil) für den Chor."""
    found = singers(url)
    taken = {found.get(singer, "").split(" (")[0]}
    picks = []
    for sid, name in found.items():
        person = name.split(" (")[0]
        if person not in taken:
            taken.add(person)
            picks.append(sid)
        if len(picks) == count:
            break
    return picks


def _teacher(url: str) -> int:
    try:
        styles = _styles(url, 3.0)
    except (VoicevoxError, ValueError, KeyError, TypeError):
        return TEACHER
    ranked = sorted((TEACHER_TYPES.index(kind), sid) for sid, _, kind in styles if kind in TEACHER_TYPES)
    return ranked[0][1] if ranked else TEACHER


def _lyric(text) -> Optional[str]:
    """Silbe für VOICEVOX: Kana bleiben, „っ“ wird eine kurze Pause, alles andere singt „ら“."""
    text = str(text).strip()
    if text in ("っ", "ッ"):
        return None
    return text if _KANA.match(text) else "ら"


def score(melody_data: list, silben: list, bpm: float, transpose: int = 0) -> dict:
    """Die Noten als VOICEVOX-Partitur: Längen in Rahmen, ohne dass sich Rundungsfehler aufsummieren."""
    from vocal_synthesizer import _gebunden
    spb = 60.0 / bpm
    notes = [{"key": None, "frame_length": PAD_FRAMES, "lyric": ""}]

    def rest(length: int) -> None:
        if notes[-1]["lyric"] == "":
            notes[-1]["frame_length"] += length
        else:
            notes.append({"key": None, "frame_length": length, "lyric": ""})

    t, edge, i = 0.0, 0, 0
    for pitch, dur in _gebunden(melody_data):
        t += dur * spb
        end = int(round(t * FRAME_RATE))
        length, edge = end - edge, end
        lyric = None
        if pitch is not None:
            lyric = _lyric(silben[i] if i < len(silben) else "ら")
            i += 1
        if length < 1:
            continue
        if lyric is None:
            rest(length)
        else:
            notes.append({"key": int(pitch) + transpose, "frame_length": length, "lyric": lyric})
    rest(PAD_FRAMES)
    return {"notes": notes}


def sing(melody_data: list, silben: list, bpm: float, wav: str, url: str = URL, singer: int = 0,
         transpose: int = 0, pitch: Optional[PitchFn] = None, timeout: float = 900.0,
         volume: Optional[PitchFn] = None) -> str:
    """
    Singt die Melodie mit VOICEVOX in die Datei wav (Beginn = Songanfang).
    pitch: ändert die Tonhöhenkurve vor dem Singen, bekommt (f0 in Hz je Rahmen, Rahmenlänge, Zeit des ersten
    Rahmens ab Songanfang). volume: genauso für die Lautstärke je Rahmen, die die Lehrer-Stimme vorgibt (F2); die
    Stimme singt sie selbst, leiser klingt dabei auch weicher. Silben, die VOICEVOX nicht kennt, singt die Stimme
    als „ら“.
    """
    notes = score(melody_data, silben, bpm, transpose)
    teacher = _teacher(url)
    for _ in range(MAX_RETRIES):
        try:
            query = json.loads(_request(url, "/sing_frame_audio_query", {"speaker": teacher}, notes, timeout))
            break
        except VoicevoxError as e:
            bad = _INVALID.search(str(e))
            changed = [n for n in notes["notes"] if bad and n["lyric"] == bad.group(1)]
            if not changed:
                raise
            log.warning("VOICEVOX kennt die Silbe %s nicht, dort wird „ら“ gesungen", bad.group(1))
            for n in changed:
                n["lyric"] = "ら"
    else:
        raise VoicevoxError("Zu viele Silben, die VOICEVOX nicht kennt")
    if pitch is not None:
        f0 = np.asarray(query["f0"], dtype=np.float64)
        query["f0"] = [float(v) for v in pitch(f0, 1.0 / FRAME_RATE, -PAD_FRAMES / FRAME_RATE)]
    if volume is not None and query.get("volume"):
        loud = np.asarray(query["volume"], dtype=np.float64)
        query["volume"] = [max(0.0, float(v)) for v in volume(loud, 1.0 / FRAME_RATE, -PAD_FRAMES / FRAME_RATE)]
    data = _request(url, "/frame_synthesis", {"speaker": singer}, query, timeout)
    audio, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    audio = audio[int(round(PAD_FRAMES / FRAME_RATE * rate)):]
    sf.write(wav, audio, rate, subtype="FLOAT")
    return wav
