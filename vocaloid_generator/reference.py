# reference.py – Vorbild-Songs messen: Tempo, Tonart, Klang, Lautstärke-Verlauf und Gesangsanteil
#
# Ein Song kann mehrere Vorbilder haben, jedes mit Gewicht. Gemessen wird mit librosa; das Ergebnis pro Datei
# landet in einem Cache, damit jede Datei nur einmal gemessen wird. Die Vorbilder werden nur gemessen,
# nichts aus ihnen landet im Song.
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

import config

log = logging.getLogger(__name__)

LIBRARY = os.path.join(config.DATA_DIR, "Vorbilder")      # Ordner mit Lieblingssongs zum Anhaken
CACHE = os.path.join(config.DATA_DIR, "vorbild_messungen.json")
AUDIO_TYPES = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".aif")
VERSION = 1                     # neue Messmethode = alter Cache ungültig

RATE = 22050
MAX_SECONDS = 240               # mehr braucht keine Messung
WINDOW = 3.0                    # Sekunden pro Fenster beim Lautstärke-Verlauf
VOCAL_EXCERPT = 30.0            # so viel vom lautesten Teil schätzt den Gesangsanteil
VOCAL_PRESENT_DB = -11.0        # darunter schätzt vocal_ratio_db auch bei Songs ohne Gesang

KEYS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
# Tonart-Profile (Krumhansl-Kessler, Temperley, EDMA); zusammen liegen sie öfter richtig als jedes allein
_PROFILES = (
    ((6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88),
     (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)),
    ((5, 2, 3.5, 2, 4.5, 4, 2, 4.5, 2, 3.5, 1.5, 4),
     (5, 2, 3.5, 4.5, 2, 4, 2, 4.5, 3.5, 2, 1.5, 4)),
    ((0.165, 0.047, 0.083, 0.067, 0.100, 0.093, 0.053, 0.132, 0.052, 0.074, 0.069, 0.064),
     (0.172, 0.040, 0.076, 0.123, 0.051, 0.085, 0.045, 0.121, 0.082, 0.043, 0.079, 0.072)),
)

# Typische Merkmale der Stile, gemessen an den Songs, die die App selbst macht.
# bpm: Bereich; mode: +1 Dur, -1 Moll, 0 beides; bright und drums: 0 bis 1 wie in Analysis
STYLE_TRAITS = {
    "J-Pop Energy": {"bpm": (155, 185), "mode": 0, "bright": 0.55, "drums": 0.6},
    "Dark Vocaloid": {"bpm": (140, 185), "mode": -1, "bright": 0.6, "drums": 0.45},
    "Kawaii Chiptune": {"bpm": (160, 195), "mode": 1, "bright": 0.7, "drums": 0.55},
    "Rock": {"bpm": (120, 160), "mode": 0, "bright": 0.75, "drums": 0.6},
    "Ballade": {"bpm": (60, 92), "mode": 0, "bright": 0.15, "drums": 0.2},
    "City Pop": {"bpm": (95, 125), "mode": 1, "bright": 0.4, "drums": 0.55},
    "Future Bass": {"bpm": (140, 165), "mode": 1, "bright": 0.6, "drums": 0.5},
    "Drum and Bass": {"bpm": (165, 180), "mode": 0, "bright": 0.6, "drums": 0.85},
    "Lo-Fi": {"bpm": (68, 95), "mode": 0, "bright": 0.1, "drums": 0.5},
    "Idol-Pop": {"bpm": (165, 195), "mode": 1, "bright": 0.65, "drums": 0.65},
    "Wafuu-Rock": {"bpm": (150, 185), "mode": -1, "bright": 0.7, "drums": 0.6},
    "Electro-Swing": {"bpm": (115, 132), "mode": 0, "bright": 0.45, "drums": 0.65},
    "Hyperpop": {"bpm": (150, 190), "mode": 1, "bright": 0.85, "drums": 0.7},
}


@dataclass
class Analysis:
    """Messung eines Vorbilds."""
    path: str
    seconds: float
    bpm: float
    key: str
    scale: str                  # "major" oder "minor"
    key_scores: list            # 24 Werte: Dur auf C..B, dann Moll auf C..B
    brightness: float           # 0 dunkel bis 1 hell (Schwerpunkt des Spektrums)
    drums: float                # 0 bis 1: wie viel Schlagzeug und Perkussion
    contrast_db: float          # laute Stellen minus leise Stellen
    vocal_db: float             # geschätzter Gesang minus Band (nur im Vergleich mit derselben Schätzung sinnvoll)


