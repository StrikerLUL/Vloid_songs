# renderer.py – MIDI mit einem SoundFont in Stereo rendern
#
# Erste Wahl ist FluidSynth: es setzt alle Regler des SoundFonts um (z. B. Anschlag öffnet den Filter), und
# GeneralUser GS ist genau dafür gebaut. Fehlt die FluidSynth-Bibliothek (unter Windows holt sie
# setup_fluidsynth.py), rendert tinysoundfont, das ohne zusätzliche DLL läuft.
import functools
import logging
import os

import numpy as np
import pretty_midi

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
TAIL_SECONDS = 2.5
DRUM_CHANNEL = 9
FLUIDSYNTH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "fluidsynth", "bin")
FLUID_GAIN = 0.5
FLUID_INTERP_HIGHEST = 7          # FluidSynth: Interpolation 7. Ordnung, die sauberste


@functools.lru_cache(maxsize=2)
def _soundfont_bytes(path: str, mtime: float) -> bytes:
    with open(path, "rb") as f:
        return f.read()


@functools.lru_cache(maxsize=1)
def _fluidsynth():
    """Das Modul pyfluidsynth, wenn die FluidSynth-Bibliothek gefunden wird, sonst None."""
    if os.path.isdir(FLUIDSYNTH_DIR):
        os.environ["PATH"] = FLUIDSYNTH_DIR + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(FLUIDSYNTH_DIR)
    try:
        import fluidsynth
        fluidsynth.Synth
    except (ImportError, OSError, AttributeError) as e:
        log.info("FluidSynth nicht gefunden (%s), Instrumente kommen von tinysoundfont", e)
        return None
    return fluidsynth


def engine_name() -> str:
    return "FluidSynth" if _fluidsynth() else "tinysoundfont"


def _events(pm: pretty_midi.PrettyMIDI) -> tuple:
    """Kanäle und zeitlich sortierte Ereignisse aller Spuren: ([(Kanal, Programm, Schlagzeug)], [Ereignis])."""
    channels, events = [], []
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
        channels.append((ch, inst.program, inst.is_drum))
        for n in inst.notes:
            events.append((n.start, 1, "on", ch, n.pitch, n.velocity))
            events.append((n.end, 0, "off", ch, n.pitch, 0))
        for cc in inst.control_changes:
            events.append((cc.time, 0, "cc", ch, cc.number, cc.value))
        for pb in inst.pitch_bends:
            events.append((pb.time, 0, "bend", ch, pb.pitch, 0))
    events.sort(key=lambda e: (e[0], e[1]))
    return channels, events


def render_midi(midi, soundfont_path: str, sample_rate: int = SAMPLE_RATE, engine: str = None) -> np.ndarray:
    """
    Rendert alle Spuren einer MIDI-Datei (Pfad oder PrettyMIDI) mit ihren eigenen Programmen.
    Schlagzeug-Spuren nutzen das Drum-Kit mit der Programmnummer aus Bank 128.
    engine: "fluidsynth" oder "tinysoundfont"; ohne Angabe FluidSynth, wenn vorhanden.
    Rückgabe: float32-Array der Form (2, Samples).
    """
    pm = midi if isinstance(midi, pretty_midi.PrettyMIDI) else pretty_midi.PrettyMIDI(midi)
    channels, events = _events(pm)
    end_time = max((e[0] for e in events), default=0.0)
    total = int((end_time + TAIL_SECONDS) * sample_rate)
    if engine != "tinysoundfont" and _fluidsynth():
        voice = _FluidVoice(soundfont_path, sample_rate)
        if voice.ok:
            return _play(voice, channels, events, total)
        log.warning("FluidSynth kann %s nicht laden, nehme tinysoundfont", soundfont_path)
    elif engine == "fluidsynth":
        raise RuntimeError("FluidSynth ist nicht installiert")
    return _play(_TinyVoice(soundfont_path, sample_rate), channels, events, total)


