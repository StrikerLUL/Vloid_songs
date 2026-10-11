# synth_engine.py – Eigene Synth-Klänge für moderne Pop-Sounds: Supersaw, Pluck, Pad, Lead und Bässe
#
# Die Oszillatoren sind bandbegrenzt (PolyBLEP), damit hohe Töne nicht verzerrt klingen. Jede Stimme
# wird in Stereo erzeugt: verstimmte Oszillatoren liegen links und rechts verteilt.
import numpy as np
import pretty_midi
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 44100
TAIL_SECONDS = 2.5


def _freq(pitch) -> np.ndarray:
    return 440.0 * 2 ** ((np.asarray(pitch, dtype=np.float64) - 69) / 12)


def _polyblep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(t)
    lo = t < dt
    x = t[lo] / dt[lo]
    out[lo] = x + x - x * x - 1
    hi = t > 1 - dt
    x = (t[hi] - 1) / dt[hi]
    out[hi] = x * x + x + x + 1
    return out


def _saw(freq: np.ndarray, n: int, phase: float) -> np.ndarray:
    """Bandbegrenzte Sägezahnwelle; freq ist ein Wert oder eine Kurve pro Sample."""
    dt = np.broadcast_to(np.asarray(freq, dtype=np.float64) / SAMPLE_RATE, (n,))
    t = (phase + np.cumsum(dt)) % 1.0
    return 2 * t - 1 - _polyblep(t, dt)


def _pulse(freq: np.ndarray, n: int, phase: float, width: float = 0.5) -> np.ndarray:
    return _saw(freq, n, phase) - _saw(freq, n, (phase + width) % 1.0)


