# separation.py – Mix pro Instrument wie die Vorbilder: Gesang, Schlagzeug, Bass und Rest einzeln angleichen
#
# Demucs (Meta, MIT) zerlegt den lautesten Abschnitt jedes Vorbilds in vier Gruppen. Gemessen wird, wie laut jede
# Gruppe gegen den ganzen Song ist und wie hell sie klingt (Höhen gegen Mitten). Der Mixer bringt dieselben Gruppen
# des eigenen Songs dorthin (mixer._match_groups), um höchstens ein paar dB, damit nichts kippt. Demucs läuft in
# einer eigenen Umgebung (setup_demucs.py, tools/demucs) wie die Bewertung; ohne sie bleibt alles wie bisher.
# Messungen landen in einem Cache, jedes Vorbild wird nur einmal zerlegt.
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Optional

import numpy as np

import cancel
import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "demucs")
WORKER = os.path.join(config.BASE_DIR, "separation_worker.py")
MARKER = "ZERLEGT "
CACHE = os.path.join(config.DATA_DIR, "vorbild_gruppen.json")
VERSION = 2                     # 2: der Gesang bekommt seine Kurve in Terzbändern dazu ("bands")
GROUPS = ("vocals", "drums", "bass", "other")
NAMES = {"vocals": "Gesang", "drums": "Schlagzeug", "bass": "Bass", "other": "Rest"}
RATE = 44100
EXCERPT_SECONDS = 45.0          # so viel vom lautesten Abschnitt (meist der Refrain) wird zerlegt
SILENT_DB = -30.0               # leiser gegen den ganzen Song: die Gruppe fehlt im Vorbild
SPLIT_HZ = (300.0, 4000.0)      # Helligkeit: Energie über 4 kHz gegen 300 Hz bis 4 kHz
TIMEOUT = 1800


def python() -> str:
    """Python der eigenen Umgebung."""
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def status() -> str:
    if not available():
        return "Demucs fehlt: unter Hilfe › Einrichten „Mix wie die Vorbilder“ laden"
    return "Demucs ist eingerichtet: der Mix gleicht Gesang, Schlagzeug, Bass und Rest einzeln an die Vorbilder an"


def environment() -> dict:
    """Das Modell liegt mit in tools/demucs, nicht irgendwo im Profil."""
    return {**os.environ, "TORCH_HOME": os.path.join(FOLDER, "torch"), "PYTHONIOENCODING": "utf-8"}


def _command(pairs: list) -> list:
    return [python(), WORKER, *[x for pair in pairs for x in pair]]


