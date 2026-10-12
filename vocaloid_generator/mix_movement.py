# mix_movement.py – Bewegung im Mix: der Song klingt nicht von vorn bis hinten gleich
#
# Drei Dinge, wie sie ein Toningenieur von Hand fahren würde:
#   - Anlauf zum Refrain: im letzten Takt davor verliert die Band nach und nach ihre Bässe (Hochpass-Filter) und wird
#     etwas leiser; mit dem Refrain ist alles auf einmal wieder da, der Refrain wirkt größer.
#   - Hall pro Sektion: Strophen trockener und näher, Bridge, Intro und Outro weiter weg.
#   - Breite Refrains: im Refrain ist die Band breiter (mehr Seitensignal), die Strophen bleiben schmaler.
from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 44100
RISE_BARS = 1                 # so viele Takte vor dem Refrain beginnt der Anlauf
RISE_HIGHPASS_HZ = 700        # so viel Bass nimmt der Filter am Ende des Anlaufs weg
RISE_MIX = 0.75               # Anteil des gefilterten Klangs am Ende des Anlaufs
RISE_DIP_DB = -2.0            # so viel leiser ist die Band am Ende des Anlaufs
RETURN_SECONDS = 0.01         # mit dem Refrain ist alles in so kurzer Zeit wieder da
REVERB = {"Intro": 1.25, "Verse": 0.75, "PreChorus": 0.95, "Chorus": 1.1, "Bridge": 1.45, "Solo": 1.1,
          "Outro": 1.35, "Drop": 0.9, "Build-up": 1.0}
CHORUS_WIDTH = 0.35           # Seitensignal der Band im Refrain so viel lauter (0,35 = +2,6 dB)
RAMP_SECONDS = 0.3            # Übergänge zwischen den Sektionen


@dataclass(frozen=True)
class Part:
    start: float              # Sekunden
    end: float
    kind: str
    bar: float                # Länge eines Takts in Sekunden


def _curve(parts: list, values: dict, length: int, default: float = 1.0) -> np.ndarray:
    """Pro Sample der Wert der Sektion, mit weichen Übergängen."""
    times, levels = [], []
    for p in parts:
        ramp = min(RAMP_SECONDS / 2, (p.end - p.start) / 4)
        times += [p.start + ramp, p.end - ramp]
        levels += [values.get(p.kind, default)] * 2
    if not times:
        return np.full(length, default, dtype=np.float32)
    return np.interp(np.arange(length) / SAMPLE_RATE, times, levels).astype(np.float32)


def reverb_curve(parts: list, length: int) -> np.ndarray:
    """Faktor für den Hall-Send über die Zeit."""
    return _curve(parts, REVERB, length)


def rise_windows(parts: list) -> list:
    """(Start, Ende) der Anläufe: der letzte Takt vor jedem Refrain, der nicht auf einen Refrain folgt."""
    windows = []
    for before, chorus in zip(parts, parts[1:]):
        if chorus.kind == "Chorus" and before.kind != "Chorus":
            start = max(before.start, chorus.start - RISE_BARS * chorus.bar)
            if chorus.start - start > 0.2:
                windows.append((start, chorus.start))
    return windows


def rise(audio: np.ndarray, windows: list) -> np.ndarray:
    """Der Anlauf auf einer Spur der Band: zunehmend gefiltert und leiser, dann sofort wieder voll."""
    out = audio.copy()
    sos = butter(2, RISE_HIGHPASS_HZ, "high", fs=SAMPLE_RATE, output="sos")
    for start, end in windows:
        a, b = int(start * SAMPLE_RATE), min(audio.shape[1], int(end * SAMPLE_RATE))
        if b - a < 2:
            continue
        # etwas Vorlauf, damit der Filter eingeschwungen ist
        pre = max(0, a - int(0.2 * SAMPLE_RATE))
        filtered = sosfilt(sos, audio[:, pre:b], axis=-1)[:, a - pre:].astype(np.float32)
        x = np.linspace(0.0, 1.0, b - a, dtype=np.float32) ** 2
        gain = 10 ** (RISE_DIP_DB * x / 20)
        out[:, a:b] = (audio[:, a:b] * (1 - RISE_MIX * x) + filtered * RISE_MIX * x) * gain
        # Übergang zurück: die letzten Millisekunden blenden in den ungefilterten Klang über
        n = min(int(RETURN_SECONDS * SAMPLE_RATE), b - a)
        fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
        out[:, b - n:b] = out[:, b - n:b] * (1 - fade) + audio[:, b - n:b] * fade
    return out


def width_curve(parts: list, length: int) -> np.ndarray:
    return _curve(parts, {"Chorus": 1.0 + CHORUS_WIDTH}, length)


def widen(audio: np.ndarray, curve: np.ndarray) -> np.ndarray:
    """Mitte bleibt, die Seite wird mit curve verstärkt."""
    mid = (audio[0] + audio[1]) / 2
    side = (audio[0] - audio[1]) / 2 * curve
    return np.vstack([mid + side, mid - side]).astype(np.float32)
