# applog.py – Protokoll in eine Datei: was die App tut und jeder Fehler mit Stack, auch nach einem Absturz lesbar
#
# Die Datei liegt im Datenordner unter Protokolle\vloid_songs.log (höchstens 3 × 2 MB, die älteste fällt heraus).
# Unbehandelte Fehler, auch in Hintergrund-Threads, landen ebenfalls dort. Der Fehlerbericht (fehlerbericht.py)
# packt diese Dateien in ein ZIP.
import logging
import logging.handlers
import os
import sys
import threading
from typing import Optional

import config

FILE_NAME = "vloid_songs.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 2
FORMAT = "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"

log = logging.getLogger(__name__)
_handler: Optional[logging.Handler] = None


def path(folder: str = None) -> str:
    return os.path.join(folder or config.LOG_DIR, FILE_NAME)


def files(folder: str = None) -> list:
    """Die Protokolldatei und ihre älteren Teile, die neueste zuerst."""
    first = path(folder)
    return [p for p in [first] + [f"{first}.{n}" for n in range(1, BACKUPS + 1)] if os.path.exists(p)]


def setup(to_file: bool = True, folder: str = None, level: int = logging.INFO) -> Optional[str]:
    """Schreibt ab jetzt alles ab level in die Datei (to_file=False: nur Fehler über excepthook ins Fenster)."""
    global _handler
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)            # das Fenster filtert selbst (main.py), die Datei bekommt alles ab level
    if _handler is not None:
        root.removeHandler(_handler)
        _handler.close()
        _handler = None
    target = None
    if to_file:
        target = path(folder)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            _handler = logging.handlers.RotatingFileHandler(target, maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                                            encoding="utf-8", delay=True)
        except OSError as e:
            log.warning("Protokolldatei nicht nutzbar (%s), es wird nur im Fenster protokolliert.", e)
            target = None
        else:
            _handler.setLevel(level)
            _handler.setFormatter(logging.Formatter(FORMAT))
            root.addHandler(_handler)
    _catch_crashes()
    return target


def close() -> None:
    setup(to_file=False)


def _catch_crashes() -> None:
    """Unbehandelte Fehler im Haupt- und in jedem anderen Thread mit Stack ins Protokoll."""
    def main_thread(kind, error, trace):
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, error, trace)
            return
        logging.getLogger("absturz").critical("Unbehandelter Fehler", exc_info=(kind, error, trace))

    def other_thread(args):
        if args.exc_type is SystemExit:
            return
        logging.getLogger("absturz").critical("Unbehandelter Fehler im Thread %s",
                                              args.thread.name if args.thread else "?",
                                              exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = main_thread
    threading.excepthook = other_thread
