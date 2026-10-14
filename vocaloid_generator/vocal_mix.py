# vocal_mix.py – der Gesang sitzt vorn, ohne einfach lauter zu werden
#
#   unmask: die Band macht Platz. Wie das Plugin Trackspacer wird die Band in 32 Frequenzbändern genau dort um bis zu
#           3 dB leiser, wo der Gesang gerade laut ist; in den Pausen klingt sie unverändert.
#   ride:   der Gesang reitet auf der Band. Alle 50 ms wird gemessen, wie weit der Gesang über der Band steht; wo er
#           deutlich untergeht oder heraussticht, wird er sanft nachgeführt (höchstens 4 dB). Kleine Unterschiede
#           (der Ausdruck pro Phrase, Strophe leiser als Refrain) bleiben stehen.
# Beides arbeitet auf (2, Samples)-Arrays, wie mixer.mische_spuren sie hält.
import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

UNMASK_DB = 3.0              # höchstens so viel leiser wird die Band, wo der Gesang am lautesten ist
UNMASK_RANGE_DB = 30.0       # ab so weit unter den lautesten Stellen des Gesangs macht die Band Platz
UNMASK_BANDS = 32
UNMASK_LOW, UNMASK_HIGH = 150.0, 8000.0      # Hz: hier liegen Grundton und Verständlichkeit des Gesangs
UNMASK_RELEASE = 0.15        # Sekunden, bis die Band nach einem lauten Ton wieder voll klingt
NFFT = 2048
HOP = 1024                   # halbe Fensterlänge: Hann-Fenster addieren sich wieder zu 1

RIDE_FRAME = 0.05            # Sekunden je Messung
RIDE_SMOOTH = 0.4            # Sekunden, über die Pegel gemittelt werden (Silben zählen nicht einzeln)
RIDE_MAX_DB = 4.0
RIDE_DEAD_DB = 1.5           # so viel darf der Gesang vom üblichen Abstand zur Band abweichen, ohne dass geritten wird
RIDE_GATE_DB = 30.0          # leiser als die lautesten Stellen minus so viel: dort singt niemand


def _db(power: np.ndarray) -> np.ndarray:
    return 10 * np.log10(np.maximum(power, 1e-12))


def _band_edges(rate: int) -> np.ndarray:
    return np.geomspace(UNMASK_LOW * 0.66, min(UNMASK_HIGH * 1.5, rate / 2), UNMASK_BANDS + 1)


def unmask_gain(vocal: np.ndarray, rate: int, depth_db: float = UNMASK_DB) -> tuple:
    """Absenkung der Band (dB, negativ) je Frequenz und STFT-Rahmen: (Frequenzen, Gain [Frequenz, Rahmen])."""
    from scipy.signal import stft
    freqs, _, spec = stft(vocal.mean(axis=0).astype(np.float32), rate, nperseg=NFFT, noverlap=NFFT - HOP)
    power = np.abs(spec) ** 2
    edges = _band_edges(rate)
    centers = np.sqrt(edges[:-1] * edges[1:])
    bands = np.stack([power[(freqs >= a) & (freqs < b)].mean(axis=0) if np.any((freqs >= a) & (freqs < b))
                      else np.zeros(power.shape[1]) for a, b in zip(edges, edges[1:])])
    level = _db(bands)
    top = np.percentile(level, 99.5)
    weight = np.clip((level - (top - UNMASK_RANGE_DB)) / UNMASK_RANGE_DB, 0.0, 1.0)
    # schnell absenken, langsam zurück
    release = np.exp(-HOP / (UNMASK_RELEASE * rate))
    held = np.empty_like(weight)
    current = np.zeros(weight.shape[0])
    for t in range(weight.shape[1]):
        current = np.maximum(weight[:, t], current * release)
        held[:, t] = current
    inside = np.clip(np.minimum(np.log2(centers / UNMASK_LOW), np.log2(UNMASK_HIGH / centers)) + 1.0, 0.0, 1.0)
    band_gain = -depth_db * held * inside[:, None]
    return freqs, (_interpolation(freqs, centers) @ band_gain).astype(np.float32)


