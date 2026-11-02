# rating.py – mehrere Fassungen eines Songs automatisch bewerten (Meta Audiobox Aesthetics)
#
# Das Modell hört von jedem Song die lautesten 30 Sekunden (meist den Refrain) und schätzt auf einer Skala von 1 bis
# 10, wie gern man zuhört (CE, Content Enjoyment), wie sauber er produziert ist (PQ, Production Quality), wie
# brauchbar er ist (CU) und wie vielschichtig (PC). Die Note ist der Mittelwert aus Hörspaß und Klang. Es läuft in
# einer eigenen Umgebung (tools/bewertung, einmal uv run setup_bewertung.py), damit PyTorch die App nicht berührt;
# mit NVIDIA-Grafikkarte auf ihr, sonst auf dem Prozessor. Fehlt die Umgebung, bleibt alles wie bisher.
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import soundfile as sf

import cancel
import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "bewertung")
WORKER = os.path.join(config.BASE_DIR, "rating_worker.py")
MARKER = "BEWERTUNG "
# Fehlt der Umgebung ein Paket, steht sein Name hier; „Einrichten“ bietet die Bewertung dann wieder an, und
# setup_bewertung.py lädt nur das Fehlende nach (z. B. requests, das Audiobox braucht, aber nicht mitbringt)
INCOMPLETE = "unvollstaendig.txt"
EXCERPT_SECONDS = 30.0
TIMEOUT = 1800          # Sekunden; beim ersten Mal lädt das Modell noch seine Gewichte herunter


@dataclass(frozen=True)
class Rating:
    enjoyment: float        # CE
    usefulness: float       # CU
    complexity: float       # PC
    quality: float          # PQ

    @property
    def overall(self) -> float:
        return (self.enjoyment + self.quality) / 2

    def describe(self) -> str:
        return f"Note {self.overall:.1f} (Hörspaß {self.enjoyment:.1f}, Klang {self.quality:.1f})"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data) -> Optional["Rating"]:
        try:
            return cls(**{k: float(data[k]) for k in ("enjoyment", "usefulness", "complexity", "quality")})
        except (KeyError, TypeError, ValueError):
            return None


def model_folder() -> str:
    return os.path.join(FOLDER, "huggingface")


def environment() -> dict:
    """Umgebungsvariablen für die Bewertung: das Modell liegt mit in tools/bewertung, nicht irgendwo im Profil."""
    return {**os.environ, **config.hf_environment(model_folder()), "PYTHONIOENCODING": "utf-8"}


def python() -> str:
    """Python der eigenen Umgebung."""
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def _incomplete() -> str:
    return os.path.join(FOLDER, INCOMPLETE)


