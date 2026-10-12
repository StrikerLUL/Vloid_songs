# guitar_amp.py – Verzerrte E-Gitarren wie über einen echten Verstärker mit Box.
#
# Die Verzerrungs-Klänge eines SoundFonts sind Ton für Ton verzerrt aufgenommen; mehrere zusammen klingen dann
# kratzig. Hier spielt der SoundFont die Gitarre sauber, und erst die ganze Spur geht durch Verzerrer und Box,
# wie bei einer echten Gitarre. Die Box ist eingebaut (Filter wie ein Gitarrenlautsprecher) oder die
# Impulsantwort einer echten Box (eine WAV-Datei, kostenlose gibt es viele im Netz).
import copy
import logging
import os
from typing import Optional

import numpy as np
import pretty_midi
import soundfile as sf
from pedalboard import Convolution, Distortion, HighpassFilter, Pedalboard, PeakFilter
from scipy.signal import butter, sosfilt

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
DRIVE_DB = {29: 16.0, 30: 28.0}     # General MIDI: Overdrive- und Distortion-Gitarre
CLEAN_PROGRAM = 27                  # die saubere E-Gitarre, die in den Verstärker spielt
INPUT_PEAK = 0.5                    # so laut kommt jede Spur im Verstärker an
CABINET_LOWPASS_HZ = 5200           # höher reicht ein Gitarrenlautsprecher nicht
OUTPUT_GAIN = 0.3


def wants_amp(inst: pretty_midi.Instrument) -> bool:
    return not inst.is_drum and inst.program in DRIVE_DB and bool(inst.notes)


def amp(audio: np.ndarray, drive_db: float) -> np.ndarray:
    """Verstärker: Bässe straffen, Mitten anheben wie ein Overdrive-Pedal, dann verzerren."""
    board = Pedalboard([HighpassFilter(110), PeakFilter(720, 6.0, 0.7), Distortion(drive_db), PeakFilter(400, -2.0, 1.0)])
    return board(audio, SAMPLE_RATE)


def cabinet(audio: np.ndarray, ir: str = "") -> np.ndarray:
    """
    Box: die Impulsantwort ir oder die eingebaute mit Resonanz bei 110 Hz, Senke bei 450 Hz, Präsenz bei 2,4 kHz
    und steilem Abfall über 5 kHz (der nimmt das Kratzen).
    """
    if ir and os.path.exists(ir):
        try:
            response, rate = sf.read(ir, dtype="float32", always_2d=True)
            box = Convolution(np.ascontiguousarray(response.mean(axis=1)), sample_rate=rate)
            return Pedalboard([box, HighpassFilter(70)])(audio, SAMPLE_RATE)
        except (RuntimeError, ValueError, OSError) as e:      # soundfile: LibsndfileError ist ein RuntimeError
            log.warning("Impulsantwort %s lässt sich nicht laden (%s), nehme die eingebaute Box", ir, e)
    shaped = Pedalboard([HighpassFilter(80), PeakFilter(110, 2.5, 1.0), PeakFilter(450, -3.5, 1.0),
                         PeakFilter(2400, 3.5, 1.2)])(audio, SAMPLE_RATE)
    sos = butter(4, CABINET_LOWPASS_HZ, "low", fs=SAMPLE_RATE, output="sos")
    return sosfilt(sos, shaped, axis=-1).astype(np.float32)


def play(inst: pretty_midi.Instrument, soundfont_path: str, library: bool = True, ir: str = "") -> Optional[np.ndarray]:
    """
    Eine verzerrte Gitarren-Spur: sauber gerendert, durch Verstärker und Box, dann an ihren Platz im Panorama.
    Rückgabe (2, Samples), None wenn der SoundFont nichts spielt (dann rendert sie wie bisher).
    """
    from renderer import _mono_pan, render_midi
    clean = copy.copy(inst)
    clean.program = CLEAN_PROGRAM
    clean.control_changes = [cc for cc in inst.control_changes if cc.number != 10]
    pm = pretty_midi.PrettyMIDI()
    pm.instruments = [clean]
    try:
        audio = render_midi(pm, soundfont_path, library=library)
    except Exception as e:      # FluidSynth und tinysoundfont werfen sehr verschiedene Fehler
        log.warning("Gitarre für den Verstärker nicht gerendert (%s)", e)
        return None
    if audio is None or not np.any(audio):
        return None
    mono = audio.mean(axis=0, keepdims=True)
    mono *= INPUT_PEAK / np.max(np.abs(mono))
    wet = cabinet(amp(mono, DRIVE_DB[inst.program]), ir)
    pan = next((cc.value for cc in inst.control_changes if cc.number == 10), 64)
    return _mono_pan(wet, pan) * OUTPUT_GAIN
