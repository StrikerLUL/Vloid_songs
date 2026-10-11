# mixer.py – Spuren rendern, mischen und mastern (Pedalboard für Effekte, pyloudnorm für die Lautheit)
import logging
import os

import numpy as np
import pretty_midi
import soundfile as sf
from pedalboard import (Compressor, Delay, HighpassFilter, HighShelfFilter, Limiter, LowpassFilter,
                        Pedalboard, PeakFilter, Reverb, load_plugin)

from config import SOUNDFONT_PFAD

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
MASTER_LUFS = -12.0          # laut wie ein Pop-Master, ohne zu zerren
MIX_REFERENCE_LUFS = -18.0   # Pegel des Mixes vor dem Master-Kompressor

# Ziel-Lautheit der einzelnen Spuren (LUFS), falls der Stil nichts anderes sagt
DEFAULT_LEVELS = {"drums": -17.0, "bass": -19.5, "piano": -22.0, "guitar": -23.0, "strings": -24.5,
                  "synth": -24.0, "brass": -24.0, "bells": -28.0, "choir": -27.0, "counter": -24.5,
                  "perc": -28.5, "melody": -21.0, "fx": -27.0, "vocals": -17.0, "harmony": -24.0}
DEFAULT_REVERB = {"drums": 0.06, "bass": 0.0, "piano": 0.16, "guitar": 0.12, "strings": 0.28,
                  "synth": 0.2, "brass": 0.15, "bells": 0.35, "choir": 0.4, "counter": 0.24,
                  "perc": 0.08, "melody": 0.2, "fx": 0.3, "vocals": 0.18, "harmony": 0.26}
# Gesangsdoppelung im Refrain: zwei leicht verstimmte, verzögerte Kopien links und rechts
DOUBLE_CENTS, DOUBLE_DELAYS, DOUBLE_DB = 12, (0.017, 0.026), -9.0


# ── Rendern ──────────────────────────────────────────────────────────────────────
def midi_zu_wav(midi_pfad: str, wav_pfad: str, is_drum: bool = False, instrument_type: str = "piano",
                vst_pfad: str = None, soundfont_pfad: str = None, voices: dict = None) -> None:
    """
    MIDI → Stereo-WAV. Reihenfolge: eigenes VST3-Instrument (wenn angegeben), SoundFont über
    FluidSynth oder tinysoundfont, zuletzt eine einfache eingebaute Klangerzeugung. Die Spur wird nicht normalisiert,
    damit die Dynamik erhalten bleibt; die Pegel setzt erst der Mixer.
    voices: {Unterspur: Stimme aus synth_engine}; diese Unterspuren spielen die eigenen Synths.
    """
    soundfont_pfad = soundfont_pfad or SOUNDFONT_PFAD
    midi = pretty_midi.PrettyMIDI(midi_pfad)
    if is_drum:
        for inst in midi.instruments:
            inst.is_drum = True

    synths = []
    if voices and not vst_pfad:
        from synth_engine import render_notes
        own = [i for i in midi.instruments if not i.is_drum and _layer(i.name) in voices]
        synths = [render_notes(i.notes, voices[_layer(i.name)]) for i in own if i.notes]
        midi.instruments = [i for i in midi.instruments if i not in own]
        if synths and not any(i.notes for i in midi.instruments):
            _write(wav_pfad, _sum(synths))
            return

    audio = _render_vst(midi, vst_pfad) if vst_pfad else None
    if audio is None and os.path.exists(soundfont_pfad):
        try:
            from renderer import render_midi
            audio = render_midi(midi, soundfont_pfad)
        except Exception as e:
            log.warning("SoundFont-Rendering fehlgeschlagen (%s), nutze die einfache Klangerzeugung", e)
    elif audio is None:
        log.warning("SoundFont nicht gefunden: %s, nutze die einfache Klangerzeugung", soundfont_pfad)
    if audio is None:
        audio = _basic_synth(midi)
    _write(wav_pfad, _sum([audio] + synths))


def _layer(track_name: str) -> str:
    """Unterspur aus dem Spurnamen: "Synth pad" → "pad", "Synth" → ""."""
    return track_name.split(" ", 1)[1] if " " in track_name else ""