def _interpolation(freqs: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Matrix [Frequenz, Band]: linear zwischen den Bandmitten (auf der Oktavskala), außerhalb 0."""
    eye = np.eye(len(centers))
    logf, logc = np.log(np.maximum(freqs, 1.0)), np.log(centers)
    return np.stack([np.interp(logf, logc, eye[b], left=0.0, right=0.0) for b in range(len(centers))], axis=1)


def unmask(band: np.ndarray, vocal: np.ndarray, rate: int, depth_db: float = UNMASK_DB) -> np.ndarray:
    """Die Band (2, n) mit Platz für den Gesang (2, n): leiser in den Frequenzen, in denen er gerade laut ist."""
    from scipy.signal import istft, stft
    if depth_db <= 0 or not np.any(vocal) or not np.any(band):
        return band
    _, gain = unmask_gain(vocal, rate, depth_db)
    scale = 10 ** (gain / 20)
    out = np.empty_like(band)
    for c in range(band.shape[0]):
        _, _, spec = stft(band[c].astype(np.float32), rate, nperseg=NFFT, noverlap=NFFT - HOP)
        frames = min(spec.shape[1], scale.shape[1])
        spec[:, :frames] *= scale[:, :frames]
        _, back = istft(spec, rate, nperseg=NFFT, noverlap=NFFT - HOP)
        n = band.shape[1]
        out[c] = np.pad(back[:n], (0, max(0, n - len(back))))
    return out


def _frame_power(mono: np.ndarray, hop: int, smooth: int) -> np.ndarray:
    frames = len(mono) // hop
    power = (mono[:frames * hop].reshape(frames, hop).astype(np.float64) ** 2).mean(axis=1)
    if smooth > 1 and frames:
        kernel = np.ones(smooth) / smooth
        power = np.convolve(np.pad(power, (smooth // 2, smooth - 1 - smooth // 2), mode="edge"), kernel, "valid")
    return power


def _presence(mono: np.ndarray, rate: int) -> np.ndarray:
    """Nur der Bereich, in dem Gesang und Band sich streiten (300 Hz bis 5 kHz)."""
    from scipy.signal import butter, sosfilt
    sos = butter(2, [300.0, min(5000.0, rate / 2 - 1)], btype="bandpass", fs=rate, output="sos")
    return sosfilt(sos, mono).astype(np.float32)


def ride_gain(vocal: np.ndarray, band: np.ndarray, rate: int, max_db: float = RIDE_MAX_DB) -> np.ndarray:
    """Verstärkung des Gesangs je Sample (linear), damit er gleich weit über der Band steht."""
    n = vocal.shape[1]
    hop = max(1, int(RIDE_FRAME * rate))
    smooth = max(1, int(RIDE_SMOOTH / RIDE_FRAME))
    v = _db(_frame_power(_presence(vocal.mean(axis=0), rate), hop, smooth))
    b = _db(_frame_power(_presence(band.mean(axis=0), rate), hop, smooth))
    if not len(v):
        return np.ones(n, dtype=np.float32)
    active = (v > v.max() - RIDE_GATE_DB) & (b > -100)
    if active.sum() < 4:
        return np.ones(n, dtype=np.float32)
    ratio = v - b
    off = np.median(ratio[active]) - ratio
    correction = np.sign(off) * np.clip(np.abs(off) - RIDE_DEAD_DB, 0.0, max_db)
    idx = np.flatnonzero(active)
    frames_db = np.interp(np.arange(len(v)), idx, correction[idx])
    frames_db = np.convolve(np.pad(frames_db, (smooth // 2, smooth - 1 - smooth // 2), mode="edge"),
                            np.ones(smooth) / smooth, "valid")
    centers = (np.arange(len(v)) + 0.5) * hop
    return (10 ** (np.interp(np.arange(n), centers, frames_db) / 20)).astype(np.float32)


# ── Hall und Delay für den Gesang (D4) ─────────────────────────────────────────
# Statt des Algorithmus-Halls eine Platte aus einer Impulsantwort (pedalboard Convolution). Ohne eigene Datei rechnet
# die App eine Platte aus gefiltertem Rauschen (frei von Lizenzen). Eigene Impulsantworten (WAV, z. B. von OpenAIR;
# die Lizenz jeder Datei selbst prüfen) liegen im Datenordner unter Hall: „platte“ oder „plate“ im Namen ersetzt die
# Gesangsplatte, „raum“, „room“ oder „hall“ den gemeinsamen Hall der Band.
IR_FOLDER = "Hall"
PLATE_T60 = 1.4              # Sekunden, bis die Platte um 60 dB abgeklungen ist
PLATE_GAIN = 1.08            # so laut wie der Algorithmus-Hall vorher (gemessen mit weißem Rauschen)
DUCK_DB = -9.0               # so viel leiser ist das Delay, solange gesungen wird
DUCK_RELEASE = 0.3           # Sekunden, bis das Delay nach dem Gesang wieder voll da ist


def predelay(bpm: float) -> float:
    """Pre-Delay im Tempo: eine Zweiunddreißigstel, zwischen 15 und 80 ms."""
    return float(np.clip(60.0 / max(bpm, 1.0) / 8, 0.015, 0.08))


def synthetic_plate(rate: int, t60: float = PLATE_T60, seed: int = 7) -> np.ndarray:
    """Eine Platte aus Rauschen: dicht von Anfang an, Höhen klingen schneller ab als Mitten. (2, Samples)."""
    from scipy.signal import butter, sosfilt
    n = int(t60 * 1.2 * rate)
    t = np.arange(n) / rate
    rng = np.random.default_rng(seed)
    out = np.empty((2, n), dtype=np.float32)
    lows = butter(2, 2500, btype="lowpass", fs=rate, output="sos")
    highs = butter(2, 2500, btype="highpass", fs=rate, output="sos")
    for c in range(2):
        noise = rng.standard_normal(n)
        body = sosfilt(lows, noise) * np.exp(-6.9 * t / t60)
        air = sosfilt(highs, noise) * np.exp(-6.9 * t / (t60 * 0.55))
        out[c] = body + 0.8 * air
    out[:, :int(0.002 * rate)] *= np.linspace(0, 1, int(0.002 * rate))      # weicher Einsatz
    return out / np.sqrt(np.mean(np.sum(out.astype(np.float64) ** 2, axis=1)))


def user_impulse(kind: str, rate: int) -> Optional[np.ndarray]:
    """Eine eigene Impulsantwort aus dem Ordner Hall (kind: "plate" oder "room"), auf rate, (2, Samples)."""
    import config
    words = {"plate": ("plate", "platte"), "room": ("room", "raum", "hall")}[kind]
    folder = os.path.join(config.DATA_DIR, IR_FOLDER)
    try:
        names = sorted(f for f in os.listdir(folder) if f.lower().endswith((".wav", ".flac", ".aiff", ".aif")))
    except OSError:
        return None
    for name in names:
        if any(w in name.lower() for w in words):
            try:
                return _read_impulse(os.path.join(folder, name), rate)
            except Exception as e:  # noqa: BLE001 – eine kaputte Datei: dann die eingebaute Platte
                log.warning("Impulsantwort %s nicht lesbar: %s", name, e)
    return None


def _read_impulse(path: str, rate: int) -> np.ndarray:
    import soundfile as sf
    from scipy.signal import resample_poly
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    data = data.T[:2]
    if data.shape[0] == 1:
        data = np.vstack([data, data])
    if sr != rate:
        data = resample_poly(data, rate, sr, axis=1).astype(np.float32)
    data = data[:, :int(6 * rate)]
    return data / np.sqrt(np.mean(np.sum(data.astype(np.float64) ** 2, axis=1)) + 1e-12)


def convolve(send: np.ndarray, impulse: np.ndarray, rate: int) -> np.ndarray:
    """send (2, n) durch die Impulsantwort (2, m), links mit links, rechts mit rechts; gleich lang wie send."""
    from scipy.signal import fftconvolve
    n = send.shape[1]
    return np.stack([fftconvolve(send[c], impulse[c % impulse.shape[0]])[:n] for c in range(send.shape[0])]
                    ).astype(np.float32)


def plate(send: np.ndarray, rate: int, bpm: float) -> np.ndarray:
    """Die Gesangsplatte: Pre-Delay im Tempo, Hochpass, Platte (eigene oder eingebaute), Tiefpass."""
    from pedalboard import HighpassFilter, LowpassFilter, Pedalboard
    impulse = user_impulse("plate", rate)
    if impulse is None:
        impulse = synthetic_plate(rate)
    d = int(predelay(bpm) * rate)
    delayed = np.zeros_like(send)
    delayed[:, d:] = send[:, :send.shape[1] - d]
    filtered = Pedalboard([HighpassFilter(350)])(delayed, rate)
    return Pedalboard([LowpassFilter(11000)])(convolve(filtered, impulse, rate) * PLATE_GAIN, rate)


def duck(wet: np.ndarray, vocal: np.ndarray, rate: int, depth_db: float = DUCK_DB) -> np.ndarray:
    """Ein Delay (2, n) leiser, solange der Gesang (2, n) singt; in den Pausen klingt es voll nach."""
    from scipy.signal import lfilter
    level = np.abs(vocal).mean(axis=0)
    hop = max(1, int(0.01 * rate))
    frames = len(level) // hop
    if not frames:
        return wet
    env = level[:frames * hop].reshape(frames, hop).max(axis=1)
    top = np.percentile(env, 95) or 1.0
    singing = np.clip(env / (0.25 * top), 0.0, 1.0)
    release = np.exp(-0.01 / DUCK_RELEASE)
    held = singing.copy()
    for i in range(1, frames):
        held[i] = max(singing[i], held[i - 1] * release)
    gain = 10 ** (depth_db * held / 20)
    gain = lfilter([0.3], [1, -0.7], gain)                    # weich ein- und ausblenden
    curve = np.interp(np.arange(wet.shape[1]), (np.arange(frames) + 0.5) * hop, gain).astype(np.float32)
    return wet * curve[None]
