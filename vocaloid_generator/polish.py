# polish.py – Klang-Veredler (Versuch): ACE-Step 1.5 spielt die fertige Band mit eigenem Klang neu ein
#
# ACE-Step bekommt nur die Band, nie den Gesang (die Lizenz von NEUTRINO verbietet, seine Stimme umzuwandeln). Es nimmt
# die Band als Vorlage („Cover“): Takt, Akkorde und Melodie bleiben, der Klang wird neu erzeugt, je nach Stärke mehr
# oder weniger. Danach liegt die veredelte Band genau unter dem Gesang und wird mit ihm zu einer zweiten Fassung
# gemischt (final_mix_veredelt.wav); der normale Song bleibt, wie er ist.
# ACE-Step läuft in einer eigenen Umgebung (tools/ace-step, einmal uv run setup_ace_step.py) und braucht eine
# NVIDIA-Grafikkarte; fehlt die Umgebung, bleibt alles wie bisher.
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf

import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "ace-step")
WORKER = os.path.join(config.BASE_DIR, "polish_worker.py")
MARKER = "VEREDELT "
READY_FILE = "bereit.json"      # schreibt setup_ace_step.py, wenn Modell und Probe geklappt haben
LOG_FILE = "letzter_lauf.log"   # was ACE-Step beim letzten Mal ausgegeben hat, zum Nachlesen bei Fehlern
TIMEOUT = 3600                  # Sekunden; auf kleinen Grafikkarten lagert ACE-Step viel in den Arbeitsspeicher aus
MAX_SHIFT = 0.25                # so weit (Sekunden) darf die neue Band verrutscht sein, bevor sie angelegt wird
SAMPLE_RATE = 44100

# Was ACE-Step aus der Vorlage machen soll, pro Stil (Englisch, so wurde das Modell trainiert)
CAPTIONS = {
    "J-Pop Energy": "energetic j-pop, anime opening, bright electric guitars, piano, supersaw synths, punchy drums",
    "Dark Vocaloid": "dark vocaloid rock, distorted electric guitars, synth bass, dramatic strings, hard drums",
    "Kawaii Chiptune": "kawaii chiptune pop, 8-bit square wave leads, bright bells, bouncy bass, upbeat drums",
    "Rock": "japanese rock band, overdriven electric guitars, bass guitar, live drums, energetic",
    "Ballade": "emotional j-pop ballad, grand piano, lush strings, soft drums, warm and intimate",
    "City Pop": "80s japanese city pop, funky slap bass, electric piano, clean guitar, brass section, smooth groove",
    "Future Bass": "future bass, wide supersaw chords, sidechained synths, trap drums, sparkling plucks",
    "Drum and Bass": "liquid drum and bass, fast breakbeats, deep sub bass, atmospheric pads",
    "Lo-Fi": "lo-fi hip hop, mellow electric piano, dusty drums, warm tape sound, relaxed",
    "Idol-Pop": "japanese idol pop, cheerful, bright synths, brass hits, four on the floor drums, sparkling bells",
}
DEFAULT_CAPTION = "j-pop, bright band, piano, synths, drums"
PRODUCTION = "instrumental, polished studio production, clear mix"


def source() -> str:
    """Hierhin lädt setup_ace_step.py ACE-Step 1.5 mit seinen Modellen (checkpoints)."""
    return os.path.join(FOLDER, "ACE-Step-1.5")


def python() -> str:
    """Python der Umgebung von ACE-Step (uv sync legt sie als .venv in den Quellordner)."""
    if sys.platform == "win32":
        return os.path.join(source(), ".venv", "Scripts", "python.exe")
    return os.path.join(source(), ".venv", "bin", "python")


def ready() -> Optional[dict]:
    """Was setup_ace_step.py bei der Probe gefunden hat ({"name", "memory_gb", "cuda"}), oder None."""
    if not os.path.isfile(python()):
        return None
    try:
        with open(os.path.join(FOLDER, READY_FILE), encoding="utf-8") as f:
            found = json.load(f)
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def available() -> bool:
    return ready() is not None


def status(settings=None) -> str:
    found = ready()
    if found is None:
        return "Klang-Veredler (ACE-Step, Versuch) fehlt: einmal uv run setup_ace_step.py ausführen"
    if settings is not None and not settings.polish:
        return "Klang-Veredler (ACE-Step): aus"
    if not found.get("cuda"):
        return "Klang-Veredler (ACE-Step) ist eingerichtet, aber ohne NVIDIA-Grafikkarte sehr langsam"
    return f"Klang-Veredler (ACE-Step) ist eingerichtet: {found.get('name', 'Grafikkarte')}, " \
           f"{found.get('memory_gb', 0):g} GB"


def caption(settings) -> str:
    own = (settings.polish_caption or "").strip()
    if own:
        return own
    return f"{CAPTIONS.get(settings.style, DEFAULT_CAPTION)}, {PRODUCTION}"


def key_scale(plan) -> str:
    """Tonart, wie ACE-Step sie versteht: „A minor“; Kirchentonarten zählen als Dur oder Moll."""
    from theory import NOTE_NAMES, is_minor
    return f"{NOTE_NAMES[plan.tonic % 12]} {'minor' if is_minor(plan.mode) else 'major'}"


