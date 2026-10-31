# project.py – Songs als Projekt aufheben und wieder öffnen (v6 Nr. 5)
#
# Der Verlauf hebt pro Song die MP3 und alle Einstellungen samt Seed auf. Daraus entstehen Noten, Band und Mix genau
# wieder, nur der Gesang müsste neu gesungen werden (mit NEUTRINO dauert das Minuten, und jede Fassung klingt etwas
# anders). Deshalb liegt neben jedem Song im Verlauf ein Ordner mit seinem Gesang (FLAC, etwa halb so groß wie WAV).
# „Wieder öffnen“ legt den Gesang zurück in den Ausgabeordner und baut den Song neu: Band und Mix entstehen frisch,
# der Gesang wird übernommen. Danach lässt sich der Song weiter bearbeiten wie gerade erzeugt.
import json
import logging
import os
import shutil
from typing import Optional

log = logging.getLogger(__name__)

FILE = "projekt.json"
VERSION = 1


def folder(audio: str) -> str:
    """Der Projektordner eines Songs im Verlauf: neben MP3 und JSON, mit demselben Namen."""
    return os.path.splitext(audio)[0]


def available(audio: str) -> bool:
    return os.path.isfile(os.path.join(folder(audio), FILE))


def size(audio: str) -> int:
    """Bytes, die der Projektordner belegt."""
    target = folder(audio)
    if not os.path.isdir(target):
        return 0
    return sum(os.path.getsize(os.path.join(target, name)) for name in os.listdir(target)
               if os.path.isfile(os.path.join(target, name)))


def notes_print(tracks: dict) -> str:
    """Fingerabdruck der gesungenen Noten: passt er nicht mehr, gehört der Gesang nicht zu diesen Noten."""
    import hashlib
    import singing
    data = [tracks.get(k) for k in singing.NOTE_KEYS]
    return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def save(out: str, tracks: dict, audio: str) -> Optional[str]:
    """Hebt den Gesang des Songs in out neben dem Song audio im Verlauf auf. Rückgabe: der Projektordner, None ohne
    Gesang oder wenn es nicht ging (der Song im Verlauf bleibt)."""
    import soundfile as sf

    import singing
    import vocal_check
    sung = [name for name in singing.VOCAL_FILES if os.path.exists(os.path.join(out, name))]
    if "vocals.wav" not in sung or not audio:
        return None
    target = folder(audio)
    try:
        os.makedirs(target, exist_ok=True)
        for name in sung:
            data, rate = sf.read(os.path.join(out, name), dtype="float32", always_2d=True)
            sf.write(os.path.join(target, _flac(name)), data, rate, format="FLAC", subtype="PCM_24")
        who = os.path.join(out, vocal_check.SUNG_FILE)
        if os.path.exists(who):
            shutil.copyfile(who, os.path.join(target, vocal_check.SUNG_FILE))
        with open(os.path.join(target, FILE), "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "files": sung, "notes": notes_print(tracks)}, f)
    except (OSError, RuntimeError) as e:
        log.warning("Gesang nicht als Projekt aufgehoben: %s", e)
        shutil.rmtree(target, ignore_errors=True)
        return None
    log.info("Projekt aufgehoben: %s (%.0f MB)", target, size(audio) / 1e6)
    return target


def unpack(audio: str, settings, out: str) -> tuple:
    """Legt den aufgehobenen Gesang des Songs audio nach out, so dass der nächste Lauf mit settings (den
    Einstellungen dieses Songs) ihn übernimmt statt neu zu singen. Rückgabe: (geklappt, Meldung für die App)."""
    import soundfile as sf

    import pipeline
    import singing
    import vocal_check
    source = folder(audio)
    try:
        with open(os.path.join(source, FILE), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return False, "Zu diesem Song ist kein Gesang aufgehoben, er wird neu gesungen."
    tracks, _ = pipeline.compose(settings)
    if saved.get("notes") != notes_print(tracks):
        return False, "Die App schreibt diesen Song inzwischen etwas anders, der Gesang wird neu gesungen."
    try:
        os.makedirs(out, exist_ok=True)
        for name in singing.VOCAL_FILES + (singing.VOCAL_KEY, vocal_check.SUNG_FILE):
            path = os.path.join(out, name)
            if os.path.exists(path):
                os.remove(path)
        for name in saved.get("files", []):
            data, rate = sf.read(os.path.join(source, _flac(name)), dtype="float32", always_2d=True)
            sf.write(os.path.join(out, name), data, rate, subtype="FLOAT")
        if os.path.exists(os.path.join(source, vocal_check.SUNG_FILE)):
            shutil.copyfile(os.path.join(source, vocal_check.SUNG_FILE), os.path.join(out, vocal_check.SUNG_FILE))
    except (OSError, RuntimeError) as e:
        return False, f"Gesang nicht lesbar ({e}), er wird neu gesungen."
    singing._remember_vocals(out, singing.vocal_key(settings, tracks))
    return True, "Song wieder geöffnet: Band und Mix entstehen neu, der Gesang bleibt."


# 1.7.1: was das Video von einem Song braucht (Zeiten der Silben, Songkarte, wer gesungen hat); ein paar KB je Song
MAP_FILES = ("liedtext.json", "songkarte.json", "gesang.json")


def has_map(audio: str) -> bool:
    """Liegen Songkarte und Zeiten der Silben im Projektordner (ab 1.7.1)?"""
    return all(os.path.isfile(os.path.join(folder(audio), name)) for name in MAP_FILES[:2])


def keep_map(out: str, audio: str) -> bool:
    """Legt Songkarte und Zeiten der Silben des Songs in out neben den Song audio im Verlauf, damit ein Video von ihm
    auch dann geht, wenn im Ausgabeordner längst ein anderer liegt (pipeline.from_history). Auch ohne Gesang."""
    if not audio or not os.path.isfile(os.path.join(out, MAP_FILES[1])):
        return False
    target = folder(audio)
    try:
        os.makedirs(target, exist_ok=True)
        for name in MAP_FILES:
            if os.path.isfile(os.path.join(out, name)):
                shutil.copyfile(os.path.join(out, name), os.path.join(target, name))
    except OSError as e:
        log.warning("Songkarte nicht im Verlauf aufgehoben: %s", e)
        return False
    return True


def notes_of(audio: str) -> Optional[str]:
    """Der Fingerabdruck der Noten, zu denen der aufgehobene Gesang gehört; None ohne Projekt."""
    try:
        with open(os.path.join(folder(audio), FILE), encoding="utf-8") as f:
            return json.load(f).get("notes")
    except (OSError, ValueError, AttributeError):
        return None


def delete(audio: str) -> None:
    shutil.rmtree(folder(audio), ignore_errors=True)


def _flac(name: str) -> str:
    return os.path.splitext(name)[0] + ".flac"