@dataclass
class Summary:
    """Alle aktiven Vorbilder zusammen, nach Gewicht."""
    bpm: int
    key: str
    scale: str
    style: str
    contrast_db: float
    vocal_db: Optional[float]   # None: kein Vorbild mit erkennbarem Gesang
    names: list

    def describe(self) -> str:
        return f"{self.bpm} BPM, {self.key} {'Dur' if self.scale == 'major' else 'Moll'}, klingt nach {self.style}"


# ── Bibliothek ───────────────────────────────────────────────────────────────────
def library_files(folder: str = "") -> list:
    """Alle Audiodateien im Vorbild-Ordner, nach Namen sortiert."""
    folder = folder or LIBRARY
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(AUDIO_TYPES) and not f.startswith("."))


def active(refs) -> list:
    """[(Pfad, Gewicht)] der eingeschalteten Vorbilder, die es gibt."""
    out = []
    for ref in refs or ():
        if not ref.enabled or ref.weight <= 0:
            continue
        if os.path.exists(ref.path):
            out.append((ref.path, float(ref.weight)))
        else:
            log.warning("Vorbild-Song nicht gefunden: %s", ref.path)
    return out


# ── Messen ───────────────────────────────────────────────────────────────────────
def analyse(path: str, use_cache: bool = True) -> Analysis:
    """Misst ein Vorbild; bekannte Dateien kommen aus dem Cache."""
    key = _cache_key(path)
    cache = _read_cache() if use_cache else {}
    if key in cache:
        return Analysis(**cache[key])
    import librosa
    y, _ = librosa.load(path, sr=RATE, mono=True, duration=MAX_SECONDS)
    if len(y) < RATE * 5:
        raise ValueError(f"{os.path.basename(path)} ist zu kurz für eine Messung")
    drums = _drum_share(y)
    scores = _key_scores(y)
    best = int(np.argmax(scores))
    result = Analysis(
        path=os.path.abspath(path), seconds=round(len(y) / RATE, 1), bpm=round(_tempo(y, drums), 1),
        key=KEYS[best % 12], scale="major" if best < 12 else "minor", key_scores=[round(float(v), 4) for v in scores],
        brightness=round(_brightness(y), 3), drums=round(drums, 3), contrast_db=round(contrast_db(y, RATE), 2),
        vocal_db=round(vocal_ratio_db(y, RATE), 2),
    )
    if use_cache:
        cache[key] = asdict(result)
        _write_cache(cache)
    log.info("Vorbild gemessen: %s: %.0f BPM, %s %s", os.path.basename(path), result.bpm, result.key, result.scale)
    return result


def summarize(refs, styles=None) -> Optional[Summary]:
    """Die Vorbilder zusammen: Tempo, Tonart und Stil nach Gewicht. None ohne messbares Vorbild."""
    measured = []
    for path, weight in active(refs):
        try:
            measured.append((analyse(path), weight))
        except Exception as e:
            log.warning("Vorbild %s nicht messbar: %s", os.path.basename(path), e)
    if not measured:
        return None
    total = sum(w for _, w in measured)
    mean = lambda attr: sum(getattr(a, attr) * w for a, w in measured) / total  # noqa: E731
    key, scale = _combine_keys(measured)
    bpm = _combine_tempi([(a.bpm, w) for a, w in measured])
    style = suggest_style(bpm, scale, mean("brightness"), mean("drums"), styles)
    sung = [(a.vocal_db, w) for a, w in measured if a.vocal_db > VOCAL_PRESENT_DB]
    vocal_db = round(sum(v * w for v, w in sung) / sum(w for _, w in sung), 2) if sung else None
    return Summary(bpm=int(round(bpm)), key=key, scale=scale, style=style, contrast_db=round(mean("contrast_db"), 2),
                   vocal_db=vocal_db, names=[os.path.basename(a.path) for a, _ in measured])


def suggest_style(bpm: float, scale: str, brightness: float, drums: float, styles=None) -> str:
    """Der Stil, dessen typische Merkmale am besten passen."""
    names = [n for n in (styles or STYLE_TRAITS) if n in STYLE_TRAITS]

    def cost(name: str) -> float:
        t = STYLE_TRAITS[name]
        lo, hi = t["bpm"]
        # halbes oder doppeltes Tempo zählt fast so gut: Messungen verwechseln das oft
        miss = min(_outside(bpm, lo, hi), _outside(bpm * 2, lo, hi) + 8, _outside(bpm / 2, lo, hi) + 8)
        mode = 0.0 if t["mode"] == 0 else (0.0 if (t["mode"] > 0) == (scale == "major") else 0.6)
        return miss / 15 + 2 * abs(brightness - t["bright"]) + 2 * abs(drums - t["drums"]) + mode

    return min(names, key=cost)


def contrast_db(y: np.ndarray, rate: int) -> float:
    """Wie weit laute und leise Stellen auseinanderliegen: 90. minus 25. Perzentil der Fenster-Pegel in dB."""
    levels = _window_levels(y, rate)
    if len(levels) < 4:
        return 0.0
    return float(np.percentile(levels, 90) - np.percentile(levels, 25))