def missing_package() -> Optional[str]:
    """Das Paket, das der Umgebung beim letzten Bewerten fehlte; None, wenn nichts fehlte."""
    try:
        with open(_incomplete(), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def complete() -> bool:
    """Eingerichtet und ohne fehlendes Paket (für den Einrichten-Assistenten)."""
    return available() and missing_package() is None


def mark_complete() -> None:
    try:
        os.remove(_incomplete())
    except OSError:
        pass


def _note_missing(output: str) -> Optional[str]:
    """Steht in output „No module named 'x'“, merkt sich x als fehlendes Paket."""
    found = re.search(r"No module named '([\w.]+)'", output)
    if not found:
        return None
    package = found.group(1).split(".")[0]
    try:
        with open(_incomplete(), "w", encoding="utf-8") as f:
            f.write(package)
    except OSError:
        pass
    return package


def problem() -> str:
    """Warum die Bewertung nicht lief, in einem Satz für Systemcheck und Oberfläche."""
    package = missing_package()
    if package:
        return (f"In der Umgebung der Bewertung fehlt das Paket „{package}“: unter Hilfe › Einrichten „Automatische "
                "Bewertung“ noch einmal einrichten, das lädt nur das Fehlende nach")
    return "Die Bewertung lief nicht (Protokoll ansehen)"


def status() -> str:
    if not available():
        return "Automatische Bewertung fehlt: einmal uv run setup_bewertung.py ausführen"
    if missing_package():
        return problem()
    return "Automatische Bewertung (Audiobox Aesthetics) ist eingerichtet"


def excerpt(audio_path: str, target: str, seconds: float = EXCERPT_SECONDS) -> Optional[str]:
    """Die lautesten seconds Sekunden von audio_path als WAV nach target; None, wenn die Datei nicht lesbar ist."""
    try:
        data, rate = sf.read(audio_path, dtype="float32", always_2d=True)
    except (RuntimeError, OSError) as e:        # soundfile: LibsndfileError ist ein RuntimeError
        log.warning("Bewertung: %s nicht lesbar (%s)", audio_path, e)
        return None
    blocks = len(data) // rate
    span = int(seconds)
    if blocks > span:
        energy = np.square(data[:blocks * rate].mean(axis=1)).reshape(blocks, rate).sum(axis=1)
        windows = np.convolve(energy, np.ones(span), mode="valid")
        start = int(np.argmax(windows)) * rate
        data = data[start:start + span * rate]
    sf.write(target, data, rate, subtype="FLOAT")
    return target


def rate(paths: list) -> list:
    """Bewertet WAV-Dateien in einem Durchgang; pro Datei eine Rating oder None (nicht eingerichtet, Fehler)."""
    if not paths or not available():
        return [None] * len(paths)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)       # unter Windows ohne schwarzes Fenster
    config.hf_without_links(model_folder())                 # 1.2.1 und älter legten Verknüpfungen an
    try:
        done = cancel.run([python(), WORKER, *paths], capture_output=True, timeout=TIMEOUT, env=environment(),
                          encoding="utf-8", errors="replace", creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Bewertung fehlgeschlagen: %s", e)
        return [None] * len(paths)
    line = next((ln for ln in reversed(done.stdout.splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        output = (done.stderr or done.stdout).strip()
        log.warning("Bewertung fehlgeschlagen: %s", output[-800:])
        if _note_missing(output):
            log.warning("%s", problem())
        return [None] * len(paths)
    mark_complete()
    try:
        found = json.loads(line[len(MARKER):])
    except ValueError:
        found = []
    ratings = [Rating.from_dict({"enjoyment": r.get("CE"), "usefulness": r.get("CU"), "complexity": r.get("PC"),
                                 "quality": r.get("PQ")}) if isinstance(r, dict) else None for r in found]
    return (ratings + [None] * len(paths))[:len(paths)]


def excerpts(audio_path: str, folder: str, seconds: float = 20.0) -> list:
    """Anfang, mittlere Teile, Schluss und stärkster Energieübergang getrennt bewerten."""
    try:
        data, rate = sf.read(audio_path, dtype="float32", always_2d=True)
    except (RuntimeError, OSError) as exc:
        log.warning("Bewertung: %s nicht lesbar (%s)", audio_path, exc)
        return []
    if not len(data) or rate <= 0:
        return []
    duration = len(data) / rate
    span = min(max(1.0, seconds), duration)
    last = max(0.0, duration - span)
    starts = [last * x for x in (0.0, 1 / 3, 2 / 3, 1.0)]
    blocks = len(data) // rate
    if blocks > 2:
        # Kanalenergie statt Mono-Summe: gegenphasige Stereosignale dürfen nicht als Stille gelten.
        energy = np.square(data[:blocks * rate]).reshape(blocks, rate, data.shape[1]).mean(axis=(1, 2))
        change = np.abs(np.diff(np.log10(energy + 1e-9)))
        edge = min(len(change) // 3, max(1, int(span / 2)))
        if len(change) > 2 * edge:
            change[:edge] = -1
            change[-edge:] = -1
        transition = max(0.0, min(last, float(np.argmax(change) + 1) - span / 2))
        starts.append(transition)
    os.makedirs(folder, exist_ok=True)
    saved, positions = [], []
    for start in sorted(starts):
        if any(abs(start - old) < span * 0.45 for old in positions):
            continue
        a = int(start * rate)
        piece = data[a:a + int(span * rate)]
        if not np.any(np.abs(piece) > 1e-6):
            continue
        path = os.path.join(folder, f"abschnitt_{len(saved) + 1}.wav")
        sf.write(path, piece, rate, subtype="FLOAT")
        saved.append(path)
        positions.append(start)
    return saved


def aggregate(ratings: list) -> Optional[Rating]:
    """Schwache Abschnitte zählen mit; fehlende Modellurteile werden nicht als gute Noten ersetzt."""
    if not ratings or any(r is None for r in ratings):
        return None
    fields = ("enjoyment", "usefulness", "complexity", "quality")
    return Rating(**{field: 0.75 * sum(getattr(r, field) for r in ratings) / len(ratings)
                    + 0.25 * min(getattr(r, field) for r in ratings) for field in fields})

