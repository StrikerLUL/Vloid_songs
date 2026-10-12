# drum_machine.py – Schlagzeug wie aus der Roland TR-808 und TR-909, ganz ohne Samples.
#
# Jeder Schlag entsteht wie in den Maschinen aus Sinus, Rauschen und Rechteck-Schwingungen: die 808 mit langer,
# tiefer Bassdrum und metallischen Becken aus sechs Rechtecken, die 909 mit kurzer, druckvoller Bassdrum,
# hellerer Snare und mehr Rauschen in den Becken. Ein offenes Hi-Hat verstummt, sobald ein geschlossenes kommt, und
# jede Bassdrum beendet die vorige (so dröhnt die lange 808 nicht in die nächste hinein).
import bisect

import numpy as np
import pretty_midi
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 44100
MACHINES = ("808", "909")
METAL_HZ = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)    # die sechs Rechtecke der 808-Becken
VARIANTS = 4                 # so viele Fassungen pro Klang, damit Wiederholungen nicht gleich klingen
CHOKE_FADE = 0.008           # so schnell verstummt ein Klang, wenn der nächste ihn abschneidet
GAIN = 0.5

KICKS, SNARES, RIM, CLAP = (35, 36), (38, 40), 37, 39
CLOSED_HATS, OPEN_HAT = (42, 44), 46
CRASHES, RIDES, TAMBOURINE, COWBELL = (49, 52, 55, 57), (51, 53, 59), 54, 56
# Toms (General MIDI) → Grundfrequenz in Hz, tief nach hoch
TOMS = {41: 82.0, 43: 98.0, 45: 112.0, 47: 132.0, 48: 152.0, 50: 178.0}
# Diese Klänge verstummen, wenn einer der anderen kommt
CHOKED_BY = {OPEN_HAT: CLOSED_HATS, **{k: KICKS for k in KICKS}}


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE


def _filter(x: np.ndarray, kind: str, freq, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, freq, kind, fs=SAMPLE_RATE, output="sos"), x)


def _sweep(f_start: float, f_end: float, tau: float, t: np.ndarray) -> np.ndarray:
    """Phase eines Sinus, dessen Frequenz in tau Sekunden von f_start auf f_end fällt (wie bei Bassdrum und Toms)."""
    f = f_end + (f_start - f_end) * np.exp(-t / tau)
    return 2 * np.pi * np.cumsum(f) / SAMPLE_RATE


def _after(t: np.ndarray, start: float, tau: float) -> np.ndarray:
    """Abklingende Hüllkurve, die erst bei start beginnt."""
    return np.where(t >= start, np.exp(-np.maximum(t - start, 0.0) / tau), 0.0)


