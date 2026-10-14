# cancel.py – Einen laufenden Song abbrechen, auch mitten in NEUTRINO, ACE-Step oder der Bewertung
#
# Die Oberfläche ruft request(); der Ablauf (pipeline.py) prüft bei jedem Fortschrittsschritt mit check() und hört
# mit Cancelled auf. Externe Programme starten über run(): ein Abbruch beendet sie sofort, statt auf sie zu warten.
import logging
import subprocess
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

POLL = 0.2              # so oft schaut run() nach, ob abgebrochen wurde (Sekunden)


class Cancelled(Exception):
    """Der Song wurde abgebrochen."""

    def __init__(self, message: str = "Abgebrochen") -> None:
        super().__init__(message)


_requested = threading.Event()
_running: set = set()
_lock = threading.Lock()


def request() -> None:
    """Bricht ab: laufende Programme werden beendet, der Ablauf hört beim nächsten Schritt auf."""
    _requested.set()
    with _lock:
        processes = list(_running)
    for process in processes:
        _stop(process)
    log.info("Abbrechen angefordert")


def reset() -> None:
    _requested.clear()


def requested() -> bool:
    return _requested.is_set()


def check() -> None:
    if _requested.is_set():
        raise Cancelled()


def _stop(process: subprocess.Popen) -> None:
    try:
        process.kill()          # NEUTRINO und PyTorch reagieren auf terminate() nicht immer
    except OSError:
        pass


def run(cmd: list, timeout: Optional[float] = None, input_bytes: Optional[bytes] = None, **kwargs) \
        -> subprocess.CompletedProcess:
    """
    Wie subprocess.run (mit capture_output, text, encoding, stdout=..., cwd, env, creationflags), aber abbrechbar:
    wirft Cancelled, wenn während des Laufs abgebrochen wird, und subprocess.TimeoutExpired nach timeout Sekunden.
    """
    check()
    if kwargs.pop("capture_output", False):
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
    if input_bytes is not None:
        kwargs["stdin"] = subprocess.PIPE
    process = subprocess.Popen(cmd, **kwargs)
    with _lock:
        _running.add(process)
    result = {}

    def talk():        # liest die Ausgabe nebenher, damit volle Pipes das Programm nicht blockieren
        result["out"], result["err"] = process.communicate(input_bytes)

    reader = threading.Thread(target=talk, daemon=True, name="cancel-run")
    reader.start()
    started = time.monotonic()
    try:
        while reader.is_alive():
            reader.join(POLL)
            if _requested.is_set():
                _stop(process)
                reader.join(5)
                raise Cancelled()
            if timeout is not None and time.monotonic() - started > timeout:
                _stop(process)
                reader.join(5)
                raise subprocess.TimeoutExpired(cmd, timeout, result.get("out"), result.get("err"))
    finally:
        with _lock:
            _running.discard(process)
    return subprocess.CompletedProcess(cmd, process.returncode, result.get("out"), result.get("err"))


def stream(cmd: list, on_line, timeout: Optional[float] = None, **kwargs) -> int:
    """
    Startet cmd und gibt jede Zeile seiner Ausgabe (stdout und stderr) sofort an on_line weiter; abbrechbar wie run().
    Rückgabe: der Exit-Code.
    """
    import queue
    check()
    process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1, **kwargs)
    with _lock:
        _running.add(process)
    lines: queue.Queue = queue.Queue()

    def read():
        for line in process.stdout:
            lines.put(line.rstrip("\r\n"))
        lines.put(None)

    threading.Thread(target=read, daemon=True, name="cancel-stream").start()
    started = time.monotonic()
    try:
        while True:
            try:
                line = lines.get(timeout=POLL)
            except queue.Empty:
                line = ""
            if line:
                on_line(line)
            if _requested.is_set():
                _stop(process)
                raise Cancelled()
            if line is None:
                break
            if timeout is not None and time.monotonic() - started > timeout:
                _stop(process)
                raise subprocess.TimeoutExpired(cmd, timeout)
        return process.wait()
    finally:
        with _lock:
            _running.discard(process)
