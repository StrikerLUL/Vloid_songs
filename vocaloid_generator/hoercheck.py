# hoercheck.py – Hör-Check: versteht man den Text? (1.5.0, St4)
#
# Nach dem Singen hört eine japanische Spracherkennung (faster-whisper „small“, MIT-Lizenz, etwa 500 MB) die
# Gesangsspur ab, ohne den Text zu kennen, und die App vergleicht Zeile für Zeile, was sie gehört hat, mit dem, was
# gesungen werden sollte (beides als Hiragana). Zeilen, die kaum wiederzuerkennen sind, stehen danach unter dem Player
# und in hoer_check.txt im Songordner, mit den Wörtern der Zeile, wie die App sie liest, als Vorlage für Lesungen.txt.
# Hat die App ein Wort falsch gelesen (既読 als きよみ), passen die Laute zwar, aber die Erkennung schreibt ein anderes
# Wort (清美): solche Wörter stehen als „Lesung prüfen“ dabei.
# Die Erkennung läuft wie die Bewertung in einer eigenen Umgebung (tools/hoercheck, einmal uv run
# setup_hoercheck.py) auf dem Prozessor. Fehlt sie, passiert nichts.
import difflib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

import cancel
import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "hoercheck")
WORKER = os.path.join(config.BASE_DIR, "hoercheck_worker.py")
MODEL = "small"                 # faster-whisper lädt Systran/faster-whisper-small
MARKER = "HOERCHECK "
RESULT_FILE = "hoer_check.json"
REPORT_FILE = "hoer_check.txt"
LOG_FILE = "letzter_lauf.log"
TIMEOUT = 1800
GOOD = 0.6                      # so ähnlich muss das Gehörte dem gesungenen Text sein (0 bis 1)
MARGIN = 0.25                   # Sekunden: Wörter so knapp vor oder nach der Zeile gehören noch zu ihr
_NOT_KANA = re.compile(r"[^ぁ-ゖ]")
_SAME_SOUND = str.maketrans({"を": "お", "ぢ": "じ", "づ": "ず"})


@dataclass
class Line:
    start: float
    end: float
    text: str                   # wie geschrieben (mit Kanji), sonst die gesungenen Kana
    expected: str               # die gesungenen Kana
    heard: str                  # was die Erkennung gehört hat
    score: float                # 0 bis 1
    # „Wort=Lesung“, wie die App sie liest: bei einer undeutlichen Zeile alle Wörter mit Kanji, sonst die, die die
    # Erkennung nicht so geschrieben hat (vielleicht falsch gelesen)
    readings: list = field(default_factory=list)

    @property
    def clear(self) -> bool:
        return self.score >= GOOD

    @property
    def doubtful(self) -> bool:
        return self.clear and bool(self.readings)


def model_folder() -> str:
    return os.path.join(FOLDER, "huggingface")


def environment() -> dict:
    return {**os.environ, **config.hf_environment(model_folder()), "PYTHONIOENCODING": "utf-8"}


def python() -> str:
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def status() -> str:
    if not available():
        return "Hör-Check fehlt: einmal uv run setup_hoercheck.py ausführen"
    return "Hör-Check (faster-whisper) ist eingerichtet"


def problem() -> str:
    return f"Die Spracherkennung lief nicht (Ausgabe in {os.path.join(FOLDER, LOG_FILE)})"


# ── Vergleichen ──────────────────────────────────────────────────────────────────
def normalize(kana: str) -> str:
    """Nur Hiragana, Laute, die gleich klingen, gleich geschrieben (を/お, づ/ず)."""
    text = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kana)
    return _NOT_KANA.sub("", text).translate(_SAME_SOUND)


def similarity(expected: str, heard: str) -> float:
    a, b = normalize(expected), normalize(heard)
    if not a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def kanji_readings(text: str) -> list:
    """[„Wort=Lesung“] der Wörter mit Kanji in einer Zeile, so wie die App sie singt."""
    import lyrics
    tagger = lyrics._tagger()
    if tagger is None or not lyrics._KANJI.search(text or ""):
        return []
    # Kanji-Wörter direkt hintereinander gehören zusammen: kennt das Wörterbuch 既読 nicht, zerlegt es 既 + 読
    groups, joined = [], False
    for token in tagger(text):
        surface = token.surface
        has = bool(lyrics._KANJI.search(surface))
        if has and joined:
            groups[-1] += surface
        elif has:
            groups.append(surface)
        joined = has
    out = []
    for surface in groups:
        entry = f"{surface}={lyrics.to_kana(surface)}"
        if entry not in out:
            out.append(entry)
    return out


def compare(lines: list, words: list) -> list:
    """Line je Zeile aus liedtext.json; words [{"start", "end", "word"}] von der Erkennung."""
    import lyrics
    found = []
    for line in lines:
        expected = "".join(s[2] for s in line.get("syllables", []))
        if not normalize(expected):
            continue
        start, end = float(line["start"]), float(line["end"])
        heard = "".join(w["word"] for w in words
                        if start - MARGIN <= (float(w["start"]) + float(w["end"])) / 2 <= end + MARGIN).strip()
        text = line.get("text") or expected
        found.append(Line(start=start, end=end, text=text, expected=expected, heard=heard,
                          score=round(similarity(expected, lyrics.to_kana(heard) if heard else ""), 3)))
    for line in found:
        words = kanji_readings(line.text)
        line.readings = words if not line.clear else [w for w in words if w.split("=")[0] not in line.heard]
    return found