def _sum(parts: list) -> np.ndarray:
    length = max(p.shape[1] for p in parts)
    out = np.zeros((2, length), dtype=np.float32)
    for p in parts:
        out[:, :p.shape[1]] += p
    return out


def _write(wav_pfad: str, audio: np.ndarray) -> None:
    audio = np.nan_to_num(audio.astype(np.float32))
    sf.write(wav_pfad, audio.T, SAMPLE_RATE, subtype="FLOAT")
    log.info("Gerendert: %s", os.path.basename(wav_pfad))


def _render_vst(midi: pretty_midi.PrettyMIDI, vst_pfad):
    """Spielt die Noten mit einem VST3-Instrument (z. B. Surge XT). None, wenn das nicht klappt."""
    if not isinstance(vst_pfad, str) or not os.path.exists(vst_pfad):
        log.warning("VST-Pfad nicht gefunden: %s", vst_pfad)
        return None
    try:
        import mido
        plugin = load_plugin(vst_pfad)
        if not getattr(plugin, "is_instrument", False):
            log.warning("%s ist kein Instrument, sondern ein Effekt", os.path.basename(vst_pfad))
            return None
        messages = []                       # pedalboard erwartet die Zeiten in Sekunden ab Songbeginn
        for inst in midi.instruments:
            ch = 9 if inst.is_drum else 0
            for n in inst.notes:
                messages.append(mido.Message("note_on", channel=ch, note=n.pitch, velocity=n.velocity, time=n.start))
                messages.append(mido.Message("note_off", channel=ch, note=n.pitch, velocity=0, time=n.end))
            for cc in inst.control_changes:
                messages.append(mido.Message("control_change", channel=ch, control=cc.number, value=cc.value,
                                             time=cc.time))
        messages.sort(key=lambda m: (m.time, m.type == "note_on"))
        audio = np.asarray(plugin(messages, duration=midi.get_end_time() + 2.5, sample_rate=SAMPLE_RATE,
                                  num_channels=2), dtype=np.float32)
        return np.vstack([audio, audio]) if audio.ndim == 1 or audio.shape[0] == 1 else audio[:2]
    except Exception as e:
        log.warning("VST-Rendering mit %s fehlgeschlagen: %s", vst_pfad, e)
        return None


def _basic_synth(midi: pretty_midi.PrettyMIDI) -> np.ndarray:
    """Notlösung ohne SoundFont: Sinustöne für Instrumente, Rauschen und Sinus-Kick für Schlagzeug."""
    n = int((midi.get_end_time() + 2.5) * SAMPLE_RATE)
    mono = np.zeros(n, dtype=np.float32)
    tonal = pretty_midi.PrettyMIDI()
    tonal.instruments = [i for i in midi.instruments if not i.is_drum]
    if any(i.notes for i in tonal.instruments):
        wave = tonal.synthesize(fs=SAMPLE_RATE)[:n]
        mono[:len(wave)] += np.nan_to_num(wave) * 0.3
    rng = np.random.default_rng(0)
    for inst in midi.instruments:
        if not inst.is_drum:
            continue
        for note in inst.notes:
            start = int(note.start * SAMPLE_RATE)
            length = int(0.12 * SAMPLE_RATE)
            t = np.arange(length) / SAMPLE_RATE
            env = np.exp(-t * 30) * note.velocity / 127
            if note.pitch in (35, 36):
                hit = np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 40)) * t) * env
            else:
                hit = rng.standard_normal(length) * env * (0.5 if note.pitch in (38, 40, 39) else 0.15)
            end = min(start + length, n)
            mono[start:end] += hit[:end - start].astype(np.float32)
    return np.vstack([mono, mono])


# ── Mischen ──────────────────────────────────────────────────────────────────────
def _track_key(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0].lower()
    if "harmon" in name:
        return "harmony"
    if "vocal" in name or "stimme" in name:
        return "vocals"
    for key in DEFAULT_LEVELS:
        if key in name:
            return key
    return name


def _load(path: str, length: int) -> np.ndarray:
    data, sr = sf.read(path, always_2d=True, dtype="float32")
    if sr != SAMPLE_RATE:
        from scipy.signal import resample_poly
        data = resample_poly(data, SAMPLE_RATE, sr, axis=0).astype(np.float32)
    data = data.T
    if data.shape[0] == 1:
        data = np.vstack([data, data])
    out = np.zeros((2, length), dtype=np.float32)
    out[:, :min(length, data.shape[1])] = data[:2, :length]
    return out


