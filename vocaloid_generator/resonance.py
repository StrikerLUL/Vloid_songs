# resonance.py – Härte zähmen: ein dynamischer Resonanz-Filter für den Gesang (1.3.0, G2)
#
# Der EQ des Gesangs ist fest eingestellt (vocal_tone.py). Hohe, laute Töne werden bei vielen Stimmen aber von selbst
# schrill: einzelne Bereiche zwischen 1,5 und 10 kHz stechen dann heraus. Wie das Plugin soothe2 senkt dieser Filter
# nur die Frequenzen, die gerade herausstechen, und nur so lange: Das Spektrum jedes kurzen Abschnitts wird etwas
# geglättet (so zählen einzelne Obertöne nicht) und mit seiner breiten Hüllkurve verglichen; was mehr als THRESHOLD_DB
# darüber liegt, wird leiser, höchstens um MAX_CUT_DB. Leise Stellen und der Rest des Spektrums bleiben, wie sie sind.
import numpy as np
from scipy.ndimage import convolve1d

FRAME, HOP = 2048, 512
# Glättung: über die Obertöne hinweg (auch bei hohen Tönen bis 900 Hz Abstand), und die breite Hüllkurve
LOCAL_OCTAVE, LOCAL_HZ = 1 / 3, 900.0
BROAD_OCTAVE, BROAD_HZ = 1.0, 3000.0
BAND = (1500.0, 10000.0)                    # hier wird gezähmt (mit weichen Rändern)
THRESHOLD_DB = 3.0                          # so weit darf ein Bereich herausstechen
SLOPE = 0.7                                 # jedes dB darüber senkt um so viel
MAX_CUT_DB = 6.0                            # höchstens so viel leiser (0 = aus)
GATE_DB = 30.0                              # Abschnitte, die so viel leiser als der lauteste sind, bleiben
RELEASE_SECONDS = 0.08                      # so schnell lässt der Filter wieder los
CHUNK = 1024                                # Abschnitte pro Rechenschritt (hält den Speicher klein)


def _ranges(bins: int, rate: int, octave: float, min_hz: float) -> tuple:
    """Für jedes Frequenzband die Grenzen (von, bis) eines Fensters von octave Oktaven, aber mindestens min_hz Breite."""
    k = np.arange(bins, dtype=np.float64)
    factor = 2 ** (octave / 2)
    half = np.maximum(k * (factor - 1 / factor) / 2, min_hz / 2 * FRAME / rate)
    lo = np.clip(np.floor(k - half), 0, bins - 1).astype(int)
    hi = np.clip(np.ceil(k + half) + 1, 1, bins).astype(int)
    hi = np.maximum(hi, lo + 1)
    return lo, hi


def _smooth(values: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Mittelwert jedes Bands über sein Fenster (values: Abschnitte × Bänder)."""
    values = values.astype(np.float64)
    cs = np.concatenate([np.zeros((values.shape[0], 1)), np.cumsum(values, axis=1)], axis=1)
    return ((cs[:, hi] - cs[:, lo]) / (hi - lo)).astype(np.float32)


def _band_weight(bins: int, rate: int) -> np.ndarray:
    freqs = np.arange(bins) * rate / FRAME
    lo, hi = BAND
    rise = np.clip((freqs - lo * 0.7) / (lo * 0.3), 0, 1)
    fall = np.clip((hi * 1.25 - freqs) / (hi * 0.25), 0, 1)
    return (rise * fall).astype(np.float32)


def tame(audio: np.ndarray, rate: int, max_cut_db: float = None) -> np.ndarray:
    """Der Gesang (Kanäle × Samples) mit gezähmten Resonanzen; gleich lang. Rückgabe ohne Änderung, wenn MAX_CUT_DB
    0 ist oder es nichts zu tun gibt."""
    max_cut = MAX_CUT_DB if max_cut_db is None else max_cut_db
    if max_cut <= 0 or audio.size == 0:
        return audio
    channels = np.atleast_2d(audio).astype(np.float32)
    n = channels.shape[1]
    pad = FRAME // 2
    padded = np.pad(channels, ((0, 0), (pad, pad + FRAME)))
    mono = padded.mean(axis=0)
    frames = 1 + (padded.shape[1] - FRAME) // HOP
    window = np.hanning(FRAME + 1)[:-1].astype(np.float32)
    bins = FRAME // 2 + 1
    local = _ranges(bins, rate, LOCAL_OCTAVE, LOCAL_HZ)
    broad = _ranges(bins, rate, BROAD_OCTAVE, BROAD_HZ)
    weight = _band_weight(bins, rate)
    view = np.lib.stride_tricks.sliding_window_view
    mono_frames = view(mono, FRAME)[::HOP][:frames]
    energy = np.concatenate([[0.0], np.cumsum(mono.astype(np.float64) ** 2)])
    starts = np.arange(frames) * HOP
    levels = 10 * np.log10((energy[starts + FRAME] - energy[starts]) / FRAME + 1e-12)
    loudest = levels.max() if len(levels) else -120.0
    release = float(np.exp(-HOP / (rate * RELEASE_SECONDS)))
    out = np.zeros_like(padded)
    norm = np.zeros(padded.shape[1], dtype=np.float32)
    chan_frames = [view(c, FRAME)[::HOP][:frames] for c in padded]
    held = np.zeros(bins, dtype=np.float32)
    total_cut = 0.0
    for begin in range(0, frames, CHUNK):
        end = min(begin + CHUNK, frames)
        spec = np.fft.rfft(mono_frames[begin:end] * window, axis=1)
        power = (spec.real ** 2 + spec.imag ** 2).astype(np.float32) + 1e-12
        local_db = 10 * np.log10(np.maximum(_smooth(power, *local), 1e-12))
        broad_db = _smooth(local_db, *broad)
        excess = local_db - broad_db
        cut = np.clip((excess - THRESHOLD_DB) * SLOPE, 0.0, max_cut) * weight
        cut[levels[begin:end] < loudest - GATE_DB] = 0.0
        cut = convolve1d(cut, np.array((0.25, 0.5, 0.25), dtype=np.float32), axis=1, mode="nearest")
        for i in range(cut.shape[0]):              # sofort greifen, langsam loslassen
            held = np.maximum(cut[i], held * release)
            cut[i] = held
        total_cut += float(cut.sum())
        gain = (10 ** (-cut / 20)).astype(np.float32)
        for c, fr in enumerate(chan_frames):
            spectrum = np.fft.rfft(fr[begin:end] * window, axis=1) * gain
            pieces = np.fft.irfft(spectrum, n=FRAME, axis=1).astype(np.float32) * window
            for i in range(pieces.shape[0]):
                at = (begin + i) * HOP
                out[c, at:at + FRAME] += pieces[i]
        for i in range(end - begin):
            at = (begin + i) * HOP
            norm[at:at + FRAME] += window ** 2
    if total_cut == 0.0:
        return audio
    out /= np.maximum(norm, 1e-6)
    result = out[:, pad:pad + n]
    return result.reshape(audio.shape).astype(audio.dtype)
