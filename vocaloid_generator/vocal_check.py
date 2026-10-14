# vocal_check.py – Gesangs-Check: wer hat gesungen?
#
# Nach dem Singen schreibt die App gesang.json in den Song-Ordner: Engine, Stimme, NEUTRINO-Ausgabe, Grafikkarte
# oder Prozessor. Der Player zeigt das als Zeile („Gesungen von NEUTRINO 3.2.2, MERROW, Grafikkarte“), und hat die
# Vorschau-Stimme gesungen, obwohl NEUTRINO oder VOICEVOX gewählt war, steht dort eine rote Warnung. Die Ersatzstimme
# klingt absichtlich schlecht; sie soll nie wieder unbemerkt im fertigen Song landen.
import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

SUNG_FILE = "gesang.json"


def record(out: str, settings, engine: str, voice: str = "") -> dict:
    """Festhalten, wer gesungen hat (engine: NEUTRINO, VOICEVOX oder Vorschau)."""
    info = {"engine": engine, "voice": voice, "chosen": settings.vocal_engine}
    if engine == "NEUTRINO":
        from vocal_synthesizer import LETZTER_LAUF, neutrino_ausgabe
        info["version"] = neutrino_ausgabe(settings.neutrino_dir())
        device = LETZTER_LAUF.get("grafikkarte")
        info["device"] = "" if device is None else ("Grafikkarte" if device else "Prozessor")
    try:
        with open(os.path.join(out, SUNG_FILE), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)
    except OSError as e:
        log.debug("%s nicht gespeichert: %s", SUNG_FILE, e)
    text, warn = describe(info)
    (log.warning if warn else log.info)(text)
    return info


def read(out: str) -> Optional[dict]:
    try:
        with open(os.path.join(out, SUNG_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def describe(info: Optional[dict]) -> tuple:
    """(Zeile für den Player, Warnung?)."""
    if not info:
        return "", False
    engine = info.get("engine", "")
    if engine == "Vorschau":
        if info.get("chosen") == "Vorschau":
            return "Gesungen von der Vorschau-Stimme (so gewählt)", False
        return ("Achtung: Hier singt die Vorschau-Stimme, weder NEUTRINO noch VOICEVOX hat gesungen. Sie klingt "
                "absichtlich schlecht. Das Protokoll sagt, warum; NEUTRINO lässt sich unter Hilfe › Einrichten "
                "einrichten."), True
    parts = [f"NEUTRINO {info['version']}" if engine == "NEUTRINO" and info.get("version") else engine]
    parts += [p for p in (info.get("voice"), info.get("device")) if p]
    text = "Gesungen von " + ", ".join(parts)
    if engine != info.get("chosen") and info.get("chosen"):
        text += f" ({info['chosen']} fehlte)"
    return text, False
