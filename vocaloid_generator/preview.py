# preview.py – geänderte Töne sofort anhören, ohne neu zu singen
#
# Die Gesangsmelodie mit den Änderungen (Tonhöhe und Länge) spielt ein Synth-Lead über der Band, aber nur um die
# geänderten Stellen herum (ein Takt davor und danach). Das dauert Sekunden statt eines ganzen Durchgangs mit
# NEUTRINO; gefällt es, singt „Neu singen“ die Änderungen richtig.
import logging
import os
from typing import Optional

import numpy as np
import pretty_midi
import soundfile as sf

from settings import edit_key

log = logging.getLogger(__name__)

FILE = "vorschau_aenderungen.wav"
LEAD_LUFS = -17.0           # so laut wie sonst der Gesang
CONTEXT_BARS = 1            # so viel vor und nach den Änderungen
MAX_SECONDS = 40.0


def edited_melody(result, edits: dict, lengths: dict) -> tuple:
    """Die Gesangsmelodie des Songs mit den Änderungen, in Sekunden, und die geänderten Töne."""
    path = os.path.join(result.output_dir, "vocal_melody.mid")
    try:
        notes = sorted((n for i in pretty_midi.PrettyMIDI(path).instruments for n in i.notes), key=lambda n: n.start)
    except Exception as e:  # noqa: BLE001 – fehlende oder kaputte Datei
        log.warning("Vorschau: keine Gesangsmelodie (%s)", e)
        return [], []
    spb = 60.0 / result.settings.bpm
    changed = []
    for i, n in enumerate(notes):
        key = edit_key(n.start / spb)
        if key not in edits and key not in lengths:
            continue
        n.pitch = edits.get(key, n.pitch)
        if key in lengths:
            limit = notes[i + 1].start if i + 1 < len(notes) else float("inf")
            n.end = min(n.start + lengths[key] * spb, limit)
        changed.append(n)
    return notes, changed


def render(result, edits: dict, lengths: dict) -> Optional[str]:
    """Die Vorschau als WAV im Ausgabeordner des Songs; None ohne Änderungen oder ohne Melodie."""
    from mixer import DEFAULT_LEVELS, SAMPLE_RATE, _loudness, _track_key
    from synth_engine import SAMPLE_RATE as SYNTH_RATE
    from synth_engine import render_notes
    notes, changed = edited_melody(result, edits, lengths)
    if not changed:
        return None
    bar = 4 * 60.0 / result.settings.bpm
    t0 = max(0.0, min(n.start for n in changed) - CONTEXT_BARS * bar)
    t1 = min(max(n.end for n in changed) + CONTEXT_BARS * bar, t0 + MAX_SECONDS)
    length = int((t1 - t0) * SAMPLE_RATE)
    band = np.zeros((2, length), dtype=np.float32)
    for path in result.wav_files.values():
        if not os.path.exists(path):
            continue
        info = sf.info(path)
        data, rate = sf.read(path, start=int(t0 * info.samplerate), stop=int(t1 * info.samplerate),
                             dtype="float32", always_2d=True)
        if rate != SAMPLE_RATE:
            from scipy.signal import resample_poly
            data = resample_poly(data, SAMPLE_RATE, rate, axis=0).astype(np.float32)
        data = np.repeat(data, 2, axis=1) if data.shape[1] == 1 else data[:, :2]
        stem = np.zeros_like(band)
        stem[:, :min(length, len(data))] = data[:length].T
        loud = _loudness(stem)
        if loud != float("-inf"):
            band += stem * 10 ** ((DEFAULT_LEVELS.get(_track_key(path), -24.0) - loud) / 20)
    lead_notes = [pretty_midi.Note(105, n.pitch, n.start - t0, min(n.end, t1) - t0)
                  for n in notes if t0 <= n.start < t1]
    lead = render_notes(lead_notes, "lead", int((t1 - t0) * SYNTH_RATE))
    if SYNTH_RATE != SAMPLE_RATE:
        from scipy.signal import resample_poly
        lead = resample_poly(lead, SAMPLE_RATE, SYNTH_RATE, axis=1)
    lead = lead[:, :length].astype(np.float32)
    loud = _loudness(lead)
    if loud != float("-inf"):
        lead *= 10 ** ((LEAD_LUFS - loud) / 20)
    mix = band
    mix[:, :lead.shape[1]] += lead
    peak = float(np.max(np.abs(mix))) or 1.0
    path = os.path.join(result.output_dir, FILE)
    sf.write(path, (mix * min(1.0, 0.89 / peak)).T, SAMPLE_RATE)
    return path