def vocal_ratio_db(y: np.ndarray, rate: int) -> float:
    """
    Gesang gegen Band in dB, geschätzt im lautesten Abschnitt: Was sich im Spektrum wiederholt, ist Band,
    der Rest Gesang (REPET-SIM aus der librosa-Dokumentation). Die Schätzung ist grob; verglichen werden
    deshalb immer zwei Signale mit derselben Schätzung.
    """
    import librosa
    y = _loudest(y, rate, VOCAL_EXCERPT)
    spec, _ = librosa.magphase(librosa.stft(y, n_fft=2048, hop_length=512))
    width = int(librosa.time_to_frames(2.0, sr=rate, hop_length=512))
    if spec.shape[1] <= 2 * width:
        return 0.0
    band = np.minimum(spec, librosa.decompose.nn_filter(spec, aggregate=np.median, metric="cosine", width=width))
    voice_mask = librosa.util.softmask(spec - band, 10 * band, power=2)
    band_mask = librosa.util.softmask(band, 2 * (spec - band), power=2)
    freqs = librosa.fft_frequencies(sr=rate, n_fft=2048)
    sel = (freqs > 150) & (freqs < 6000)
    voice = float(np.sum((voice_mask * spec)[sel] ** 2))
    rest = float(np.sum((band_mask * spec)[sel] ** 2))
    return 10 * np.log10((voice + 1e-12) / (rest + 1e-12))


# ── Mastering nach mehreren Vorbildern ───────────────────────────────────────────
def mastering_reference(refs, folder: str = None) -> Optional[str]:
    """
    Eine Datei, nach der matchering mastert. Ein Vorbild: die Datei selbst. Mehrere: ein Zusammenschnitt der
    lautesten Stellen, jedes Vorbild auf dieselbe Lautheit gebracht und so lang, wie sein Gewicht es will;
    der Klang liegt dann im Mittel der Vorbilder.
    """
    chosen = active(refs)
    if not chosen:
        return None
    if len(chosen) == 1:
        return chosen[0][0]
    import librosa
    import soundfile as sf
    from mixer import SAMPLE_RATE, _loudness
    heaviest = max(w for _, w in chosen)
    pieces, levels = [], []
    for path, weight in chosen:
        try:
            audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=False, duration=MAX_SECONDS)
        except Exception as e:
            log.warning("Vorbild %s nicht lesbar: %s", os.path.basename(path), e)
            continue
        audio = np.atleast_2d(audio)
        if audio.shape[0] == 1:
            audio = np.vstack([audio, audio])
        seconds = max(10.0, 60.0 * weight / heaviest)
        start = _loudest_start(audio.mean(axis=0), SAMPLE_RATE, seconds)
        piece = audio[:, start:start + int(seconds * SAMPLE_RATE)].astype(np.float32)
        loud = _loudness(piece)
        if loud == float("-inf"):
            continue
        pieces.append(piece)
        levels.append((loud, weight))
    if not pieces:
        return None
    if len(pieces) == 1:
        return chosen[0][0]
    target = sum(l * w for l, w in levels) / sum(w for _, w in levels)
    mixed = np.concatenate([p * 10 ** ((target - l) / 20) for p, (l, _) in zip(pieces, levels)], axis=1)
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.99:
        mixed *= 0.99 / peak
    folder = folder or tempfile.mkdtemp(prefix="vorbild_")
    path = os.path.join(folder, "vorbilder_zusammen.wav")
    sf.write(path, mixed.T, SAMPLE_RATE, subtype="FLOAT")
    log.info("Mastering nach %d Vorbildern", len(pieces))
    return path


# ── Hilfen ───────────────────────────────────────────────────────────────────────
def _tempo(y: np.ndarray, drums: float) -> float:
    import librosa
    onsets = librosa.onset.onset_strength(y=y, sr=RATE)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onsets, sr=RATE, start_bpm=140, units="time")
    bpm = float(np.atleast_1d(tempo)[0])
    if len(beats) > 8:
        bpm = 60.0 / float(np.median(np.diff(beats)))      # genauer als das Tempo-Raster von beat_track
    while bpm < 60:
        bpm *= 2
    while bpm > 200:
        bpm /= 2
    if drums < 0.3 and bpm > 130:                            # ruhige Songs mit wenig Schlagzeug: halbes Tempo
        bpm /= 2
    return bpm


