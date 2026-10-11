# renderer.py – MIDI mit einem SoundFont in Stereo rendern
#
# Erste Wahl ist FluidSynth: es setzt alle Regler des SoundFonts um (z. B. Anschlag öffnet den Filter), und
# GeneralUser GS ist genau dafür gebaut. Fehlt die FluidSynth-Bibliothek (unter Windows holt sie
# setup_fluidsynth.py), rendert tinysoundfont, das ohne zusätzliche DLL läuft.
import copy
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


@functools.lru_cache(maxsize=3)
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


def _events(pm: pretty_midi.PrettyMIDI, sounds: list) -> tuple:
    """
    Kanäle und zeitlich sortierte Ereignisse aller Spuren: ([(Kanal, Programm, Schlagzeug, Klang)], [Ereignis]).
    sounds: pro Spur ein Klang aus sound_library oder None (dann spielt der Haupt-SoundFont).
    """
    channels, events = [], []
    free_channels = [c for c in range(16) if c != DRUM_CHANNEL]
    drum_channel_used = False
    for inst, sound in zip(pm.instruments, sounds):
        if inst.is_drum and not drum_channel_used:
            ch, drum_channel_used = DRUM_CHANNEL, True
        elif free_channels:
            ch = free_channels.pop(0)
        else:
            log.warning("Mehr als 16 Spuren in einer MIDI-Datei, %s wird übersprungen", inst.name)
            continue
        channels.append((ch, inst.program, inst.is_drum, sound))
        for n in inst.notes:
            pitch = sound.pitch(n.pitch) if sound else n.pitch
            events.append((n.start, 1, "on", ch, pitch, n.velocity))
            events.append((n.end, 0, "off", ch, pitch, 0))
        for cc in inst.control_changes:
            events.append((cc.time, 0, "cc", ch, cc.number, cc.value))
        for pb in inst.pitch_bends:
            events.append((pb.time, 0, "bend", ch, pb.pitch, 0))
    events.sort(key=lambda e: (e[0], e[1]))
    return channels, events


def render_midi(midi, soundfont_path: str, sample_rate: int = SAMPLE_RATE, engine: str = None,
                library: bool = True) -> np.ndarray:
    """
    Rendert alle Spuren einer MIDI-Datei (Pfad oder PrettyMIDI) mit ihren eigenen Programmen.
    Schlagzeug-Spuren nutzen das Drum-Kit mit der Programmnummer aus Bank 128.
    engine: "fluidsynth" oder "tinysoundfont"; ohne Angabe FluidSynth, wenn vorhanden.
    library: Programme, für die sound_library einen besseren Klang hat, spielen aus dessen SoundFont.
    Rückgabe: float32-Array der Form (2, Samples).
    """
    pm = midi if isinstance(midi, pretty_midi.PrettyMIDI) else pretty_midi.PrettyMIDI(midi)
    if engine != "tinysoundfont" and _fluidsynth():
        audio = _render(pm, _FluidVoice, soundfont_path, sample_rate, library)
        if audio is not None:
            return audio
        log.warning("FluidSynth kann %s nicht laden, nehme tinysoundfont", soundfont_path)
    elif engine == "fluidsynth":
        raise RuntimeError("FluidSynth ist nicht installiert")
    return _render(pm, _TinyVoice, soundfont_path, sample_rate, library)


def _render(pm: pretty_midi.PrettyMIDI, voice_class, soundfont_path: str, sample_rate: int, library: bool):
    import sound_library
    sounds = [sound_library.find(i.program, i.is_drum, sf3=voice_class.PLAYS_SF3) if library else None
              for i in pm.instruments]
    # Spuren, deren Klang das MIDI-Panorama kaum umsetzt (z. B. die doppelte Gitarre links und rechts),
    # einzeln rendern und selbst verteilen
    own = [k for k, (inst, sound) in enumerate(zip(pm.instruments, sounds))
           if sound and sound.own_pan and _pan_value(inst) is not None]
    if not own:
        return _render_once(pm, sounds, voice_class, soundfont_path, sample_rate)
    keep = [k for k in range(len(pm.instruments)) if k not in own]
    parts = []
    if keep:
        rest = _subset(pm, [pm.instruments[k] for k in keep])
        parts.append(_render_once(rest, [sounds[k] for k in keep], voice_class, soundfont_path, sample_rate))
    for k in own:
        inst = copy.copy(pm.instruments[k])
        inst.control_changes = [cc for cc in inst.control_changes if cc.number != 10]
        audio = _render_once(_subset(pm, [inst]), [sounds[k]], voice_class, soundfont_path, sample_rate)
        parts.append(None if audio is None else _mono_pan(audio, _pan_value(pm.instruments[k])))
    if any(p is None for p in parts):
        return None
    out = np.zeros((2, max(p.shape[1] for p in parts)), dtype=np.float32)
    for p in parts:
        out[:, :p.shape[1]] += p
    return out


