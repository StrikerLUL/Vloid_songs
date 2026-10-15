# fx.py – Übergangs-Effekte wie in Pop-Produktionen: Riser, Becken-Swell, Impact und Downlifter
#
# Die Geräusche entstehen aus Rauschen, dessen Spektrum sich über die Zeit verschiebt (STFT), und aus
# einem tiefen Sinus für den Impact. Alles wird an den Bauplan gehängt: Riser enden genau auf der Eins
# des Refrains, Impacts und Downlifter beginnen dort.
import numpy as np
from scipy.signal import istft

from song_plan import SongPlan

SAMPLE_RATE = 44100
TAIL_SECONDS = 2.5
_NPERSEG = 2048


def _shaped_noise(seconds: float, rng: np.random.Generator, center_hz, width_oct: float, gain) -> np.ndarray:
    """Stereo-Rauschen, dessen Frequenzband (center_hz) und Lautstärke (gain) sich über die Zeit ändern.
    center_hz und gain sind Funktionen von 0..1 (Anteil der Dauer)."""
    hop = _NPERSEG // 4
    n = int(seconds * SAMPLE_RATE)
    frames = n // hop + 5
    freqs = np.fft.rfftfreq(_NPERSEG, 1 / SAMPLE_RATE)
    pos = np.clip(np.arange(frames) * hop / max(n, 1), 0.0, 1.0)   # Frame k liegt bei Sample k * hop
    centers = np.log2(np.maximum(center_hz(pos), 20.0))
    octaves = np.log2(np.maximum(freqs, 20.0))
    env = np.exp(-0.5 * ((octaves[:, None] - centers[None, :]) / width_oct) ** 2) * gain(pos)[None, :]
    out = []
    for _ in range(2):
        spec = (rng.standard_normal(env.shape) + 1j * rng.standard_normal(env.shape)) * env
        _, wave = istft(spec, fs=SAMPLE_RATE, nperseg=_NPERSEG, noverlap=_NPERSEG - hop)
        out.append(wave[:n])
    audio = np.vstack(out)
    peak = np.max(np.abs(audio)) or 1.0
    return audio / peak


def riser(seconds: float, rng: np.random.Generator) -> np.ndarray:
    return _shaped_noise(seconds, rng, lambda p: 300 * (9000 / 300) ** p, 0.7, lambda p: p ** 2.2) * 0.8


def cymbal_swell(seconds: float, rng: np.random.Generator) -> np.ndarray:
    """Rückwärts abgespieltes Becken: hell, schwillt an und reißt auf der Eins ab."""
    return _shaped_noise(seconds, rng, lambda p: 7000 + 0 * p, 1.4, lambda p: np.exp(4.5 * (p - 1))) * 0.7


def downlifter(seconds: float, rng: np.random.Generator) -> np.ndarray:
    return _shaped_noise(seconds, rng, lambda p: 6000 * (250 / 6000) ** p, 0.8, lambda p: (1 - p) ** 1.8) * 0.55


def impact(seconds: float, rng: np.random.Generator) -> np.ndarray:
    """Tiefer Schlag mit fallender Tonhöhe und kurzem Rauschanteil."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    freq = 38 + 50 * np.exp(-t * 7)
    boom = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE) * np.exp(-t * 2.6)
    burst = _shaped_noise(seconds, rng, lambda p: 900 + 0 * p, 1.6, lambda p: np.exp(-p * 18))
    mono = boom + 0.35 * burst.mean(axis=0)[:n]
    return np.vstack([mono, mono]) * 0.9


def render_fx(plan: SongPlan, seed: int = 0) -> np.ndarray:
    """Alle Übergangs-Effekte des Songs als (2, Samples) float32. Leer, wenn der Stil keine nutzt."""
    level = plan.style.fx
    total = int((plan.total_beats * plan.seconds_per_beat + TAIL_SECONDS) * SAMPLE_RATE)
    out = np.zeros((2, total))
    if level == "none":
        return out.astype(np.float32)
    rng = np.random.default_rng(seed)
    spb = plan.seconds_per_beat
    bar = plan.bar_beats * spb         # im 3/4-Takt drei Schläge

    def place(audio, at_seconds, gain=1.0):
        start = int(round(at_seconds * SAMPLE_RATE))
        if start < 0:
            audio, start = audio[:, -start:], 0
        end = min(total, start + audio.shape[1])
        out[:, start:end] += audio[:, :end - start] * gain

    for sec, nxt in zip(plan.sections, plan.sections[1:]):
        if nxt.kind not in ("Chorus", "Drop"):
            continue
        # beginnt der Refrain leise (Breakdown), kommt der Übergang erst, wenn die Band wieder einsetzt
        quiet = nxt.feel == "breakdown"
        hit = (nxt.resume if quiet else sec.end) * spb
        lead = (nxt.resume - nxt.start) * spb if quiet else sec.beats * spb
        swell = min(bar, 2.2)
        place(cymbal_swell(swell, rng), hit - swell, 0.6 if level == "soft" else 0.8)
        if level == "full":
            rise = min(2 * bar, lead)
            place(riser(rise, rng), hit - rise, 0.7)
            place(impact(2.5, rng), hit, 0.9)
            place(downlifter(min(2 * bar, 4.0), rng), hit, 0.45)
    return out.astype(np.float32)