def _metal(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return sum(np.sign(np.sin(2 * np.pi * f * t + rng.random() * 2 * np.pi)) for f in METAL_HZ) / len(METAL_HZ)


def kick(machine: str, rng: np.random.Generator) -> np.ndarray:
    if machine == "808":
        t = _t(0.9)
        body = np.sin(_sweep(125, 48, 0.03, t)) * np.exp(-t / 0.3)
        click = _filter(rng.standard_normal(len(t)), "high", 1200) * np.exp(-t / 0.002) * 0.25
        return body + click
    t = _t(0.5)
    body = np.tanh(2.2 * np.sin(_sweep(270, 52, 0.022, t)) * np.exp(-t / 0.11)) / np.tanh(2.2)
    click = _filter(rng.standard_normal(len(t)), "high", 2500) * np.exp(-t / 0.003) * 0.5
    return body + click


def snare(machine: str, rng: np.random.Generator) -> np.ndarray:
    if machine == "808":
        t = _t(0.3)
        tone = (0.6 * np.sin(2 * np.pi * 180 * t) + 0.4 * np.sin(2 * np.pi * 330 * t)) * np.exp(-t / 0.05)
        snappy = _filter(rng.standard_normal(len(t)), "high", 1800) * np.exp(-t / 0.07)
        return 0.9 * tone + 0.5 * snappy
    t = _t(0.35)
    tone = np.sin(_sweep(270, 185, 0.02, t)) * np.exp(-t / 0.06)
    snappy = _filter(rng.standard_normal(len(t)), "band", (1200, 10000)) * np.exp(-t / 0.11)
    return 0.8 * tone + 0.75 * snappy


def clap(machine: str, rng: np.random.Generator) -> np.ndarray:
    """Mehrere Hände kurz nacheinander, dann ein Nachhall aus Rauschen."""
    t = _t(0.4)
    band = (850, 2600) if machine == "808" else (1000, 4200)
    noise = _filter(rng.standard_normal(len(t)), "band", band)
    env = sum(_after(t, start, 0.006) for start in (0.0, 0.011, 0.023)) + 0.8 * _after(t, 0.031, 0.09)
    return noise * env * 1.2


def rim(machine: str, rng: np.random.Generator) -> np.ndarray:
    t = _t(0.06)
    tone = 0.5 * np.sin(2 * np.pi * 1700 * t) + 0.6 * np.sin(2 * np.pi * 480 * t)
    return _filter(tone, "high", 300) * np.exp(-t / 0.012)


def cymbal(machine: str, rng: np.random.Generator, seconds: float, tau: float, highpass: float) -> np.ndarray:
    """Hi-Hats und Becken: metallische Rechtecke (808) oder mehr Rauschen (909), nur die Höhen."""
    t = _t(seconds)
    metal, noise = (0.75, 0.25) if machine == "808" else (0.4, 0.6)
    source = metal * _metal(t, rng) + noise * rng.standard_normal(len(t))
    bright = _filter(_filter(source, "high", highpass, 4), "low", 16000)
    attack = np.minimum(1.0, t / 0.0005)
    return bright * np.exp(-t / tau) * attack


def ride(machine: str, rng: np.random.Generator) -> np.ndarray:
    t = _t(1.8)
    bell = sum(np.sin(2 * np.pi * f * t) for f in (2950.0, 4410.0, 5320.0)) / 3 * np.exp(-t / 0.4)
    return 0.7 * cymbal(machine, rng, 1.8, 0.7, 3500) + 0.25 * bell


def tom(machine: str, rng: np.random.Generator, freq: float) -> np.ndarray:
    t = _t(0.6 if machine == "808" else 0.45)
    tau = 0.3 if machine == "808" else 0.2
    body = np.sin(_sweep(freq * 1.35, freq, 0.05, t)) * np.exp(-t / tau)
    skin = _filter(rng.standard_normal(len(t)), "band", (freq * 4, freq * 20)) * np.exp(-t / 0.03)
    return body + (0.1 if machine == "808" else 0.25) * skin


def cowbell(machine: str, rng: np.random.Generator) -> np.ndarray:
    t = _t(0.35)
    tone = sum(np.sign(np.sin(2 * np.pi * f * t)) for f in (540.0, 800.0)) / 2
    env = 0.6 * np.exp(-t / 0.012) + 0.4 * np.exp(-t / 0.09)
    return _filter(tone, "band", (500, 3500)) * env


def tambourine(machine: str, rng: np.random.Generator) -> np.ndarray:
    t = _t(0.25)
    env = sum(_after(t, start, 0.03) for start in (0.0, 0.012, 0.024))
    return _filter(rng.standard_normal(len(t)), "high", 6500, 4) * env * 0.6


def hit(pitch: int, machine: str, rng: np.random.Generator):
    """Ein Schlag als Mono-Audio, None für Töne, die die Maschine nicht hat."""
    if pitch in KICKS:
        return kick(machine, rng)
    if pitch in SNARES:
        return snare(machine, rng)
    if pitch == CLAP:
        return clap(machine, rng)
    if pitch == RIM:
        return rim(machine, rng)
    if pitch in CLOSED_HATS:
        return cymbal(machine, rng, 0.15, 0.022 if pitch == 42 else 0.014, 7000) * (1.0 if pitch == 42 else 0.7)
    if pitch == OPEN_HAT:
        return cymbal(machine, rng, 0.9, 0.24, 7000)
    if pitch in CRASHES:
        return cymbal(machine, rng, 2.5, 0.9, 4500)
    if pitch in RIDES:
        return ride(machine, rng)
    if pitch in TOMS:
        return tom(machine, rng, TOMS[pitch])
    if pitch == COWBELL:
        return cowbell(machine, rng)
    if pitch == TAMBOURINE:
        return tambourine(machine, rng)
    return None


def render(midi: pretty_midi.PrettyMIDI, machine: str) -> tuple:
    """
    Spielt die Schlagzeug-Spuren mit der Drum-Machine. Rückgabe: (Stereo-Audio (2, Samples), die Spuren mit
    den Tönen, die die Maschine nicht hat); die übrigen spielt danach der SoundFont.
    Jede Spur bleibt an ihrem Platz im Panorama (MIDI-CC 10, z. B. die Hi-Hats links).
    """
    from renderer import TAIL_SECONDS, _mono_pan
    total = int((midi.get_end_time() + TAIL_SECONDS) * SAMPLE_RATE)
    cutters = {pitch: sorted(n.start for inst in midi.instruments for n in inst.notes if n.pitch in group)
               for pitch, group in CHOKED_BY.items()}
    sounds = {}
    out = np.zeros((2, total), dtype=np.float32)
    rest = []
    for inst in midi.instruments:
        mono = np.zeros(total)
        unknown = []
        for note in inst.notes:
            key = (note.pitch, int(note.start * 1000) % VARIANTS)
            if key not in sounds:
                sounds[key] = hit(note.pitch, machine, np.random.default_rng(key[0] * VARIANTS + key[1]))
            audio = sounds[key]
            if audio is None:
                unknown.append(note)
                continue
            start = int(note.start * SAMPLE_RATE)
            if start >= total:
                continue
            audio = audio[:total - start] * (note.velocity / 127) ** 1.4
            if note.pitch in cutters:
                audio = _choke(audio, note.start, cutters[note.pitch])
            mono[start:start + len(audio)] += audio
        pan = next((cc.value for cc in inst.control_changes if cc.number == 10), 64)
        out += _mono_pan(mono[None, :].astype(np.float32), pan)
        if unknown:
            leftover = pretty_midi.Instrument(program=inst.program, is_drum=True, name=inst.name)
            leftover.notes, leftover.control_changes = unknown, list(inst.control_changes)
            rest.append(leftover)
    return out * GAIN, rest


def _choke(audio: np.ndarray, start: float, chokes: list) -> np.ndarray:
    """Der Klang bis zum nächsten, der ihn abschneidet (chokes: Anschlagzeiten), dann kurz ausblenden."""
    k = bisect.bisect_right(chokes, start + 1e-4)
    if k == len(chokes):
        return audio
    cut = int((chokes[k] - start) * SAMPLE_RATE)
    if cut >= len(audio):
        return audio
    fade = int(CHOKE_FADE * SAMPLE_RATE)
    audio = audio[:cut + fade].copy()
    audio[cut:] *= np.linspace(1.0, 0.0, len(audio) - cut)
    return audio
