# laufzeit.py – Restzeit aus früheren Läufen und Meldung, wenn ein Song fertig ist (v6 Nr. 10)
#
# Jeder fertige Lauf merkt sich, wann er welchen Fortschritt erreicht hat (laufzeiten.json im Datenordner). Ein neuer
# Lauf vergleicht sich mit den letzten seiner Art (gleiche Engine, Entwurf oder nicht, Zahl der Fassungen): ist er
# bis hierher langsamer als sie, braucht er auch für den Rest länger. Ohne frühere Läufe schätzt er aus dem
# bisherigen Fortschritt. Die Meldung ist eine Windows-Benachrichtigung (wie bei Mails), nur nach längeren Läufen.
import json
import logging
import os
import subprocess
import sys
from typing import Optional

import config

log = logging.getLogger(__name__)

FILE = "laufzeiten.json"
KEEP = 8                    # so viele Läufe je Art
MIN_FRACTION = 0.1          # ohne frühere Läufe: erst ab diesem Fortschritt eine Schätzung
NOTICE_AFTER = 20.0         # Sekunden: kürzere Läufe sieht man ja kommen
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"   # zeigt jede Windows-Version


def _path() -> str:
    return os.path.join(config.DATA_DIR, FILE)


def kind(settings, n: int = 1, draft: bool = False) -> str:
    """Welche Läufe sich vergleichen lassen."""
    return f"{'Entwurf' if draft else 'Song'}|{n}|{settings.vocal_engine}"


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def past(what: str) -> list:
    """Die letzten Läufe dieser Art: [{"marks": [[Anteil, Sekunden]], "total": Sekunden}]."""
    return [run for run in _load().get(what, []) if run.get("total", 0) > 0 and run.get("marks")]


def typical(what: str) -> Optional[float]:
    """Wie lange Läufe dieser Art meist dauern (Median in Sekunden); None ohne frühere Läufe."""
    totals = sorted(run["total"] for run in past(what))
    return totals[len(totals) // 2] if totals else None


def record(what: str, marks: list, total: float) -> None:
    """Einen fertigen Lauf merken; marks: [(Anteil 0–1, Sekunden seit dem Start)]."""
    data = _load()
    runs = data.get(what, []) + [{"marks": [[round(f, 4), round(t, 2)] for f, t in marks], "total": round(total, 2)}]
    data[what] = runs[-KEEP:]
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        log.debug("%s nicht gespeichert: %s", FILE, e)


def _time_at(marks: list, fraction: float) -> Optional[float]:
    """Wann ein früherer Lauf diesen Fortschritt erreicht hat (dazwischen gerade gerechnet)."""
    before = (0.0, 0.0)
    for f, t in marks:
        if f >= fraction:
            if f - before[0] < 1e-9:
                return t
            return before[1] + (t - before[1]) * (fraction - before[0]) / (f - before[0])
        before = (f, t)
    return None


def remaining(runs: list, fraction: float, elapsed: float) -> Optional[float]:
    """Geschätzte Sekunden bis fertig; None, wenn sich noch nichts sagen lässt."""
    if fraction >= 1.0:
        return 0.0
    guesses = []
    for run in runs:
        then = _time_at(run["marks"], fraction)
        if then is not None and then > 0.5 and elapsed > 0.5:
            guesses.append((run["total"] - then) * elapsed / then)
    if guesses:
        guesses.sort()
        return max(0.0, guesses[len(guesses) // 2])
    if fraction >= MIN_FRACTION and elapsed > 2.0:
        return elapsed * (1.0 - fraction) / fraction
    return None


def describe(seconds: Optional[float]) -> str:
    """„noch etwa 3 Min.“; leer ohne Schätzung."""
    if seconds is None:
        return ""
    if seconds < 60:
        return f"noch etwa {max(5, int(round(seconds / 5)) * 5)} s"
    return f"noch etwa {int(round(seconds / 60))} Min."


def notify(title: str, message: str, elapsed: float) -> bool:
    """Windows-Benachrichtigung nach einem Lauf ab NOTICE_AFTER Sekunden; True, wenn sie abgeschickt wurde."""
    if elapsed < NOTICE_AFTER or sys.platform != "win32":
        return False

    def quoted(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]"
        " > $null; "
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$x = $t.GetElementsByTagName('text'); "
        f"$x.Item(0).AppendChild($t.CreateTextNode({quoted(title)})) > $null; "
        f"$x.Item(1).AppendChild($t.CreateTextNode({quoted(message)})) > $null; "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        f"{quoted(APP_ID)}).Show([Windows.UI.Notifications.ToastNotification]::new($t))")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                          "-Command", script], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as e:
        log.debug("Benachrichtigung nicht gezeigt: %s", e)
        return False