def _loudness(audio: np.ndarray) -> float:
    import pyloudnorm
    if audio.shape[1] < SAMPLE_RATE // 2 or not np.any(audio):
        return float("-inf")
    return pyloudnorm.Meter(SAMPLE_RATE).integrated_loudness(audio.T.astype(np.float64))


def _channel_chain(key: str) -> Pedalboard:
    chains = {
        "drums":   [HighpassFilter(30), Compressor(threshold_db=-12, ratio=2.5, attack_ms=15, release_ms=120)],
        "bass":    [HighpassFilter(35), LowpassFilter(5000),
                    Compressor(threshold_db=-20, ratio=4, attack_ms=10, release_ms=150)],
        "piano":   [HighpassFilter(90), PeakFilter(300, -2.5, 1.0), HighShelfFilter(8000, 1.5)],
        "guitar":  [HighpassFilter(100), PeakFilter(400, -2.0, 1.0), LowpassFilter(9000)],
        "strings": [HighpassFilter(120), PeakFilter(300, -2.0, 1.0)],
        "synth":   [HighpassFilter(150), PeakFilter(2500, -1.5, 1.0)],
        "brass":   [HighpassFilter(120), PeakFilter(3500, -1.5, 1.0)],
        "melody":  [HighpassFilter(150), PeakFilter(3000, 1.5, 1.0)],
        "bells":   [HighpassFilter(500), HighShelfFilter(9000, 2.0)],
        "choir":   [HighpassFilter(180), PeakFilter(350, -2.5, 1.0), HighShelfFilter(8000, 1.5)],
        "counter": [HighpassFilter(150), PeakFilter(350, -1.5, 1.0), PeakFilter(3000, 1.0, 1.0)],
        "perc":    [HighpassFilter(250), HighShelfFilter(10000, 1.0)],
        "fx":      [HighpassFilter(30)],
        "vocals":  [HighpassFilter(100), Compressor(threshold_db=-14, ratio=6, attack_ms=1, release_ms=40),
                    PeakFilter(250, -2.0, 1.0), PeakFilter(3500, 3.0, 1.0), HighShelfFilter(10000, 2.5),
                    Compressor(threshold_db=-22, ratio=3, attack_ms=8, release_ms=120)],
        "harmony": [HighpassFilter(220), PeakFilter(300, -3.0, 1.0), PeakFilter(3000, 1.0, 1.0),
                    HighShelfFilter(10000, 1.5), Compressor(threshold_db=-22, ratio=4, attack_ms=5, release_ms=100)],
    }
    return Pedalboard(chains.get(key, [HighpassFilter(80)]))


def _deess(audio: np.ndarray, ratio: float = 4.0, share: float = 0.3) -> np.ndarray:
    """
    Zischlaute leiser machen wie ein Split-Band-De-Esser: nur das Band 5–10 kHz wird gedämpft, und nur
    solange es mehr als share des gesamten Gesangspegels ausmacht (bei „s“ und „sh“, nicht bei Vokalen).
    """
    from scipy.signal import butter, lfilter, sosfiltfilt
    # phasenfrei gefiltert, damit audio - band das Band sauber heraustrennt
    band = sosfiltfilt(butter(4, [5000, 10000], "bandpass", fs=SAMPLE_RATE, output="sos"), audio, axis=1)
    a = np.exp(-1.0 / (0.004 * SAMPLE_RATE))
    env_band = lfilter([1 - a], [1, -a], np.abs(band).max(axis=0))
    env_full = lfilter([1 - a], [1, -a], np.abs(audio).max(axis=0))
    excess = np.maximum(env_band / (share * env_full + 1e-6), 1.0)
    gain = excess ** (1 / ratio - 1)
    return (audio - band + band * gain).astype(np.float32)


