"""Die tatsächlich benutzte Klangerzeugung pro WAV, auch nach Wiederverwendung aus dem Cache."""
import json
import logging
import os

log = logging.getLogger(__name__)


def record(wav, engine, fallback=False, reason=""):
    path = wav + ".render.json"
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as stream:
            json.dump({"engine": engine, "fallback": fallback, "reason": reason}, stream, ensure_ascii=False)
        os.replace(path + ".tmp", path)
    except OSError as exc:
        log.debug("Klangstatus nicht gespeichert: %s", exc)


def read(wav):
    try:
        with open(wav + ".render.json", encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def warnings(wavs):
    return [f"{name}: einfache Ersatzklänge – {found.get('reason') or 'Klangerzeugung nicht verfügbar'}. "
            "Unter Hilfe › Einrichten die Instrumente prüfen."
            for name, path in wavs.items() if (found := read(path)).get("fallback")]
