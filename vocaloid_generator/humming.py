# humming.py – eine gesummte oder gesungene Melodie (Aufnahme) in Noten verwandeln
#
# Die Tonhöhe kommt aus librosa (pYIN, für eine einzelne Stimme gemacht). Wer etwas schief summt, wird auf die
# eigene Stimmung bezogen: zählt der Abstand zwischen den Tönen, nicht ob sie genau auf dem Klavier liegen. Neue
# Töne beginnen, wo sich die Tonhöhe ändert oder die Stimme kurz absetzt („da-da“). Gerundet wird auf Sechzehntel im
# Tempo des Songs; der erste Ton liegt auf der Eins. Das Ergebnis ist eine MIDI-Datei, die die App wie jede eigene Melodie singt.
import logging
import os
from typing import Optional

import numpy as np
import pretty_midi

log = logging.getLogger(__name__)

RATE = 22050
HOP = 256                   # etwa 12 ms pro Schritt
LOWEST, HIGHEST = "C2", "C6"
MIN_NOTE_SECONDS = 0.08     # kürzere Schnipsel sind Gleiten zwischen zwei Tönen, keine Töne
MIN_VOICED = 0.5            # so sicher muss pYIN sein, dass hier gesungen wird
DIP = 0.3                   # leiser als so viel vom Üblichen: hier setzt die Stimme ab
STEPS_PER_BEAT = 4
MIN_NOTES = 3
FILE_TYPES = ("Aufnahme (*.wav;*.mp3;*.flac;*.ogg;*.m4a)",)


def pitches(path: str) -> np.ndarray:
    """Tonhöhe pro Schritt (MIDI), NaN wo nicht gesungen wird oder die Stimme absetzt."""
    import librosa
    y, _ = librosa.load(path, sr=RATE, mono=True)
    if len(y) < RATE // 4 or not np.any(y):
        return np.array([])
    f0, voiced, prob = librosa.pyin(y, fmin=librosa.note_to_hz(LOWEST), fmax=librosa.note_to_hz(HIGHEST), sr=RATE,
                                    frame_length=2048, hop_length=HOP)
    midi = librosa.hz_to_midi(f0)
    sung = voiced & (prob >= MIN_VOICED)
    level = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0][:len(midi)]
    level = np.pad(level, (0, len(midi) - len(level)))
    if sung.any():
        sung &= level >= DIP * np.median(level[sung])
    midi[~sung] = np.nan
    return midi


def notes(midi: np.ndarray) -> list:
    """Töne als [(Anfang, Ende, Tonhöhe)] in Sekunden."""
    from scipy.signal import medfilt
    sung = ~np.isnan(midi)
    if sung.sum() < 3:
        return []
    # eigene Stimmung: um so viel liegt der Sänger neben den Halbtönen
    tuning = float(np.median((midi[sung] - np.round(midi[sung]) + 0.5) % 1.0 - 0.5))
    smooth = np.where(sung, medfilt(np.nan_to_num(midi - tuning), 5), np.nan)
    steps = np.where(sung, np.round(smooth), -1).astype(int)
    found, start = [], None
    for i in range(len(steps) + 1):
        pitch = steps[i] if i < len(steps) else -1
        if start is not None and pitch != steps[start]:
            found.append((start * HOP / RATE, i * HOP / RATE, int(steps[start])))
            start = None
        if start is None and pitch >= 0:
            start = i
    return [n for n in found if n[1] - n[0] >= MIN_NOTE_SECONDS]


def quantize(found: list, bpm: float) -> list:
    """Auf Sechzehntel im Tempo des Songs, einstimmig, der erste Ton auf der Eins: [(Schlag, Dauer, Tonhöhe)]."""
    if not found:
        return []
    beat = 60.0 / bpm
    first = found[0][0]
    out = []
    for start, end, pitch in found:
        a = round((start - first) / beat * STEPS_PER_BEAT) / STEPS_PER_BEAT
        b = max(a + 1 / STEPS_PER_BEAT, round((end - first) / beat * STEPS_PER_BEAT) / STEPS_PER_BEAT)
        if out and a <= out[-1][0]:            # zwei Töne auf demselben Sechzehntel: der längere bleibt
            if b - a > out[-1][1]:
                out[-1] = (a, b - a, pitch)
            continue
        if out and out[-1][0] + out[-1][1] > a:
            out[-1] = (out[-1][0], a - out[-1][0], out[-1][2])
        out.append((a, b - a, pitch))
    return out


def transcribe(path: str, bpm: float, target: str) -> Optional[int]:
    """Die Aufnahme path als Melodie nach target (MIDI) im Tempo bpm; Rückgabe: Zahl der Töne, None ohne Melodie."""
    try:
        midi = pitches(path)
    except Exception as e:  # noqa: BLE001 – audioread/soundfile werfen je nach Format Verschiedenes
        log.warning("Aufnahme %s nicht lesbar: %s", path, e)
        return None
    melody = quantize(notes(midi), bpm)
    if len(melody) < MIN_NOTES:
        log.warning("In %s ist keine Melodie zu hören", path)
        return None
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
    track = pretty_midi.Instrument(0, name="Gesummt")
    beat = 60.0 / bpm
    track.notes = [pretty_midi.Note(100, pitch, start * beat, (start + dur) * beat) for start, dur, pitch in melody]
    pm.instruments.append(track)
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    pm.write(target)
    log.info("Gesummte Melodie: %d Töne nach %s", len(melody), target)
    return len(melody)


def target_for(recording: str, folder: str) -> str:
    """Wohin die Noten einer Aufnahme kommen: folder/summen/<Name der Aufnahme>.mid."""
    name = os.path.splitext(os.path.basename(recording))[0] or "aufnahme"
    return os.path.join(folder, "summen", f"{name}.mid")