def separate(sources: list, folders: list) -> list:
    """Zerlegt jede Datei in ihren Ordner (vocals.wav, drums.wav, bass.wav, other.wav). Gibt die fertigen Ordner
    zurück; ohne Demucs oder bei Fehlern eine leere Liste."""
    if not sources or not available():
        return []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        done = cancel.run(_command(list(zip(sources, folders))), capture_output=True, timeout=TIMEOUT,
                          env=environment(), encoding="utf-8", errors="replace", creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Demucs fehlgeschlagen: %s", e)
        return []
    line = next((ln for ln in reversed(done.stdout.splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        log.warning("Demucs fehlgeschlagen: %s", (done.stderr or done.stdout).strip()[-800:])
        return []
    try:
        found = json.loads(line[len(MARKER):])
    except ValueError:
        return []
    log.info("Demucs lief auf %s", "der Grafikkarte" if found.get("device") == "cuda" else "dem Prozessor")
    return [f for f in found.get("done", []) if all(os.path.isfile(os.path.join(f, g + ".wav")) for g in GROUPS)]


# ── Messen ───────────────────────────────────────────────────────────────────────
def tilt_db(audio: np.ndarray, rate: int = RATE) -> float:
    """Wie hell: Energie über 4 kHz gegen 300 Hz bis 4 kHz, in dB (audio: Kanäle × Samples oder mono)."""
    mono = audio.mean(axis=0) if audio.ndim == 2 else audio
    if len(mono) < 2048:
        return 0.0
    frames = mono[:len(mono) // 2048 * 2048].reshape(-1, 2048) * np.hanning(2048)
    power = np.square(np.abs(np.fft.rfft(frames, axis=1))).sum(axis=0)
    freqs = np.fft.rfftfreq(2048, 1.0 / rate)
    mids = power[(freqs >= SPLIT_HZ[0]) & (freqs < SPLIT_HZ[1])].sum()
    highs = power[freqs >= SPLIT_HZ[1]].sum()
    return float(10 * np.log10((highs + 1e-12) / (mids + 1e-12)))


# Terzbänder für die Klangkurve des Gesangs (D3): Mitten von 125 Hz bis 10 kHz
BAND_CENTERS = tuple(round(1000 * 2 ** (k / 3), 1) for k in range(-9, 11))


def bands_db(audio: np.ndarray, rate: int = RATE) -> list:
    """Die Klangkurve: Pegel je Terzband in dB, um den Mittelwert verschoben (nur die Form zählt)."""
    mono = audio.mean(axis=0) if audio.ndim == 2 else audio
    if len(mono) < 4096:
        return [0.0] * len(BAND_CENTERS)
    frames = mono[:len(mono) // 4096 * 4096].reshape(-1, 4096) * np.hanning(4096)
    power = np.square(np.abs(np.fft.rfft(frames, axis=1))).sum(axis=0)
    freqs = np.fft.rfftfreq(4096, 1.0 / rate)
    out = []
    for center in BAND_CENTERS:
        sel = (freqs >= center / 2 ** (1 / 6)) & (freqs < center * 2 ** (1 / 6))
        out.append(float(10 * np.log10(power[sel].sum() + 1e-12)))
    mean = float(np.mean(out))
    return [round(v - mean, 2) for v in out]


def measure(groups: dict) -> dict:
    """{Gruppe: Audio (Kanäle × Samples)} → {Gruppe: {"level": dB gegen alle zusammen, "tilt": dB}}; stille
    Gruppen fehlen."""
    from mixer import _loudness
    total = _loudness(sum(groups.values()))
    if total == float("-inf"):
        return {}
    out = {}
    for name, audio in groups.items():
        level = _loudness(audio) - total
        if level > SILENT_DB:
            out[name] = {"level": round(float(level), 2), "tilt": round(tilt_db(audio), 2)}
            if name == "vocals":
                out[name]["bands"] = bands_db(audio)
    return out


def _excerpt(path: str, target: str) -> str:
    """Der lauteste Abschnitt des Vorbilds als WAV mit 44,1 kHz, Stereo."""
    import librosa
    import soundfile as sf

    from reference import _loudest_start
    audio, _ = librosa.load(path, sr=RATE, mono=False, duration=240)
    audio = np.atleast_2d(audio)
    if audio.shape[0] == 1:
        audio = np.repeat(audio, 2, axis=0)
    start = _loudest_start(audio.mean(axis=0), RATE, EXCERPT_SECONDS)
    sf.write(target, audio[:2, start:start + int(EXCERPT_SECONDS * RATE)].T, RATE, subtype="FLOAT")
    return target


def profiles(paths: list) -> dict:
    """{Pfad: Messung} für alle Vorbilder; fehlende werden in einem Durchgang zerlegt und gemessen."""
    import soundfile as sf

    from reference import _cache_key
    cache = _read_cache()
    keys = {path: f"{VERSION}|{_cache_key(path)}" for path in paths}
    todo = [path for path in paths if keys[path] not in cache]
    if todo and available():
        with tempfile.TemporaryDirectory() as temp:
            readable = []                   # (Pfad, Ausschnitt, Ordner) der lesbaren Vorbilder
            for i, path in enumerate(todo):
                try:
                    readable.append((path, _excerpt(path, os.path.join(temp, f"{i}.wav")), os.path.join(temp, str(i))))
                except Exception as e:  # noqa: BLE001 – ein unlesbares Vorbild zählt einfach nicht mit
                    log.warning("Vorbild %s nicht lesbar: %s", os.path.basename(path), e)
            log.info("Zerlege %d Vorbild(er) mit Demucs ...", len(readable))
            finished = set(separate([r[1] for r in readable], [r[2] for r in readable]))
            for path, _, folder in readable:
                if folder not in finished:
                    continue
                groups = {g: sf.read(os.path.join(folder, g + ".wav"), dtype="float32", always_2d=True)[0].T
                          for g in GROUPS}
                cache[keys[path]] = measure(groups)
                log.info("Vorbild zerlegt: %s: %s", os.path.basename(path), describe(cache[keys[path]]))
        _write_cache(cache)
    return {path: cache[keys[path]] for path in paths if keys[path] in cache}


def summarize(refs) -> Optional[dict]:
    """Die eingeschalteten Vorbilder zusammen, nach Gewicht: {Gruppe: {"level", "tilt"}}. None ohne Demucs oder
    ohne zerlegbares Vorbild."""
    import reference
    chosen = reference.active(refs)
    if not chosen or not available():
        return None
    found = profiles([path for path, _ in chosen])
    out = {}
    for group in GROUPS:
        values = [(found[path][group], weight) for path, weight in chosen if group in found.get(path, {})]
        if values:
            total = sum(w for _, w in values)
            out[group] = {k: round(sum(v[k] * w for v, w in values) / total, 2) for k in ("level", "tilt")}
            curves = [(v["bands"], w) for v, w in values if len(v.get("bands") or []) == len(BAND_CENTERS)]
            if curves:
                weight = sum(w for _, w in curves)
                out[group]["bands"] = [round(sum(c[k] * w for c, w in curves) / weight, 2)
                                       for k in range(len(BAND_CENTERS))]
    return out or None


def describe(measured: dict) -> str:
    return ", ".join(f"{NAMES[g]} {m['level']:+.1f} dB" for g, m in measured.items()) or "nichts hörbar"


def _read_cache() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict) -> None:
    try:
        with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
        os.replace(CACHE + ".tmp", CACHE)
    except OSError as e:
        log.warning("Vorbild-Gruppen nicht gespeichert: %s", e)