def environment() -> dict:
    root = source()
    return {**os.environ, "ACESTEP_PROJECT_ROOT": root, "HF_HOME": os.path.join(FOLDER, "huggingface"),
            "PYTHONIOENCODING": "utf-8"}


def run(job: dict, folder: str) -> Optional[dict]:
    """Ein Auftrag an ACE-Step; das Ergebnis als dict oder None (Meldung im Log)."""
    path = os.path.join(folder, "auftrag.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"root": source(), **job}, f)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)       # unter Windows ohne schwarzes Fenster
    os.makedirs(FOLDER, exist_ok=True)
    log_path = os.path.join(FOLDER, LOG_FILE)
    try:
        # Die Ausgabe geht in eine Datei, nicht in Pipes: Pipes liest Windows erst zu Ende, wenn jeder Prozess fertig
        # ist, der sie geerbt hat. -P: der Ordner des Workers (die App) gehört nicht auf den Suchpfad von ACE-Step.
        with open(log_path, "w", encoding="utf-8") as output:
            done = subprocess.run([python(), "-P", WORKER, path], cwd=source(), stdin=subprocess.DEVNULL,
                                  stdout=output, stderr=subprocess.STDOUT, timeout=TIMEOUT, env=environment(),
                                  creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Klang-Veredler fehlgeschlagen: %s", e)
        return None
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    line = next((ln for ln in reversed(text.splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        log.warning("Klang-Veredler fehlgeschlagen (ganze Ausgabe in %s): %s", log_path, text.strip()[-800:])
        return None
    try:
        found = json.loads(line[len(MARKER):])
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def _envelope(mono: np.ndarray, rate: int) -> np.ndarray:
    """Einsätze pro Millisekunde: wo die Lautstärke steigt."""
    hop = rate // 1000
    n = len(mono) // hop
    level = np.sqrt(np.mean(np.square(mono[:n * hop]).reshape(n, hop), axis=1) + 1e-12)
    rise = np.maximum(np.diff(np.log(level), prepend=np.log(level[:1])), 0.0)
    return rise - rise.mean()


def offset(reference: np.ndarray, moved: np.ndarray, rate: int) -> int:
    """Um so viele Samples liegt moved später als reference (negativ: früher), höchstens MAX_SHIFT."""
    from scipy.signal import correlate
    a, b = _envelope(reference, rate), _envelope(moved, rate)
    n = min(len(a), len(b))
    if n < 10:
        return 0
    lags = int(MAX_SHIFT * 1000)
    full = correlate(b[:n], a[:n], mode="full", method="fft")
    middle = n - 1
    window = full[max(0, middle - lags):middle + lags + 1]
    best = int(np.argmax(window)) - min(lags, middle)
    return best * (rate // 1000)


def fit(raw: str, reference: str, target: str) -> Optional[str]:
    """Die neue Band auf Abtastrate, Länge und Lage der Vorlage bringen."""
    try:
        data, rate = sf.read(raw, dtype="float32", always_2d=True)
        ref, ref_rate = sf.read(reference, dtype="float32", always_2d=True)
    except (RuntimeError, OSError) as e:
        log.warning("Klang-Veredler: Ergebnis nicht lesbar (%s)", e)
        return None
    if rate != ref_rate:
        from math import gcd

        from scipy.signal import resample_poly
        g = gcd(rate, ref_rate)
        data = resample_poly(data, ref_rate // g, rate // g, axis=0).astype(np.float32)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    shift = offset(ref.mean(axis=1), data.mean(axis=1), ref_rate)
    data = data[shift:] if shift > 0 else np.vstack([np.zeros((-shift, data.shape[1]), np.float32), data])
    out = np.zeros((len(ref), 2), dtype=np.float32)
    out[:min(len(ref), len(data))] = data[:len(ref), :2]
    if abs(shift) > 0:
        log.info("Klang-Veredler: neue Band um %.0f ms verschoben", 1000 * shift / ref_rate)
    sf.write(target, out, ref_rate, subtype="FLOAT")
    return target


def polish(band_wav: str, target: str, settings, plan, seed: int) -> Optional[str]:
    """Die Band (band_wav) veredeln und als target ablegen; None, wenn es nicht geklappt hat."""
    if not available() or not os.path.exists(band_wav):
        return None
    strength = min(max(float(settings.polish_strength), 0.05), 0.95)
    job = {"source": os.path.abspath(band_wav), "caption": caption(settings), "bpm": int(round(plan.bpm)),
           "key": key_scale(plan), "seed": int(seed), "keep": round(1.0 - strength, 3)}
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    folder = tempfile.mkdtemp(prefix="veredler_", dir=os.path.dirname(os.path.abspath(target)))
    try:
        job["folder"] = folder
        log.info("Klang-Veredler: %s (Stärke %.2f, %s)", job["caption"], strength, job["key"])
        found = run(job, folder)
        if not found or not found.get("path") or not os.path.exists(found["path"]):
            return None
        return fit(found["path"], band_wav, target)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