def describe(found: list) -> tuple:
    """(Zeile unter dem Player, Warnung?)."""
    if not found:
        return "", False
    unclear = [line for line in found if not line.clear]
    doubtful = list(dict.fromkeys(w for line in found if line.doubtful for w in line.readings))
    check = f"; Lesung prüfen: {', '.join(doubtful[:3])}" + (" …" if len(doubtful) > 3 else "") if doubtful else ""
    if not unclear:
        return f"Hör-Check: alle {len(found)} Zeilen verständlich{check}", bool(doubtful)
    names = ", ".join(f"„{line.text}“" for line in unclear[:3]) + (" …" if len(unclear) > 3 else "")
    return (f"Hör-Check: {len(unclear)} von {len(found)} Zeilen undeutlich: {names}{check} (Details in "
            f"{REPORT_FILE})", True)


def report(found: list) -> str:
    lines = ["Hör-Check: Was die Spracherkennung im Gesang gehört hat", "",
             f"Eine Zeile gilt als undeutlich, wenn weniger als {GOOD:.0%} ihrer Laute wiederzuerkennen sind. Liest die",
             "App ein Wort falsch, trag es in Lesungen.txt ein (Tab Text › Eigene Lesungen), als „Wort=Lesung“.",
             ""]
    for line in found:
        mark = "!! " if not line.clear else "?  " if line.doubtful else "ok "
        lines.append(f"{mark}{_time(line.start)}  {line.text}")
        if not line.clear or line.doubtful:
            lines.append(f"     gesungen: {line.expected}")
            lines.append(f"     gehört:   {line.heard or '(nichts)'}   ({line.score:.0%})")
            for entry in line.readings:
                lines.append(f"     Lesung prüfen: {entry}")
    return "\n".join(lines) + "\n"


def _time(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def load(folder: str) -> list:
    """Das Ergebnis des letzten Hör-Checks in einem Songordner; leer, wenn es keins gibt."""
    try:
        with open(os.path.join(folder, RESULT_FILE), encoding="utf-8") as f:
            return [Line(**item) for item in json.load(f)]
    except (OSError, ValueError, TypeError):
        return []


# ── Erkennen ─────────────────────────────────────────────────────────────────────
def check_song(folder: str, vocals: str, progress=None) -> list:
    """Hört vocals ab und vergleicht mit liedtext.json in folder; schreibt hoer_check.json und hoer_check.txt.
    Leer ohne Erkennung oder ohne Text."""
    import karaoke
    for name in (RESULT_FILE, REPORT_FILE):
        try:
            os.remove(os.path.join(folder, name))       # ein Ergebnis vom letzten Song darf nicht als neues gelten
        except OSError:
            pass
    lines = karaoke.load(os.path.join(folder, karaoke.FILE))
    if not available() or not lines or not vocals or not os.path.exists(vocals):
        return []
    if progress:
        progress(0.5, "Hör-Check: die Spracherkennung hört den Gesang ab...")
    words = transcribe(vocals, folder)
    if words is None:
        return []
    found = compare(lines, words)
    with open(os.path.join(folder, RESULT_FILE), "w", encoding="utf-8") as f:
        json.dump([asdict(line) for line in found], f, ensure_ascii=False, indent=1)
    with open(os.path.join(folder, REPORT_FILE), "w", encoding="utf-8") as f:
        f.write(report(found))
    log.info(describe(found)[0])
    return found


def transcribe(audio: str, folder: str) -> Optional[list]:
    """[{"start", "end", "word"}] der Erkennung; None, wenn sie nicht lief."""
    request = os.path.join(folder, "hoercheck_auftrag.json")
    output = os.path.join(folder, "hoercheck_woerter.json")
    with open(request, "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "audio": os.path.abspath(audio), "output": output, "folder": model_folder()}, f)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    config.hf_without_links(model_folder())
    try:
        done = cancel.run([python(), WORKER, request], capture_output=True, timeout=TIMEOUT, env=environment(),
                          encoding="utf-8", errors="replace", creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Hör-Check fehlgeschlagen: %s", e)
        return None
    finally:
        try:
            os.remove(request)
        except OSError:
            pass
    try:
        os.makedirs(FOLDER, exist_ok=True)
        with open(os.path.join(FOLDER, LOG_FILE), "w", encoding="utf-8") as f:
            f.write((done.stdout or "") + "\n" + (done.stderr or ""))
    except OSError:
        pass
    marked = any(ln.startswith(MARKER) for ln in (done.stdout or "").splitlines())
    if done.returncode != 0 or not marked:
        log.warning("Hör-Check fehlgeschlagen: %s", (done.stderr or done.stdout or "").strip()[-800:])
        return None
    try:
        with open(output, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
    finally:
        try:
            os.remove(output)
        except OSError:
            pass


def probe(folder: str) -> bool:
    """Lädt das Modell und hört eine Sekunde Stille ab (Systemcheck, Einrichten)."""
    import numpy as np
    import soundfile as sf
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "probe.wav")
    sf.write(path, np.zeros(16000, dtype=np.float32), 16000)
    return transcribe(path, folder) is not None
