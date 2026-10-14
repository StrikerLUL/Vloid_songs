# resume.py – Weitermachen nach einem Absturz
#
# Während ein Song entsteht, liegen seine Einstellungen (samt Seed) in laufender_song.json im Datenordner. Endet der
# Song, auch mit Fehler oder Abbruch, verschwindet die Datei wieder. Liegt sie beim nächsten Start noch da, ist die
# App mittendrin ausgegangen: dann bietet sie an, denselben Song noch einmal zu erzeugen. Fertige Schritte (Gesang,
# gerenderte Spuren) liegen noch im Ausgabeordner und werden übernommen statt neu berechnet.
import json
import logging
import os
from datetime import datetime
from typing import Optional

import config
from settings import SongSettings

log = logging.getLogger(__name__)

FILE_NAME = "laufender_song.json"


def path() -> str:
    return os.path.join(config.DATA_DIR, FILE_NAME)


def start(settings: SongSettings) -> None:
    try:
        os.makedirs(os.path.dirname(path()), exist_ok=True)
        with open(path(), "w", encoding="utf-8") as f:
            json.dump({**settings.model_dump(), "gestartet": datetime.now().isoformat(timespec="seconds")}, f,
                      ensure_ascii=False)
    except OSError as e:
        log.debug("Laufenden Song nicht vermerkt: %s", e)


def finish() -> None:
    try:
        os.remove(path())
    except FileNotFoundError:
        pass
    except OSError as e:
        log.debug("Vermerk nicht gelöscht: %s", e)


def pending() -> Optional[tuple]:
    """(Einstellungen, Startzeit) des Songs, der beim letzten Mal nicht fertig wurde, sonst None."""
    if not os.path.exists(path()):
        return None
    try:
        with open(path(), encoding="utf-8") as f:
            started = json.load(f).get("gestartet", "")
        return SongSettings.load(path()), datetime.fromisoformat(started) if started else None
    except (OSError, ValueError) as e:
        log.warning("Vermerk des letzten Songs nicht lesbar: %s", e)
        finish()
        return None
