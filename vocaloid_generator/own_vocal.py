# own_vocal.py – eigene Gesangsspur einsetzen (Gesang 1.1, E1)
#
# Eine WAV, die woanders gesungen oder bearbeitet wurde (NEUTRINO-Tuning-Tool, VoiSona, eine eigene Aufnahme),
# ersetzt die Hauptstimme. Die Begleitstimmen singt weiter die Engine, gemischt wird die Spur wie die eigene.
# Wo die Spur anfängt, ist oft unklar: die exportierte MusicXML hat einen Takt Vorlauf, andere Programme fangen
# beim ersten Ton an. Deshalb wird die Spur an den Noten ausgerichtet: ihre Lautstärke gegen die Stellen, an denen
# die Melodie singt, verschoben um bis zu ALIGN_BARS Takte in beide Richtungen.
import logging
import os

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

RATE = 48000
HOP = 0.01                 # Sekunden je Lautstärkewert
ALIGN_BARS = 2             # so weit wird höchstens verschoben
BEATS_PER_BAR = 4


def available(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def load(path: str, rate: int = RATE) -> np.ndarray:
    """Die Spur als Mono in rate; andere Abtastraten werden umgerechnet."""
    audio, sr = sf.read(path, dtype="float64", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != rate:
        from math import gcd

        from scipy.signal import resample_poly
        g = gcd(int(sr), rate)
        mono = resample_poly(mono, rate // g, int(sr) // g)
    return mono


def _envelope(audio: np.ndarray, rate: int) -> np.ndarray:
    hop = int(HOP * rate)
    n = len(audio) // hop
    if n == 0:
        return np.zeros(0)
    rms = np.sqrt(np.mean(audio[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    floor = np.percentile(db, 10)
    return np.clip(db - floor - 6.0, 0.0, 40.0) / 40.0       # leise Reste und Rauschen zählen nicht


def _mask(notes: list, frames: int) -> np.ndarray:
    mask = np.zeros(frames)
    for n in notes:
        a, b = int(n.start / HOP), int(n.end / HOP)
        mask[max(0, a):max(0, min(frames, b))] = 1.0
    return mask


def offset(audio: np.ndarray, rate: int, notes: list, bpm: float) -> float:
    """Sekunden, um die die Spur zu spät anfängt (positiv: vorn abschneiden, negativ: Stille davor)."""
    env = _envelope(audio, rate)
    if not len(env) or not notes:
        return 0.0
    reach = int(ALIGN_BARS * BEATS_PER_BAR * 60.0 / bpm / HOP)
    length = max(len(env), int(max(n.end for n in notes) / HOP)) + 2 * reach
    mask = _mask(notes, length)
    mask = mask - mask.mean()
    best, best_lag = -np.inf, 0
    for lag in range(-reach, reach + 1):
        # die Spur um lag Rahmen nach vorn geschoben: env[i + lag] gehört zur Songzeit i
        lo = max(0, -lag)
        hi = min(length, len(env) - lag)
        if hi <= lo:
            continue
        score = float(np.dot(env[lo + lag:hi + lag], mask[lo:hi]))
        if score > best + 1e-9 or (abs(score - best) <= 1e-9 and abs(lag) < abs(best_lag)):
            best, best_lag = score, lag
    return best_lag * HOP


def place(path: str, notes: list, bpm: float, out: str, align: bool = True) -> float:
    """Schreibt die eigene Spur als out (48 kHz, Mono), ausgerichtet an den Noten (voice_fx.timeline).
    Rückgabe: die Verschiebung in Sekunden (0 ohne align)."""
    audio = load(path)
    shift = offset(audio, RATE, notes, bpm) if align else 0.0
    cut = int(round(shift * RATE))
    audio = audio[cut:] if cut >= 0 else np.concatenate([np.zeros(-cut), audio])
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0.99:
        audio = audio * (0.99 / peak)
    sf.write(out, audio.astype(np.float32), RATE, subtype="FLOAT")
    if abs(shift) >= HOP:
        log.info("Eigene Gesangsspur %s: um %.2f s %s ausgerichtet", os.path.basename(path), abs(shift),
                 "nach vorn" if shift > 0 else "nach hinten")
    return shift