def _pan_value(inst: pretty_midi.Instrument):
    return next((cc.value for cc in inst.control_changes if cc.number == 10), None)


def _subset(pm: pretty_midi.PrettyMIDI, instruments: list) -> pretty_midi.PrettyMIDI:
    sub = pretty_midi.PrettyMIDI()
    sub.instruments = list(instruments)
    return sub


def _mono_pan(audio: np.ndarray, value: int) -> np.ndarray:
    """Stereo → Mono, dann mit gleicher Leistung an die Stelle value (MIDI-CC 10, 64 = Mitte)."""
    mono = audio.mean(axis=0)
    angle = (max(-1.0, min(1.0, (value - 64) / 63)) + 1) * np.pi / 4
    return (np.vstack([mono * np.cos(angle), mono * np.sin(angle)]) * np.sqrt(2)).astype(np.float32)


def _render_once(pm: pretty_midi.PrettyMIDI, sounds: list, voice_class, soundfont_path: str, sample_rate: int):
    channels, events = _events(pm, sounds)
    end_time = max((e[0] for e in events), default=0.0)
    total = int((end_time + TAIL_SECONDS) * sample_rate)
    voice = voice_class(sample_rate)
    main = voice.load(soundfont_path)
    if main is None:
        voice.close()
        return None
    for ch, program, is_drum, sound in channels:
        sfid = voice.load(sound.path) if sound else None
        if sfid is not None:
            log.debug("Kanal %d: %s, Preset %d", ch, sound.file, sound.preset)
            voice.select(ch, sfid, sound.bank, sound.preset, is_drum)
        else:
            voice.select(ch, main, 128 if is_drum else 0, program, is_drum)
    return _play(voice, events, total)


def _play(voice, events: list, total: int) -> np.ndarray:
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
    PLAYS_SF3 = True

    def __init__(self, sample_rate: int):
        import ctypes
        fs = _fluidsynth()
        self.sample_rate = sample_rate
        # Samples erst laden, wenn ein Preset gewählt wird: große SoundFonts kosten so kaum Zeit
        self.synth = fs.Synth(gain=FLUID_GAIN, samplerate=sample_rate, channels=16,
                              **{"synth.reverb.active": 0, "synth.chorus.active": 0, "synth.polyphony": 512,
                                 "synth.dynamic-sample-loading": 1})
        self._write = fs._fl.fluid_synth_write_float
        self._write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        fs._fl.fluid_synth_set_interp_method.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        fs._fl.fluid_synth_set_interp_method(self.synth.synth, -1, FLUID_INTERP_HIGHEST)
        self.loaded = {}

    def load(self, path: str):
        """ID des SoundFonts (einmal pro Datei geladen) oder None, wenn er sich nicht laden lässt."""
        if path not in self.loaded:
            sfid = self.synth.sfload(os.path.abspath(path))
            self.loaded[path] = sfid if sfid >= 0 else None
        return self.loaded[path]

    def select(self, ch, sfid, bank, program, is_drum):
        if self.synth.program_select(ch, sfid, bank, program) != 0:
            self.synth.program_select(ch, sfid, bank, 0)

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
    PLAYS_SF3 = False

    def __init__(self, sample_rate: int):
        import tinysoundfont
        self.sample_rate = sample_rate
        self.synth = tinysoundfont.Synth(samplerate=sample_rate)
        self.loaded = {}

    def load(self, path: str):
        if path not in self.loaded:
            try:
                self.loaded[path] = self.synth.sfload(_soundfont_bytes(path, os.path.getmtime(path)))
            except Exception as e:
                log.warning("tinysoundfont kann %s nicht laden: %s", path, e)
                self.loaded[path] = None
        return self.loaded[path]

    def select(self, ch, sfid, bank, program, is_drum):
        _select(self.synth, ch, sfid, bank, program, is_drum and bank == 128)

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