def _play(voice, channels: list, events: list, total: int) -> np.ndarray:
    for ch, program, is_drum in channels:
        voice.select(ch, 128 if is_drum else 0, program, is_drum)
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    for time, _, kind, ch, a, b in events:
        target = min(int(round(time * voice.sample_rate)), total)
        if target > pos:
            out[pos:target] = voice.generate(target - pos)
            pos = target
        if kind == "on":
            voice.noteon(ch, a, b)
        elif kind == "off":
            voice.noteoff(ch, a)
        elif kind == "cc":
            voice.cc(ch, a, b)
        else:
            voice.bend(ch, a)
    if pos < total:
        out[pos:] = voice.generate(total - pos)
    voice.close()
    return out.T


class _FluidVoice:
    """FluidSynth ohne eigenen Hall und Chorus: die kommen im Mixer, für alle Spuren gemeinsam."""

    def __init__(self, soundfont_path: str, sample_rate: int):
        import ctypes
        fs = _fluidsynth()
        self.sample_rate = sample_rate
        self.synth = fs.Synth(gain=FLUID_GAIN, samplerate=sample_rate, channels=16,
                              **{"synth.reverb.active": 0, "synth.chorus.active": 0, "synth.polyphony": 512})
        self._write = fs._fl.fluid_synth_write_float
        self._write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        fs._fl.fluid_synth_set_interp_method.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        fs._fl.fluid_synth_set_interp_method(self.synth.synth, -1, FLUID_INTERP_HIGHEST)
        self.sfid = self.synth.sfload(os.path.abspath(soundfont_path))
        self.ok = self.sfid >= 0

    def select(self, ch, bank, program, is_drum):
        if self.synth.program_select(ch, self.sfid, bank, program) != 0:
            self.synth.program_select(ch, self.sfid, bank, 0)

    def generate(self, n: int) -> np.ndarray:
        buf = np.zeros((n, 2), dtype=np.float32)
        self._write(self.synth.synth, n, buf.ctypes.data, 0, 2, buf.ctypes.data, 1, 2)
        return buf

    def noteon(self, ch, pitch, vel):
        self.synth.noteon(ch, pitch, vel)

    def noteoff(self, ch, pitch):
        self.synth.noteoff(ch, pitch)

    def cc(self, ch, number, value):
        self.synth.cc(ch, number, value)

    def bend(self, ch, value):
        self.synth.pitch_bend(ch, value)

    def close(self):
        self.synth.delete()


class _TinyVoice:
    def __init__(self, soundfont_path: str, sample_rate: int):
        import tinysoundfont
        self.sample_rate = sample_rate
        self.synth = tinysoundfont.Synth(samplerate=sample_rate)
        self.sfid = self.synth.sfload(_soundfont_bytes(soundfont_path, os.path.getmtime(soundfont_path)))

    def select(self, ch, bank, program, is_drum):
        _select(self.synth, ch, self.sfid, bank, program, is_drum)

    def generate(self, n: int) -> np.ndarray:
        return np.frombuffer(self.synth.generate(n), dtype=np.float32).reshape(-1, 2)

    def noteon(self, ch, pitch, vel):
        self.synth.noteon(ch, pitch, vel)

    def noteoff(self, ch, pitch):
        self.synth.noteoff(ch, pitch)

    def cc(self, ch, number, value):
        self.synth.control_change(ch, number, value)

    def bend(self, ch, value):
        self.synth.pitchbend(ch, value + 8192)

    def close(self):
        pass


def _select(synth, ch: int, sfid: int, bank: int, preset: int, is_drums: bool = False) -> None:
    """Programm wählen; fehlt es im SoundFont, nimmt es das erste Programm der Bank."""
    try:
        synth.program_select(ch, sfid, bank, preset, is_drums)
    except Exception:
        synth.program_select(ch, sfid, bank, 0, is_drums)
