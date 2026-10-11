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
                  "synth": -24.0, "brass": -24.0, "melody": -21.0, "vocals": -17.0}
DEFAULT_REVERB = {"drums": 0.06, "bass": 0.0, "piano": 0.16, "guitar": 0.12, "strings": 0.28,
                  "synth": 0.2, "brass": 0.15, "melody": 0.2, "vocals": 0.18}


# ── Rendern ──────────────────────────────────────────────────────────────────────
def midi_zu_wav(midi_pfad: str, wav_pfad: str, is_drum: bool = False, instrument_type: str = "piano",
                vst_pfad: str = None, soundfont_pfad: str = None) -> None:
    """
    MIDI → Stereo-WAV. Reihenfolge: eigenes VST3-Instrument (wenn angegeben), SoundFont über
    tinysoundfont, zuletzt eine einfache eingebaute Klangerzeugung. Die Spur wird nicht normalisiert,
    damit die Dynamik erhalten bleibt; die Pegel setzt erst der Mixer.
    """
    soundfont_pfad = soundfont_pfad or SOUNDFONT_PFAD
    midi = pretty_midi.PrettyMIDI(midi_pfad)
    if is_drum:
        for inst in midi.instruments:
            inst.is_drum = True

    audio = _render_vst(midi_pfad, midi, vst_pfad) if vst_pfad else None
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

    audio = np.nan_to_num(audio.astype(np.float32))
    sf.write(wav_pfad, audio.T, SAMPLE_RATE, subtype="FLOAT")
    log.info("Gerendert: %s", os.path.basename(wav_pfad))


def _render_vst(midi_pfad: str, midi: pretty_midi.PrettyMIDI, vst_pfad):
    if not isinstance(vst_pfad, str) or not os.path.exists(vst_pfad):
        log.warning("VST-Pfad nicht gefunden: %s", vst_pfad)
        return None
    try:
        import mido
        plugin = load_plugin(vst_pfad)
        messages = []
        for track in mido.MidiFile(midi_pfad).tracks:
            t = 0.0
            for msg in track:
                t += msg.time
                if not msg.is_meta:
                    messages.append(msg.copy(time=t))
        messages.sort(key=lambda m: m.time)
        seconds = midi.get_end_time() + 2.5
        silence = np.zeros((2, int(seconds * SAMPLE_RATE)), dtype=np.float32)
        return plugin(silence, SAMPLE_RATE, midi_messages=messages)
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
        "vocals":  [HighpassFilter(100), PeakFilter(250, -2.0, 1.0), PeakFilter(3500, 3.0, 1.0),
                    HighShelfFilter(10000, 2.0), Compressor(threshold_db=-20, ratio=3.5, attack_ms=3, release_ms=60)],
    }
    return Pedalboard(chains.get(key, [HighpassFilter(80)]))


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
) -> None:
    """
    Mischt die Spuren zu einem Stereo-Master:
    jede Spur auf ihre Ziel-Lautheit (levels, LUFS) bringen, Fader/Panorama/Mute/Solo aus der App anwenden,
    EQ und Kompressor pro Spur, gemeinsamer Hall und ein Delay für die Stimme, Bass duckt unter der Kick,
    dann Master-Kompressor, Lautheit auf MASTER_LUFS und Limiter.
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
        audio = _channel_chain(key)(audio, SAMPLE_RATE)
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
        if key == "vocals":
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
