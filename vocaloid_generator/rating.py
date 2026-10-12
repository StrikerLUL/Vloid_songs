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
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import soundfile as sf

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "bewertung")
WORKER = os.path.join(config.BASE_DIR, "rating_worker.py")
MARKER = "BEWERTUNG "
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


def environment() -> dict:
    """Umgebungsvariablen für die Bewertung: das Modell liegt mit in tools/bewertung, nicht irgendwo im Profil."""
    return {**os.environ, "HF_HOME": os.path.join(FOLDER, "huggingface"), "PYTHONIOENCODING": "utf-8"}


def python() -> str:
    """Python der eigenen Umgebung."""
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def status() -> str:
    if not available():
        return "Automatische Bewertung fehlt: einmal uv run setup_bewertung.py ausführen"
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
    try:
        done = subprocess.run([python(), WORKER, *paths], capture_output=True, timeout=TIMEOUT, env=environment(),
                              encoding="utf-8", errors="replace", creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Bewertung fehlgeschlagen: %s", e)
        return [None] * len(paths)
    line = next((ln for ln in reversed(done.stdout.splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        log.warning("Bewertung fehlgeschlagen: %s", (done.stderr or done.stdout).strip()[-800:])
        return [None] * len(paths)
    try:
        found = json.loads(line[len(MARKER):])
    except ValueError:
        found = []
    ratings = [Rating.from_dict({"enjoyment": r.get("CE"), "usefulness": r.get("CU"), "complexity": r.get("PC"),
                                 "quality": r.get("PQ")}) if isinstance(r, dict) else None for r in found]
    return (ratings + [None] * len(paths))[:len(paths)]