def _window_mask(length: int, windows: list, fade: float = 0.04) -> np.ndarray:
    mask = np.zeros(length, dtype=np.float32)
    ramp = int(fade * SAMPLE_RATE)
    for start, end in windows:
        a, b = int(start * SAMPLE_RATE), min(length, int(end * SAMPLE_RATE))
        if b <= a:
            continue
        mask[a:b] = 1.0
        n = min(ramp, (b - a) // 2)
        if n:
            mask[a:a + n] *= np.linspace(0, 1, n)
            mask[b - n:b] *= np.linspace(1, 0, n)
    return mask


def _double(audio: np.ndarray, windows: list) -> np.ndarray:
    """Doppelt eingesungen klingender Gesang in den Refrains."""
    from pedalboard import PitchShift
    mask = _window_mask(audio.shape[1], windows)
    if not mask.any():
        return audio
    mono = audio.mean(axis=0, keepdims=True)
    out = audio.copy()
    for ch, (cents, delay) in enumerate(zip((DOUBLE_CENTS, -DOUBLE_CENTS), DOUBLE_DELAYS)):
        copy = PitchShift(semitones=cents / 100)(mono, SAMPLE_RATE)[0]
        d = int(delay * SAMPLE_RATE)
        shifted = np.zeros_like(copy)
        shifted[d:] = copy[:len(copy) - d]
        out[ch] += shifted * mask * 10 ** (DOUBLE_DB / 20)
    return out


def _widen(audio: np.ndarray, delay: float = 0.014) -> np.ndarray:
    """Mono-Spur breit machen: rechts ein paar Millisekunden später."""
    d = int(delay * SAMPLE_RATE)
    out = np.vstack([audio[0], np.zeros_like(audio[1])])
    out[1, d:] = audio[1, :audio.shape[1] - d]
    return out


def _pan(audio: np.ndarray, pan: float) -> np.ndarray:
    """Balance für Stereo-Spuren: -1 links, +1 rechts, gleiche Lautheit in der Mitte."""
    if abs(pan) < 1e-3:
        return audio
    angle = (pan + 1) * np.pi / 4
    return np.vstack([audio[0] * np.cos(angle) * np.sqrt(2), audio[1] * np.sin(angle) * np.sqrt(2)])


def _kick_envelope(drums: np.ndarray) -> np.ndarray:
    from scipy.signal import butter, lfilter, sosfilt
    mono = drums.mean(axis=0)
    low = np.abs(sosfilt(butter(4, 120, "low", fs=SAMPLE_RATE, output="sos"), mono))
    a = np.exp(-1.0 / (0.09 * SAMPLE_RATE))
    env = lfilter([1 - a], [1, -a], low)
    peak = np.percentile(env, 99.5) or 1.0
    return np.clip(env / peak, 0.0, 1.0).astype(np.float32)


def mische_spuren(
    spur_pfade: list,
    lautstaerken: list = None,
    output_pfad: str = "final_mix.wav",
    volumes: dict = None,
    panning: dict = None,
    mutes: dict = None,
    solos: dict = None,
    compressor_threshold: float = -20.0,
    compressor_ratio: float = 2.0,
    limiter_threshold: float = -0.3,
    levels: dict = None,
    reverb: dict = None,
    bpm: float = 120.0,
    sidechain_depth: float = 0.25,
    double_windows: list = None,
) -> None:
    """
    Mischt die Spuren zu einem Stereo-Master:
    jede Spur auf ihre Ziel-Lautheit (levels, LUFS) bringen, Fader/Panorama/Mute/Solo aus der App anwenden,
    EQ und Kompressor pro Spur, gemeinsamer Hall und ein Delay für die Stimme, Bass duckt unter der Kick,
    dann Master-Kompressor, Lautheit auf MASTER_LUFS und Limiter.
    double_windows: Zeitbereiche (Sekunden), in denen der Gesang gedoppelt klingt, z. B. die Refrains.
    """
    from settings import DEFAULT_VOLUMES

    levels = {**DEFAULT_LEVELS, **(levels or {})}
    reverb = {**DEFAULT_REVERB, **(reverb or {})}
    volumes, panning, mutes, solos = volumes or {}, panning or {}, mutes or {}, solos or {}
    paths = [p for p in spur_pfade if os.path.exists(p)]
    if not paths:
        log.error("Kein Mix erstellt: keine Spuren vorhanden.")
        return
    length = max(sf.info(p).frames for p in paths)
    any_solo = any(solos.values())

    tracks = {}
    for path in paths:
        key = _track_key(path)
        audible = (solos.get(key, False) if any_solo else True) and not mutes.get(key, False)
        if not audible:
            continue
        audio = _load(path, length)
        loud = _loudness(audio)
        if loud == float("-inf"):
            continue
        fader = volumes.get(key, DEFAULT_VOLUMES.get(key, 1.0)) / max(DEFAULT_VOLUMES.get(key, 1.0), 1e-6)
        audio *= 10 ** ((levels.get(key, -22.0) - loud) / 20) * fader
        if key in ("vocals", "harmony"):
            audio = _deess(audio)
        audio = _channel_chain(key)(audio, SAMPLE_RATE)
        if key == "vocals" and double_windows:
            audio = _double(audio, double_windows)
        elif key == "harmony":
            audio = _widen(audio)
        audio = _pan(audio, panning.get(key, 0.0))
        tracks[path] = (key, audio)

    if not tracks:
        log.error("Kein Mix erstellt: alle Spuren stumm.")
        return

    drums = [a for k, a in tracks.values() if k == "drums"]
    if drums and sidechain_depth > 0:
        duck = 1.0 - sidechain_depth * _kick_envelope(drums[0])
        for path, (key, audio) in tracks.items():
            if key in ("bass", "synth"):
                tracks[path] = (key, audio * duck)

    mix = np.zeros((2, length), dtype=np.float32)
    send = np.zeros_like(mix)
    vocal_send = np.zeros_like(mix)
    for key, audio in tracks.values():
        mix += audio
        send += audio * reverb.get(key, 0.1)
        if key in ("vocals", "harmony"):
            vocal_send += audio * 0.18

    hall = Pedalboard([HighpassFilter(250), Reverb(room_size=0.78, damping=0.45, wet_level=1.0, dry_level=0.0, width=1.0),
                       LowpassFilter(9000)])
    mix += hall(send, SAMPLE_RATE)
    if np.any(vocal_send):
        echo = Pedalboard([HighpassFilter(300), Delay(delay_seconds=0.75 * 60.0 / bpm, feedback=0.3, mix=1.0),
                           LowpassFilter(6000)])
        mix += echo(vocal_send, SAMPLE_RATE)

    master_volume = min(max(volumes.get("master", 1.0), 0.05), 1.0)
    mix = master(mix, compressor_threshold, compressor_ratio, limiter_threshold,
                 target_lufs=MASTER_LUFS + 20 * np.log10(master_volume))
    sf.write(output_pfad, mix.T, SAMPLE_RATE, subtype="PCM_24")
    log.info("Mix fertig: %s (%.1f LUFS)", output_pfad, _loudness(mix))


def master(mix: np.ndarray, compressor_threshold: float = -20.0, compressor_ratio: float = 2.0,
           limiter_threshold: float = -0.3, target_lufs: float = MASTER_LUFS) -> np.ndarray:
    loud = _loudness(mix)
    if loud == float("-inf"):
        return mix
    mix = mix * 10 ** ((MIX_REFERENCE_LUFS - loud) / 20)
    chain = Pedalboard([
        HighpassFilter(25),
        Compressor(threshold_db=compressor_threshold, ratio=compressor_ratio, attack_ms=30, release_ms=150),
        PeakFilter(120, 1.0, 0.7),
        PeakFilter(3000, 0.8, 0.8),
        HighShelfFilter(10000, 1.5),
    ])
    mix = chain(mix, SAMPLE_RATE)
    # Der Limiter verändert die Lautheit selbst, deshalb die Vorverstärkung ein paar Mal nachregeln
    limiter = Limiter(threshold_db=limiter_threshold, release_ms=80)
    gain_db = target_lufs - _loudness(mix)
    limited = mix
    for _ in range(4):
        limited = limiter(mix * 10 ** (gain_db / 20), SAMPLE_RATE)
        error = target_lufs - _loudness(limited)
        if abs(error) < 0.3:
            break
        gain_db += error
    mix = limited
    ceiling = 10 ** (limiter_threshold / 20)
    peak = float(np.max(np.abs(mix)))
    if peak > ceiling:
        mix *= ceiling / peak
    return mix.astype(np.float32)