def _combine_keys(measured: list) -> tuple:
    """Die Tonart, auf die das meiste Gewicht fällt; bei Gleichstand entscheidet die Passung aller Vorbilder."""
    votes = {}
    for a, weight in measured:
        votes[(a.key, a.scale)] = votes.get((a.key, a.scale), 0.0) + weight
    best = max(votes.values())
    tied = [k for k, v in votes.items() if v >= best - 1e-9]
    if len(tied) == 1:
        return tied[0]
    scores = sum(np.asarray(a.key_scores) * w for a, w in measured)
    return max(tied, key=lambda k: scores[KEYS.index(k[0]) + (0 if k[1] == "major" else 12)])


def _combine_tempi(tempi: list) -> float:
    """Gewichtetes Mittel; Tempi, die halb oder doppelt so schnell sind wie das wichtigste, werden angeglichen."""
    anchor = max(tempi, key=lambda t: t[1])[0]
    folded = []
    for bpm, weight in tempi:
        bpm = min((bpm, bpm * 2, bpm / 2), key=lambda b: abs(np.log2(b / anchor)))
        folded.append((bpm, weight))
    return sum(b * w for b, w in folded) / sum(w for _, w in folded)


def _key_scores(y: np.ndarray) -> np.ndarray:
    """Passung auf alle 24 Tonarten; gemessen ohne das letzte Drittel, wo oft die Tonart wechselt."""
    import librosa
    part = y[int(len(y) * 0.05):int(len(y) * 0.65)]
    chroma = librosa.feature.chroma_stft(y=part, sr=RATE, n_fft=8192, hop_length=4096).mean(axis=1)
    scores = np.zeros(24)
    for major, minor in _PROFILES:
        for mode, profile in enumerate((major, minor)):
            for k in range(12):
                scores[mode * 12 + k] += np.corrcoef(np.roll(profile, k), chroma)[0, 1]
    return scores / len(_PROFILES)


def _drum_share(y: np.ndarray) -> float:
    """Anteil der perkussiven Energie (HPSS), auf 0 bis 1 gestreckt: 0,3 ist schon sehr viel Schlagzeug."""
    import librosa
    spec = np.abs(librosa.stft(_middle(y, 60.0), n_fft=2048, hop_length=1024))
    harmonic, percussive = librosa.decompose.hpss(spec)
    share = float(np.sum(percussive ** 2) / (np.sum(harmonic ** 2) + np.sum(percussive ** 2) + 1e-12))
    return float(np.clip(share / 0.3, 0.0, 1.0))


def _brightness(y: np.ndarray) -> float:
    """Schwerpunkt des Spektrums, nach Lautstärke gewichtet: 1200 Hz = 0, 3000 Hz = 1."""
    import librosa
    spec = np.abs(librosa.stft(_middle(y, 60.0), n_fft=2048, hop_length=1024))
    centroid = librosa.feature.spectral_centroid(S=spec, sr=RATE)[0]
    rms = librosa.feature.rms(S=spec, frame_length=2048)[0]
    hz = float(np.sum(centroid * rms) / (np.sum(rms) + 1e-12))
    return float(np.clip((hz - 1200) / 1800, 0.0, 1.0))


def _window_levels(y: np.ndarray, rate: int) -> np.ndarray:
    """Pegel in dB pro WINDOW Sekunden; Stille (Anfang, Ende, Pausen) zählt nicht mit."""
    n = int(WINDOW * rate)
    if len(y) < n:
        return np.array([])
    frames = y[:len(y) // n * n].reshape(-1, n)
    levels = 10 * np.log10(np.mean(frames ** 2, axis=1) + 1e-12)
    return levels[levels > levels.max() - 30]


def _loudest_start(y: np.ndarray, rate: int, seconds: float) -> int:
    """Start (Sample) der lautesten seconds Sekunden, auf ganze Sekunden genau."""
    per_second = np.square(y[:len(y) // rate * rate]).reshape(-1, rate).sum(axis=1)
    window = max(int(seconds), 1)
    if len(per_second) <= window:
        return 0
    return int(np.argmax(np.convolve(per_second, np.ones(window), mode="valid"))) * rate


def _loudest(y: np.ndarray, rate: int, seconds: float) -> np.ndarray:
    start = _loudest_start(y, rate, seconds)
    return y[start:start + int(seconds * rate)]


def _middle(y: np.ndarray, seconds: float) -> np.ndarray:
    n = int(seconds * RATE)
    if len(y) <= n:
        return y
    start = (len(y) - n) // 2
    return y[start:start + n]


def _outside(value: float, lo: float, hi: float) -> float:
    return max(lo - value, 0.0, value - hi)


def _cache_key(path: str) -> str:
    stat = os.stat(path)
    return f"{VERSION}|{os.path.abspath(path)}|{stat.st_size}|{stat.st_mtime_ns}"


def _read_cache() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict) -> None:
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except OSError as e:
        log.warning("Vorbild-Messungen nicht gespeichert: %s", e)
