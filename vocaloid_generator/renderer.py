# renderer.py – MIDI mit einem SoundFont in Stereo rendern (tinysoundfont: läuft ohne FluidSynth-DLL)
import functools
import logging
import os

import numpy as np
import pretty_midi

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
TAIL_SECONDS = 2.5
DRUM_CHANNEL = 9


@functools.lru_cache(maxsize=2)
def _soundfont_bytes(path: str, mtime: float) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def render_midi(midi, soundfont_path: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Rendert alle Spuren einer MIDI-Datei (Pfad oder PrettyMIDI) mit ihren eigenen Programmen.
    Schlagzeug-Spuren nutzen das Drum-Kit mit der Programmnummer aus Bank 128.
    Rückgabe: float32-Array der Form (2, Samples).
    """
    import tinysoundfont

    pm = midi if isinstance(midi, pretty_midi.PrettyMIDI) else pretty_midi.PrettyMIDI(midi)
    synth = tinysoundfont.Synth(samplerate=sample_rate)
    sfid = synth.sfload(_soundfont_bytes(soundfont_path, os.path.getmtime(soundfont_path)))

    events = []
    free_channels = [c for c in range(16) if c != DRUM_CHANNEL]
    drum_channel_used = False
    for inst in pm.instruments:
        if inst.is_drum and not drum_channel_used:
            ch, drum_channel_used = DRUM_CHANNEL, True
        elif free_channels:
            ch = free_channels.pop(0)
        else:
            log.warning("Mehr als 16 Spuren in einer MIDI-Datei, %s wird übersprungen", inst.name)
            continue
        if inst.is_drum:
            _select(synth, ch, sfid, 128, inst.program, is_drums=True)
        else:
            _select(synth, ch, sfid, 0, inst.program)
        for n in inst.notes:
            events.append((n.start, 1, "on", ch, n.pitch, n.velocity))
            events.append((n.end, 0, "off", ch, n.pitch, 0))
        for cc in inst.control_changes:
            events.append((cc.time, 0, "cc", ch, cc.number, cc.value))
        for pb in inst.pitch_bends:
            events.append((pb.time, 0, "bend", ch, pb.pitch + 8192, 0))
    events.sort(key=lambda e: (e[0], e[1]))

    end_time = max((e[0] for e in events), default=0.0)
    total = int((end_time + TAIL_SECONDS) * sample_rate)
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    for time, _, kind, ch, a, b in events:
        target = min(int(round(time * sample_rate)), total)
        if target > pos:
            out[pos:target] = np.frombuffer(synth.generate(target - pos), dtype=np.float32).reshape(-1, 2)
            pos = target
        if kind == "on":
            synth.noteon(ch, a, b)
        elif kind == "off":
            synth.noteoff(ch, a)
        elif kind == "cc":
            synth.control_change(ch, a, b)
        else:
            synth.pitchbend(ch, a)
    if pos < total:
        out[pos:] = np.frombuffer(synth.generate(total - pos), dtype=np.float32).reshape(-1, 2)
    return out.T


def _select(synth, ch: int, sfid: int, bank: int, preset: int, is_drums: bool = False) -> None:
    """Programm wählen; fehlt es im SoundFont, nimmt es das erste Programm der Bank."""
    try:
        synth.program_select(ch, sfid, bank, preset, is_drums)
    except Exception:
        synth.program_select(ch, sfid, bank, 0, is_drums)