def _adsr(n_note: int, n_total: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a, d, r = (max(1, int(x * SAMPLE_RATE)) for x in (attack, decay, release))
    env = np.full(n_total, sustain, dtype=np.float64)
    env[:min(a, n_total)] = np.linspace(0, 1, a, endpoint=False)[:n_total]
    if a < n_total:
        dec = np.linspace(1, sustain, d, endpoint=False)[:max(0, n_total - a)]
        env[a:a + len(dec)] = dec
    hold = env[min(n_note, n_total) - 1] if n_note > 0 else 0.0
    if n_note < n_total:
        env[n_note:] = hold * np.exp(-np.arange(n_total - n_note) / (r / 5))
    return env


def _spread(voices: list, width: float) -> np.ndarray:
    """Oszillatoren gleichmäßig von links nach rechts verteilen."""
    n = len(voices)
    out = np.zeros((2, len(voices[0])))
    for i, v in enumerate(voices):
        pos = 0.0 if n == 1 else (i / (n - 1) * 2 - 1) * width
        angle = (pos + 1) * np.pi / 4
        out[0] += v * np.cos(angle)
        out[1] += v * np.sin(angle)
    return out * np.sqrt(2 / n)


def _rng(note: pretty_midi.Note) -> np.random.Generator:
    return np.random.default_rng(int(note.start * 1000) * 131 + note.pitch)


# ── Stimmen ──────────────────────────────────────────────────────────────────────
SUPERSAW_DETUNE = (-24, -15, -7, 0, 7, 15, 24)     # Cent
FB_DETUNE = (-33, -21, -10, 0, 10, 21, 33)         # Cent, Future-Bass-Akkorde noch breiter
FB_BEND_SEMITONES = 0.8        # Future-Bass-Akkorde setzen so weit über dem Ton ein
REESE_SWEEP_HZ = 0.6           # so oft pro Sekunde öffnet sich der Filter des Reese-Basses


def _supersaw(note, n_note, n_total):
    rng = _rng(note)
    f = _freq(note.pitch)
    voices = [_saw(f * 2 ** (c / 1200), n_total, rng.random()) for c in SUPERSAW_DETUNE]
    env = _adsr(n_note, n_total, 0.012, 0.25, 0.8, 0.25)
    return _spread(voices, 0.9) * env


def _pad(note, n_note, n_total):
    rng = _rng(note)
    f = _freq(note.pitch)
    voices = [_saw(f * 2 ** (c / 1200), n_total, rng.random()) for c in (-11, -4, 4, 11)]
    voices.append(0.5 * np.sin(2 * np.pi * f * np.arange(n_total) / SAMPLE_RATE))
    env = _adsr(n_note, n_total, 0.45, 0.6, 0.85, 1.0)
    return _spread(voices, 0.8) * env


def _pluck(note, n_note, n_total):
    """Zwei leicht verstimmte Sägezähne mit schnell abklingender Lautstärke; die Helligkeit regelt render_notes."""
    rng = _rng(note)
    f = _freq(note.pitch)
    t = np.arange(n_total) / SAMPLE_RATE
    env = np.exp(-t / 0.28) * np.minimum(1.0, t / 0.002)
    if n_note < n_total:
        env[n_note:] *= np.exp(-np.arange(n_total - n_note) / (0.06 * SAMPLE_RATE))
    left = _saw(f * 2 ** (-6 / 1200), n_total, rng.random())
    right = _saw(f * 2 ** (6 / 1200), n_total, rng.random())
    return np.vstack([left, right]) * env


def _lead(note, n_note, n_total, prev_pitch=None):
    """Mono-Lead mit Gleiten vom vorigen Ton und verzögertem Vibrato."""
    f0 = float(_freq(note.pitch))
    t = np.arange(n_total) / SAMPLE_RATE
    semis = np.zeros(n_total)
    if prev_pitch is not None and prev_pitch != note.pitch:
        glide = int(0.035 * SAMPLE_RATE)
        semis[:glide] = (prev_pitch - note.pitch) * (1 - np.linspace(0, 1, glide))[:n_total]
    vib_depth = np.clip((t - 0.18) / 0.25, 0, 1) * 0.18
    semis += vib_depth * np.sin(2 * np.pi * 5.5 * t)
    f = f0 * 2 ** (semis / 12)
    rng = _rng(note)
    voices = [_saw(f * 2 ** (-8 / 1200), n_total, rng.random()), _saw(f * 2 ** (8 / 1200), n_total, rng.random()),
              0.6 * _pulse(f / 2, n_total, rng.random(), 0.5)]
    env = _adsr(n_note, n_total, 0.008, 0.15, 0.85, 0.12)
    return _spread(voices, 0.35) * env


def _chip(note, n_note, n_total):
    rng = _rng(note)
    f = _freq(note.pitch)
    wave = _pulse(f, n_total, rng.random(), 0.25)
    env = _adsr(n_note, n_total, 0.003, 0.12, 0.6, 0.06)
    return np.vstack([wave, wave]) * env * 0.7


def _reese(note, n_note, n_total):
    """Reese-Bass für Drum and Bass: drei verstimmte Sägezähne, deren Schwebung den Ton wandern lässt, ein Filter,
    der langsam auf- und zugeht, etwas Sättigung und darunter ein Sinus für den Druck."""
    rng = _rng(note)
    f = _freq(note.pitch)
    t = np.arange(n_total) / SAMPLE_RATE
    body = _spread([_saw(f * 2 ** (c / 1200), n_total, rng.random()) for c in (-19, 0, 17)], 0.5)
    dark = sosfilt(butter(2, 260, "low", fs=SAMPLE_RATE, output="sos"), body, axis=1)
    bright = sosfilt(butter(2, 1500, "low", fs=SAMPLE_RATE, output="sos"), body, axis=1)
    sweep = 0.5 - 0.5 * np.cos(2 * np.pi * REESE_SWEEP_HZ * t + rng.random() * np.pi)
    growl = np.tanh(2.0 * (dark + sweep * (bright - dark))) / np.tanh(2.0)
    sub = np.sin(2 * np.pi * f * t)
    env = _adsr(n_note, n_total, 0.006, 0.2, 0.9, 0.08)
    return (growl + 0.7 * sub) * env * 0.7


def _sub(note, n_note, n_total):
    """Sub-Bass: ein Sinus mit leichter Sättigung, damit er auch auf kleinen Lautsprechern zu hören ist."""
    f = float(_freq(note.pitch))
    t = np.arange(n_total) / SAMPLE_RATE
    wave = np.tanh(1.6 * np.sin(2 * np.pi * f * t)) / np.tanh(1.6)
    env = _adsr(n_note, n_total, 0.004, 0.1, 0.9, 0.06)
    return np.vstack([wave, wave]) * env * 0.8


def _fb_chord(note, n_note, n_total):
    """Future-Bass-Akkord: sehr breite Supersaw mit einer Oktave darunter, die von oben in den Ton fällt."""
    rng = _rng(note)
    t = np.arange(n_total) / SAMPLE_RATE
    f = _freq(note.pitch) * 2 ** (FB_BEND_SEMITONES * np.exp(-t / 0.025) / 12)
    voices = [_saw(f * 2 ** (c / 1200), n_total, rng.random()) for c in FB_DETUNE]
    voices.append(0.6 * _saw(f / 2, n_total, rng.random()))
    env = _adsr(n_note, n_total, 0.004, 0.3, 0.75, 0.12)
    return _spread(voices, 1.0) * env


# Plucks werden pro Anschlag erst hell und dann dunkel, wie ein Filter, der sich schnell schließt
PLUCK_BRIGHT_HZ, PLUCK_DARK_HZ, PLUCK_FILTER_SECONDS = 9000, 900, 0.09

VOICES = {
    "supersaw": (_supersaw, 0.14, (150, 9000)),
    "pad": (_pad, 1.0, (180, 4200)),
    "pluck": (_pluck, 0.5, (200, 16000)),
    "lead": (_lead, 0.12, (180, 7000)),
    "chip": (_chip, 0.06, (120, 11000)),
    "reese": (_reese, 0.1, (28, 6000)),
    "sub": (_sub, 0.08, (25, 4000)),
    "fb_chord": (_fb_chord, 0.15, (150, 13000)),
}


def render_notes(notes: list, voice: str, length: int = None) -> np.ndarray:
    """Rendert Noten (pretty_midi.Note) mit einer eigenen Stimme. Rückgabe: (2, Samples) float32."""
    fn, release, (hp, lp) = VOICES[voice]
    end = max((n.end for n in notes), default=0.0)
    total = length or int((end + TAIL_SECONDS) * SAMPLE_RATE)
    out = np.zeros((2, total))
    brightness = np.zeros(total) if voice == "pluck" else None
    prev = None
    for note in sorted(notes, key=lambda n: n.start):
        start = int(note.start * SAMPLE_RATE)
        if start >= total:
            continue
        n_note = max(1, int((note.end - note.start) * SAMPLE_RATE))
        n_total = min(n_note + int(release * SAMPLE_RATE), total - start)
        gain = (note.velocity / 127) ** 1.6
        if voice == "lead":
            legato = prev is not None and note.start - prev.end < 0.06
            audio = fn(note, min(n_note, n_total), n_total, prev.pitch if legato else None)
        else:
            audio = fn(note, min(n_note, n_total), n_total)
        out[:, start:start + n_total] += audio * gain
        if brightness is not None:
            decay = np.exp(-np.arange(n_total) / (PLUCK_FILTER_SECONDS * SAMPLE_RATE)) * (0.5 + 0.5 * note.velocity / 127)
            np.maximum(brightness[start:start + n_total], decay, out=brightness[start:start + n_total])
        prev = note
    sos = np.vstack([butter(2, hp, "high", fs=SAMPLE_RATE, output="sos"),
                     butter(2, lp, "low", fs=SAMPLE_RATE, output="sos")])
    out = sosfilt(sos, out, axis=1)
    if brightness is not None:
        dark = sosfilt(butter(2, PLUCK_DARK_HZ, "low", fs=SAMPLE_RATE, output="sos"), out, axis=1)
        bright = sosfilt(butter(2, PLUCK_BRIGHT_HZ, "low", fs=SAMPLE_RATE, output="sos"), out, axis=1)
        out = dark + brightness * (bright - dark)
    return (out * 0.25).astype(np.float32)
