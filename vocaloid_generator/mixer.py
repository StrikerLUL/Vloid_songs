# mixer.py – Spuren rendern, mischen und mastern (Pedalboard für Effekte, pyloudnorm für die Lautheit)
import functools
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pretty_midi
import soundfile as sf
from pedalboard import (Compressor, Delay, HighpassFilter, HighShelfFilter, Limiter, LowpassFilter, LowShelfFilter,
                        Pedalboard, PeakFilter, Reverb, load_plugin)

from config import SOUNDFONT_PFAD

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
MASTER_LUFS = -12.0          # laut wie ein Pop-Master, ohne zu zerren
MIX_REFERENCE_LUFS = -18.0   # Pegel des Mixes vor dem Master-Kompressor
# True Peak: so hoch darf das Signal auch zwischen den Samples werden. -1 dBTP empfehlen YouTube, Spotify und die EBU,
# weil MP3 und AAC Spitzen zwischen den Samples sonst über 0 dB heben (Knacksen beim Abspielen)
TRUE_PEAK_DB = -1.0
TRUE_PEAK_OVERSAMPLING = 4

# Ziel-Lautheit der einzelnen Spuren (LUFS), falls der Stil nichts anderes sagt
DEFAULT_LEVELS = {"drums": -17.0, "bass": -19.5, "piano": -22.0, "guitar": -23.0, "strings": -24.5,
                  "synth": -24.0, "brass": -24.0, "bells": -28.0, "choir": -27.0, "counter": -24.5,
                  "perc": -28.5, "melody": -21.0, "fx": -27.0, "vocals": -17.0, "harmony": -24.0, "gang": -23.0,
                  "double": -25.0, "chops": -23.0}
DEFAULT_REVERB = {"drums": 0.06, "bass": 0.0, "piano": 0.16, "guitar": 0.12, "strings": 0.28,
                  "synth": 0.2, "brass": 0.15, "bells": 0.35, "choir": 0.4, "counter": 0.24,
                  "perc": 0.08, "melody": 0.2, "fx": 0.3, "vocals": 0.18, "harmony": 0.26, "gang": 0.32,
                  "double": 0.18, "band": 0.03, "chops": 0.25}
# Gesangsdoppelung im Refrain: zwei leicht verstimmte, verzögerte Kopien links und rechts
DOUBLE_CENTS, DOUBLE_DELAYS, DOUBLE_DB = 12, (0.017, 0.026), -9.0
# Echte Doppelung (zweitbeste Fassung im Refrain, vocals_double.wav): so viel leiser als die Hauptstimme, rechts später
REAL_DOUBLE_DB, REAL_DOUBLE_DELAY = -8.0, 0.012
# Gesangsspuren: Hauptstimme, zweite Stimme, der Chor im letzten Refrain („gang“) und die Doppelung; sie hören auf
# den Kanal Gesang
VOCAL_KEYS = ("vocals", "harmony", "gang", "double")
TAMED = ("vocals", "double", "harmony")      # diese Stimmen zähmt resonance.py (1.3.0, G2)
# Studio-Gesangskette: Sättigung (Drive in dB, Anteil) und je Sektion eigener Hall und Delay (Anteil des Sends)
SATURATION_DB, SATURATION_MIX = 6.0, 0.3
# I10 (1.3.0) Druck: Parallelkompression aufs Schlagzeug (die stark komprimierte Kopie so laut dazu), ein
# Bus-Kompressor über die Band als Kleber und ein Mehrband-Kompressor im Master (Übergänge in Hz, je Band
# (Schwelle dB, Ratio, Attack ms, Release ms))
PARALLEL_MIX = 0.4
PARALLEL = (-32.0, 8.0, 1.0, 60.0)
GLUE = (-20.0, 2.0, 10.0, 120.0)
CROSSOVER = (200.0, 3000.0)
MULTIBAND = ((-22.0, 2.5, 20.0, 160.0), (-22.0, 1.8, 10.0, 120.0), (-26.0, 2.0, 4.0, 80.0))
VOCAL_SPACE = {"Intro": (0.22, 0.15), "Verse": (0.10, 0.08), "PreChorus": (0.14, 0.12), "Chorus": (0.20, 0.16),
               "Bridge": (0.30, 0.22), "Build-up": (0.16, 0.14), "Drop": (0.18, 0.14), "Outro": (0.24, 0.18)}
VOCAL_SPACE_DEFAULT = (0.15, 0.12)
# Echo auf dem letzten Wort: Pegel des Sends, Rückkopplung und Länge in Schlägen (punktierte Achtel)
THROW_DB, THROW_FEEDBACK, THROW_BEATS = -2.0, 0.45, 0.75
# Lo-Fi: die Band leiert wie auf einer alten Bandmaschine (Tiefe in Sekunden, Tempo in Hz), klingt dumpfer,
# dazu knistert eine Schallplatte
LOFI_WOW, LOFI_FLUTTER = (0.0012, 0.55), (0.00015, 6.5)
LOFI_LOWPASS_HZ = 6500
VINYL_LUFS, VINYL_CLICKS_PER_SECOND = -40.0, 7.0


# ── Rendern ──────────────────────────────────────────────────────────────────────
def midi_zu_wav(midi_pfad: str, wav_pfad: str, is_drum: bool = False, instrument_type: str = "piano",
                vst_pfad: str = None, soundfont_pfad: str = None, voices: dict = None,
                library: bool = True, drum_machine: str = None, amp: bool = False, cabinet_ir: str = "",
                vst_state: str = "", samples: bool = False, real_drums: bool = False, band: bool = False,
                surge: bool = False, amp_models: bool = False) -> None:
    """
    MIDI → Stereo-WAV. Reihenfolge: eigenes VST3-Instrument (wenn angegeben), SoundFont über
    FluidSynth oder tinysoundfont, zuletzt eine einfache eingebaute Klangerzeugung. Die Spur wird nicht normalisiert,
    damit die Dynamik erhalten bleibt; die Pegel setzt erst der Mixer.
    voices: {Unterspur: Stimme aus synth_engine}; diese Unterspuren spielen die eigenen Synths.
    library: bessere Klänge aus den zusätzlichen SoundFonts (sound_library), soweit vorhanden.
    drum_machine: "808" oder "909": das Schlagzeug kommt aus der Drum-Machine statt aus dem SoundFont.
    amp: verzerrte E-Gitarren spielen sauber und gehen dann über Verstärker und Box (guitar_amp),
    cabinet_ir ist die Impulsantwort einer echten Box (leer = eingebaute Box).
    vst_state: gespeicherter Klang des VST-Instruments (vst_sounds), leer = sein Standardklang.
    samples: Orchester-Instrumente spielen aus echten Aufnahmen (sample_library), soweit vorhanden.
    real_drums: akustische Schlagzeuge spielen aus dem DRS Kit (drum_kit), soweit vorhanden.
    band: Flügel, E-Bass und E-Gitarre spielen aus echten Aufnahmen (band_library), soweit vorhanden.
    surge: die eigenen Synths spielen Werks-Klänge von Surge XT (surge_sounds), soweit es einen passenden gibt.
    amp_models: mit amp der Verstärker aus einem NAM-Modell (amp_models), soweit eingerichtet.
    """
    soundfont_pfad = soundfont_pfad or SOUNDFONT_PFAD
    midi = pretty_midi.PrettyMIDI(midi_pfad)
    if is_drum:
        for inst in midi.instruments:
            inst.is_drum = True

    synths = []
    if is_drum and drum_machine:
        import drum_machine as machine
        audio, midi.instruments = machine.render(midi, drum_machine)
        synths.append(audio)
    elif is_drum and real_drums and not vst_pfad:
        import drum_kit
        audio, midi.instruments = drum_kit.render(midi, SAMPLE_RATE)
        if audio is not None:
            synths.append(audio)
    if amp and not vst_pfad:
        import guitar_amp
        for inst in [i for i in midi.instruments if guitar_amp.wants_amp(i)]:
            audio = guitar_amp.play(inst, soundfont_pfad, library, cabinet_ir, band, amp_models)
            if audio is not None:
                synths.append(audio)
                midi.instruments.remove(inst)
    if voices and not vst_pfad:
        from synth_engine import render_notes
        own = [i for i in midi.instruments if not i.is_drum and _layer(i.name) in voices]
        for i in [i for i in own if i.notes]:
            voice = voices[_layer(i.name)]
            audio = None
            if surge:
                import surge_sounds
                audio = surge_sounds.render(i.notes, voice, SAMPLE_RATE)
            synths.append(audio if audio is not None else render_notes(i.notes, voice))
        midi.instruments = [i for i in midi.instruments if i not in own]
    if samples and not vst_pfad:
        import sample_library
        for inst in [i for i in midi.instruments if sample_library.covers(i)]:
            audio = sample_library.render(inst, SAMPLE_RATE)
            if audio is not None:
                synths.append(audio)
                midi.instruments.remove(inst)
    if band and not vst_pfad:
        import band_library
        for inst in [i for i in midi.instruments if band_library.covers(i)]:
            audio = band_library.render(inst, SAMPLE_RATE)
            if audio is not None:
                synths.append(audio)
                midi.instruments.remove(inst)
    if synths and not any(i.notes for i in midi.instruments):
        _write(wav_pfad, _sum(synths))
        return

    audio = _render_vst(midi, vst_pfad, vst_state) if vst_pfad else None
    if audio is None and os.path.exists(soundfont_pfad):
        try:
            from renderer import render_midi
            audio = render_midi(midi, soundfont_pfad, library=library)
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


def _render_vst(midi: pretty_midi.PrettyMIDI, vst_pfad, state: str = ""):
    """Spielt die Noten mit einem VST3-Instrument (z. B. Surge XT), mit dem gespeicherten Klang state.
    None, wenn das nicht klappt."""
    if not isinstance(vst_pfad, str) or not os.path.exists(vst_pfad):
        log.warning("VST-Pfad nicht gefunden: %s", vst_pfad)
        return None
    try:
        import mido
        plugin = load_plugin(vst_pfad)
        if not getattr(plugin, "is_instrument", False):
            log.warning("%s ist kein Instrument, sondern ein Effekt", os.path.basename(vst_pfad))
            return None
        if state:
            import surge_sounds
            import vst_sounds
            vst_sounds.apply(plugin, state)
            surge_sounds.warm(plugin, SAMPLE_RATE)   # sonst gehen die Töne im ersten Block verloren
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
    if name == "chops":
        return "chops"            # Vocal Chops spielen wie ein Instrument (vocal_chops.py)
    if "vocals_chor" in name or "flaechen" in name or "vocals_rufe" in name:
        return "gang"
    if "adlib" in name:
        return "harmony"
    if "vocals_double" in name:
        return "double"
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


@functools.lru_cache(maxsize=1)
def _k_weighting() -> tuple:
    """Die Filter von pyloudnorm (ITU-R BS.1770-4) als eine Kette von Biquads: (sos, Verstärkung)."""
    import pyloudnorm
    stages = list(pyloudnorm.Meter(SAMPLE_RATE)._filters.values())
    sos = np.array([np.concatenate([f.b / f.a[0], f.a / f.a[0]]) for f in stages], dtype=np.float32)
    return sos, float(np.prod([f.passband_gain for f in stages]))


def _loudness(audio: np.ndarray) -> float:
    """
    Integrierte Lautheit in LUFS (ITU-R BS.1770-4), rechnet wie pyloudnorm (auf 0,001 LU genau), nur schneller:
    beide Filter in einem Durchgang und in 32 Bit, die Blöcke (400 ms, alle 100 ms) aus Summen über 100 ms, und ein
    unhörbar leises Rauschen (-300 dB) hält die Filter in stillen Stellen aus dem extrem langsamen Bereich winziger
    Zahlen (Denormals).
    """
    from scipy.signal import sosfilt
    if audio.shape[1] < SAMPLE_RATE // 2 or not np.any(audio):
        return float("-inf")
    sos, gain = _k_weighting()
    x = np.array(audio[:2], dtype=np.float32)
    x[:, ::2] += 1e-15
    x[:, 1::2] -= 1e-15
    power = sosfilt(sos, x, axis=1)
    np.square(power, out=power)
    hop = SAMPLE_RATE // 10                    # bei 44,1 kHz liegen die Blockgrenzen genau auf diesen Schritten
    channels, n = power.shape
    full = n // hop
    hops = np.concatenate([power[:, :full * hop].reshape(channels, full, hop).sum(axis=2, dtype=np.float64),
                           power[:, full * hop:].sum(axis=1, keepdims=True, dtype=np.float64),
                           np.zeros((channels, 4))], axis=1)
    blocks = int(np.round((n / SAMPLE_RATE - 0.4) / 0.1)) + 1
    z = sum(hops[:, k:k + blocks] for k in range(4)) * (gain * gain / (0.4 * SAMPLE_RATE))
    with np.errstate(divide="ignore"):
        level = -0.691 + 10 * np.log10(z.sum(axis=0))
        audible = level >= -70.0
        if not audible.any():
            return float("-inf")
        relative = -0.691 + 10 * np.log10(z[:, audible].mean(axis=1).sum()) - 10
        gated = (level > relative) & (level > -70.0)
        if not gated.any():
            return float("-inf")
        return float(-0.691 + 10 * np.log10(z[:, gated].mean(axis=1).sum()))


def _channel_chain(key: str, tone=None) -> Pedalboard:
    """EQ und Kompressor einer Spur; tone (vocal_tone.Tone): die Kette des Gesangs für Stimme und Stil."""
    if key == "vocals" and tone is not None:
        return Pedalboard([HighpassFilter(tone.highpass),
                           Compressor(threshold_db=tone.threshold_db, ratio=tone.ratio, attack_ms=tone.attack_ms,
                                      release_ms=tone.release_ms),
                           PeakFilter(tone.mud_hz, tone.mud_db, 1.0),
                           PeakFilter(tone.presence_hz, tone.presence_db, tone.presence_q),
                           HighShelfFilter(tone.air_hz, tone.air_db),
                           Compressor(threshold_db=-22, ratio=3, attack_ms=8, release_ms=120)])
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
        "gang":    [HighpassFilter(200), PeakFilter(350, -3.0, 1.0), PeakFilter(2500, 1.0, 1.0),
                    HighShelfFilter(9000, 1.0), Compressor(threshold_db=-24, ratio=4, attack_ms=8, release_ms=120)],
        "chops":   [HighpassFilter(250), PeakFilter(3000, 1.5, 1.0),
                    Compressor(threshold_db=-20, ratio=3, attack_ms=3, release_ms=80)],
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


def _saturate(audio: np.ndarray, drive_db: float = SATURATION_DB, share: float = SATURATION_MIX) -> np.ndarray:
    """Sanfte Bandsättigung parallel dazu: dichter und präsenter, ohne hörbar zu zerren."""
    drive = 10 ** (drive_db / 20)
    return (audio * (1 - share) + np.tanh(audio * drive) / drive * share).astype(np.float32)


def _vocal_space(sections: list, length: int) -> tuple:
    """(Hall, Delay) des Gesangs über die Zeit: Strophen trockener, Refrain und Bridge weiter; weich übergeblendet."""
    plate = np.full(length, VOCAL_SPACE_DEFAULT[0], dtype=np.float32)
    delay = np.full(length, VOCAL_SPACE_DEFAULT[1], dtype=np.float32)
    for start, end, kind in sections:
        a, b = max(0, int(start * SAMPLE_RATE)), min(length, int(end * SAMPLE_RATE))
        plate[a:b], delay[a:b] = VOCAL_SPACE.get(kind, VOCAL_SPACE_DEFAULT)
    from voice_fx import smooth
    n = int(0.3 * SAMPLE_RATE)
    return smooth(plate, n), smooth(delay, n)


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
    gains = np.array([[np.cos(angle)], [np.sin(angle)]], dtype=np.float32) * np.float32(np.sqrt(2))
    return audio[:2] * gains


def _echo_throws(vocals: np.ndarray, windows: list, bpm: float) -> np.ndarray:
    """Echo nur auf den Fenstern (z. B. dem letzten Wort einer Phrase): punktierte Achtel, abwechselnd rechts
    und links (Ping-Pong), ohne Bass und ohne scharfe Höhen."""
    mask = _window_mask(vocals.shape[1], windows, fade=0.02)
    if not mask.any():
        return np.zeros_like(vocals)
    send = (vocals.mean(axis=0) * mask * 10 ** (THROW_DB / 20))[None].astype(np.float32)
    send = Pedalboard([HighpassFilter(350), LowpassFilter(5000)])(send, SAMPLE_RATE)
    step = THROW_BEATS * 60.0 / bpm
    # links Echos bei 2, 4, 6 ... Schritten, rechts bei 1, 3, 5: dieselbe Kette, um einen Schritt früher
    left = Delay(delay_seconds=2 * step, feedback=THROW_FEEDBACK, mix=1.0)(send, SAMPLE_RATE)[0]
    shift = int(step * SAMPLE_RATE)
    right = np.zeros_like(left)
    right[:len(left) - shift] = left[shift:]
    left = left * np.sqrt(THROW_FEEDBACK)
    return np.vstack([left, right]).astype(np.float32)


def _lofi(band: np.ndarray) -> np.ndarray:
    """Die Band wie von einer alten Bandmaschine: leichtes Leiern, warme Sättigung, gedämpfte Höhen."""
    n = band.shape[1]
    t = np.arange(n) / SAMPLE_RATE
    delay = 0.003 + LOFI_WOW[0] * np.sin(2 * np.pi * LOFI_WOW[1] * t) + \
        LOFI_FLUTTER[0] * np.sin(2 * np.pi * LOFI_FLUTTER[1] * t)
    warped = np.vstack([np.interp(np.arange(n) - delay * SAMPLE_RATE, np.arange(n), ch, left=0.0) for ch in band])
    peak = float(np.max(np.abs(warped))) or 1.0
    warm = np.tanh(1.5 * warped / peak) / np.tanh(1.5) * peak
    warm *= np.sqrt(np.mean(warped ** 2) / max(np.mean(warm ** 2), 1e-12))     # so laut wie vorher
    dull = Pedalboard([LowpassFilter(LOFI_LOWPASS_HZ), LowpassFilter(LOFI_LOWPASS_HZ), HighpassFilter(35)])
    return dull(warm.astype(np.float32), SAMPLE_RATE)


def _vinyl(length: int, seed: int = 7) -> np.ndarray:
    """Schallplatten-Knistern: Knackser in zufälligen Abständen, links und rechts verschieden, und leises Rauschen."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(seed)
    count = int(length / SAMPLE_RATE * VINYL_CLICKS_PER_SECOND)
    clicks = np.zeros((2, length))
    for ch in range(2):
        clicks[ch, rng.integers(0, length, count)] = rng.exponential(1.0, count) * rng.choice((-1.0, 1.0), count)
    crackle = sosfilt(butter(2, (900, 7000), "bandpass", fs=SAMPLE_RATE, output="sos"), clicks, axis=1)
    hiss = sosfilt(butter(2, (2000, 9000), "bandpass", fs=SAMPLE_RATE, output="sos"),
                   rng.standard_normal((2, length)), axis=1) * 0.01
    vinyl = (crackle + hiss).astype(np.float32)
    loud = _loudness(vinyl)
    return vinyl * 10 ** ((VINYL_LUFS - loud) / 20) if np.isfinite(loud) else vinyl


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
    throw_windows: list = None,
    reference: str = None,
    target_lufs: float = MASTER_LUFS,
    sections: list = None,
    energy_contrast_db: float = None,
    vocal_ratio_db: float = None,
    group_targets: dict = None,
    texture: str = "",
    movement: list = None,
    band: str = None,
    vocal_chain: bool = False,
    vocal_space: list = None,
    unmask: bool = False,
    ride: bool = False,
    sung_pads: list = None,
    convolution: bool = False,
    ducked_delay: bool = False,
    vocal_tone=None,
    airwindows: bool = False,
    true_peak: bool = False,
    level_of: Optional["Level"] = None,
    tame: bool = False,
    punch: bool = False,
    sound=None,
) -> Optional["Level"]:
    """
    Mischt die Spuren zu einem Stereo-Master:
    jede Spur auf ihre Ziel-Lautheit (levels, LUFS) bringen, Fader/Panorama/Mute/Solo aus der App anwenden,
    EQ und Kompressor pro Spur, gemeinsamer Hall und ein Delay für die Stimme, Bass duckt unter der Kick,
    dann Master-Kompressor, Lautheit auf target_lufs (Standard MASTER_LUFS) und Limiter.
    double_windows: Zeitbereiche (Sekunden), in denen der Gesang gedoppelt klingt, z. B. die Refrains.
    throw_windows: Zeitbereiche (Sekunden), deren Gesang ein deutliches Echo bekommt, z. B. das letzte Wort einer Phrase.
    reference: Vorbild-Song (WAV, MP3, FLAC); das Mastering gleicht Klangfarbe und Lautheit an ihn an.
    sections, energy_contrast_db: [(Start, Ende in Sekunden, Energie)] und der Abstand zwischen lauten und leisen
    Stellen, den die Vorbilder haben; die Band wird in ruhigen Sektionen entsprechend leiser oder lauter.
    vocal_ratio_db: Gesang gegen Band, wie reference.vocal_ratio_db ihn in den Vorbildern schätzt.
    group_targets: Gesang, Schlagzeug, Bass und Rest der Vorbilder, einzeln gemessen ({Gruppe: {"level", "tilt"}},
    separation.summarize); jede Gruppe wird so laut und so hell wie dort.
    texture: "lofi" lässt die Band wie von einer alten Bandmaschine klingen, mit Schallplatten-Knistern.
    movement: die Sektionen (mix_movement.Part); dann bewegt sich der Mix: Anlauf vor jedem Refrain, Hall je nach
    Sektion, breitere Refrains.
    band: eine fertige Fassung der Band (WAV, z. B. vom Klang-Veredler); sie ersetzt alle Spuren außer Gesang und
    Effekten, so laut wie diese zusammen.
    vocal_chain: Studio-Kette für den Gesang: leichte Sättigung, eine echte Doppelung (vocals_double.wav) statt der
    verstimmten Kopie und, mit vocal_space [(Start, Ende in Sekunden, Sektionsart)], eigener Hall und Delay je Sektion.
    unmask: die Band wird in den Frequenzen leiser, in denen der Gesang gerade laut ist (vocal_mix.unmask).
    ride: der Gesang wird nachgeführt, damit er gleich weit über der Band steht (vocal_mix.ride_gain).
    sung_pads: Zeitbereiche (Sekunden), in denen gesungene Flächen den Keyboard-Chor (choir) ersetzen.
    convolution: die Gesangsplatte aus einer Impulsantwort mit Pre-Delay im Tempo (vocal_mix.plate); eine eigene
    Raum-Impulsantwort ersetzt den gemeinsamen Hall. ducked_delay: das Gesangs-Delay ist leiser, solange gesungen wird.
    vocal_tone: EQ, Kompressor und Sättigung des Gesangs für Stimme und Stil (vocal_tone.Tone); None = die feste Kette.
    airwindows: mit Airwindows Consolidated (setup_airwindows.py), wenn es da ist: Bandsättigung ToTape9 statt der
    eigenen auf dem Gesang, Console7 auf jeder Spur und der Summe.
    true_peak: auch zwischen den Samples höchstens TRUE_PEAK_DB (gemessen mit vierfacher Überabtastung).
    tame: Härte zähmen (resonance.py): Hauptstimme, Doppelung und zweite Stimme werden nur dort leiser, wo einzelne
    Frequenzen gerade herausstechen.
    punch: Druck (I10): Parallelkompression aufs Schlagzeug, Bus-Kompressor über die Band, Mehrband-Kompressor im
    Master.
    sound: Klangbild des Stils (1.4.0, style_dna.Sound): Raum, Delay, Klangfarbe, Breite und Sättigung; None = das
    gemeinsame Klangbild bis 1.3.
    level_of: der Pegel des ganzen Songs (der Rückgabewert seines Mixes); dann ist dieser Mix ein Teil davon
    (Off-Vocal, A-cappella) und geht mit derselben Verstärkung durch den Master, so klingt er so laut wie im Song,
    statt auf target_lufs zu kommen.
    Rückgabe: der Pegel dieses Mixes (Level), None ohne Mix.
    """
    from settings import DEFAULT_VOLUMES

    levels = {**DEFAULT_LEVELS, **(levels or {})}
    levels["double"] = levels["vocals"] + REAL_DOUBLE_DB
    reverb = {**DEFAULT_REVERB, **(reverb or {})}
    volumes, panning, mutes, solos = volumes or {}, panning or {}, mutes or {}, solos or {}
    paths = [p for p in spur_pfade if os.path.exists(p)]
    if not paths:
        log.error("Kein Mix erstellt: keine Spuren vorhanden.")
        return None
    length = max(sf.info(p).frames for p in paths)
    any_solo = any(solos.values())
    real_double = vocal_chain and any(_track_key(p) == "double" for p in paths)
    tape, console, buss = _airwindows(vocal_tone, vocal_chain) if airwindows else (None, None, None)

    tracks = {}
    for path in paths:
        key = _track_key(path)
        channel = "vocals" if key in VOCAL_KEYS else key
        audible = (solos.get(channel, False) if any_solo else True) and not mutes.get(channel, False)
        if not audible:
            continue
        audio = _load(path, length)
        mono = np.array_equal(audio[0], audio[1])
        loud = _loudness(audio)
        if loud == float("-inf"):
            continue
        fader = volumes.get(channel, DEFAULT_VOLUMES.get(channel, 1.0)) / max(DEFAULT_VOLUMES.get(channel, 1.0), 1e-6)
        audio *= 10 ** ((levels.get(key, -22.0) - loud) / 20) * fader
        if key == "choir" and sung_pads:
            audio *= 1.0 - _window_mask(length, sung_pads)
        if key in VOCAL_KEYS:
            audio = _deess(audio)
        if tame and key in TAMED:
            import resonance
            audio = resonance.tame(audio, SAMPLE_RATE)
        if key in ("vocals", "double") and vocal_chain:
            if tape is not None:
                audio = _keep_level(tape(audio, SAMPLE_RATE), audio)
            else:
                audio = _saturate(audio) if vocal_tone is None else _saturate(audio, vocal_tone.drive_db,
                                                                                vocal_tone.drive_mix)
        audio = _channel_chain("vocals" if key == "double" else key, vocal_tone)(audio, SAMPLE_RATE)
        if sound is not None and key not in VOCAL_KEYS and key != "fx":
            audio = _band_color(audio, key, sound)
        if punch and key == "drums":
            audio = parallel_compress(audio)
        if console is not None:
            audio = console(audio, SAMPLE_RATE)
        if key == "vocals" and double_windows and not real_double:
            audio = _double(audio, double_windows)
        elif key == "harmony" and mono:
            audio = _widen(audio)          # eine gedoppelte Harmonie (links und rechts) ist schon breit
        elif key == "double":
            audio = _widen(audio, REAL_DOUBLE_DELAY)
        audio = _pan(audio, panning.get(channel, 0.0))
        tracks[path] = (key, audio)

    if not tracks:
        log.error("Kein Mix erstellt: alle Spuren stumm.")
        return None

    if energy_contrast_db is not None and sections:
        _shape_energy(tracks, sections, energy_contrast_db, length)
    if group_targets:
        _match_groups(tracks, group_targets)
    if vocal_ratio_db is not None:
        _match_vocal_level(tracks, vocal_ratio_db)

    if movement:
        _move(tracks, movement, length)

    drums = [a for k, a in tracks.values() if k == "drums"]
    if drums and sidechain_depth > 0:
        duck = 1.0 - sidechain_depth * _kick_envelope(drums[0])
        for path, (key, audio) in tracks.items():
            if key in ("bass", "synth"):
                tracks[path] = (key, audio * duck)
    if band:
        _replace_band(tracks, band, length)
    room = _seat_vocals(tracks, ride, unmask) if ride or unmask else None

    mix = np.zeros((2, length), dtype=np.float32)
    send = np.zeros_like(mix)
    vocal_send = np.zeros_like(mix)
    plate_send = np.zeros_like(mix)
    space = _vocal_space(vocal_space, length) if vocal_chain and vocal_space else None
    if room is not None:
        mix += room
    if punch:
        glue_band(tracks)
    for key, audio in tracks.values():
        mix += audio
        if space is not None and key in ("vocals", "double"):
            plate_send += audio * space[0]
            vocal_send += audio * space[1]
            continue
        send += audio * reverb.get(key, 0.1)
        if key in VOCAL_KEYS:
            vocal_send += audio * 0.18
    if texture == "lofi":
        band = np.zeros_like(mix)
        for key, audio in tracks.values():
            if key not in VOCAL_KEYS:
                band += audio
        mix += _lofi(band) - band + _vinyl(length)
    lead = [audio for key, audio in tracks.values() if key == "vocals"]
    if throw_windows and lead:
        throws = _echo_throws(lead[0], throw_windows, bpm)
        mix += throws
        send += throws * 0.3

    if movement:
        from mix_movement import reverb_curve
        send *= reverb_curve(movement, length)
    import vocal_mix
    room = vocal_mix.user_impulse("room", SAMPLE_RATE) if convolution else None
    if room is not None:
        mix += LowpassFilter(9000)(vocal_mix.convolve(HighpassFilter(250)(send, SAMPLE_RATE), room, SAMPLE_RATE)
                                   * np.float32(HALL_GAIN), SAMPLE_RATE)
    elif sound is not None:
        mix += _hall(sound)(send, SAMPLE_RATE) * np.float32(sound.hall_gain)
    else:
        hall = Pedalboard([HighpassFilter(250), Reverb(room_size=0.78, damping=0.45, wet_level=1.0, dry_level=0.0,
                                                       width=1.0), LowpassFilter(9000)])
        mix += hall(send, SAMPLE_RATE)
    if np.any(plate_send):
        if convolution:
            mix += vocal_mix.plate(plate_send, SAMPLE_RATE, bpm)
        else:
            plate = Pedalboard([Delay(delay_seconds=0.025, feedback=0.0, mix=1.0), HighpassFilter(350),
                                Reverb(room_size=0.5, damping=0.25, wet_level=1.0, dry_level=0.0, width=0.9),
                                LowpassFilter(11000)])
            mix += plate(plate_send, SAMPLE_RATE)
    if np.any(vocal_send):
        beats, feedback, top = (sound.delay_beats, sound.delay_feedback, sound.delay_lowpass) if sound is not None \
            else (0.75, 0.3, 6000.0)
        echo = Pedalboard([HighpassFilter(300), Delay(delay_seconds=beats * 60.0 / bpm, feedback=feedback, mix=1.0),
                           LowpassFilter(top)])
        wet = echo(vocal_send, SAMPLE_RATE)
        if ducked_delay and lead:
            wet = vocal_mix.duck(wet, lead[0], SAMPLE_RATE)
        mix += wet

    if sound is not None:
        mix = _master_color(mix, sound)
    if buss is not None:
        mix = buss(mix, SAMPLE_RATE)
    master_volume = min(max(volumes.get("master", 1.0), 0.05), 1.0)
    target_lufs += 20 * np.log10(master_volume)
    premaster = _loudness(mix)
    if level_of is not None and level_of.gain_db is None:
        if premaster != float("-inf"):                     # der Song nach Vorbild gemastert: so viel leiser wie davor
            target_lufs += premaster - level_of.premaster
        level_of = None
    if reference and _master_like(mix, reference, output_pfad, target_lufs, limiter_threshold, true_peak):
        return Level(premaster)
    mix, gain_db, scale = _master(mix, compressor_threshold, compressor_ratio, limiter_threshold, target_lufs,
                                  true_peak, punch, level_of)
    sf.write(output_pfad, mix.T, SAMPLE_RATE, subtype="PCM_24")
    log.info("Mix fertig: %s (%.1f LUFS)", output_pfad, _loudness(mix))
    return Level(premaster, gain_db, scale)


@dataclass(frozen=True)
class Level:
    """Wie laut ein Mix vor dem Master war und mit welcher Verstärkung der Master ihn auf die Ziel-Lautheit brachte.
    Ein Teil des Songs (Off-Vocal, A-cappella) geht mit genau diesen Werten durch den Master: dann drücken die
    Kompressoren die Band dort so zusammen wie im Song, und sie ist so laut wie dort."""
    premaster: float
    gain_db: Optional[float] = None     # vor dem Limiter; None nach dem Mastering nach Vorbild
    scale: float = 1.0                  # nach dem Limiter, damit keine Spitze über die Grenze kommt


def _hall(sound) -> Pedalboard:
    """Der gemeinsame Hall im Klangbild des Stils: Größe, Dämpfung, Vorverzögerung und Höhen."""
    chain = [HighpassFilter(250)]
    if sound.predelay > 0:
        chain.append(Delay(delay_seconds=sound.predelay, feedback=0.0, mix=1.0))
    chain += [Reverb(room_size=sound.room, damping=sound.damping, wet_level=1.0, dry_level=0.0, width=1.0),
              LowpassFilter(sound.hall_lowpass)]
    return Pedalboard(chain)


BAND_DRIVE_DB = 9.0          # Sättigung der Band im Klangbild des Stils, bei drive 1 zur Hälfte beigemischt
WIDE_KEYS = ("piano", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "perc")   # Breite je Stil


def _band_color(audio: np.ndarray, key: str, sound) -> np.ndarray:
    """Sättigung und Stereobreite einer Band-Spur im Klangbild des Stils; Bass und Bassdrum bleiben in der Mitte."""
    if sound.drive > 0 and key != "bass":
        audio = _keep_level(_saturate(audio, BAND_DRIVE_DB, 0.5 * sound.drive), audio)
    if abs(sound.width - 1.0) > 1e-3 and key in WIDE_KEYS and audio.shape[0] == 2:
        mid, side = (audio[0] + audio[1]) / 2, (audio[0] - audio[1]) / 2 * np.float32(sound.width)
        audio = np.vstack([mid + side, mid - side]).astype(np.float32)
    return audio


def _master_color(mix: np.ndarray, sound) -> np.ndarray:
    """Die Klangfarbe des Stils auf der Summe, vor dem Master: Tiefen, Mitten und Höhen."""
    chain = [f for f, db in ((LowShelfFilter(110, sound.low_db, 0.7), sound.low_db),
                             (PeakFilter(sound.mid_hz, sound.mid_db, 0.8), sound.mid_db),
                             (HighShelfFilter(9000, sound.high_db, 0.7), sound.high_db)) if abs(db) >= 0.05]
    return Pedalboard(chain)(mix, SAMPLE_RATE) if chain else mix


def _airwindows(tone, vocal_chain: bool) -> tuple:
    """(Band für den Gesang, Console7 Channel, Console7 Buss) als Plugins; fehlt Airwindows, (None, None, None)."""
    import airwindows
    if not airwindows.available():
        return None, None, None
    try:
        tape = airwindows.effect(airwindows.tape_for(tone.drive_mix if tone else 0.3)) if vocal_chain else None
        channel, buss = airwindows.effect(airwindows.CONSOLE_CHANNEL), airwindows.effect(airwindows.CONSOLE_BUSS)
    except Exception as e:  # noqa: BLE001 – ein Plugin, das nicht lädt, ist kein Grund für einen schlechteren Mix
        log.warning("Airwindows nicht geladen, der Mix läuft ohne: %s", e)
        return None, None, None
    log.info("Airwindows: Band auf dem Gesang, Console7 auf jeder Spur und der Summe")
    return tape, channel, buss


def _keep_level(audio: np.ndarray, before: np.ndarray) -> np.ndarray:
    """audio so laut (RMS) wie before."""
    a, b = float(np.sqrt(np.mean(audio ** 2))), float(np.sqrt(np.mean(before ** 2)))
    return (audio * np.float32(b / a)).astype(np.float32) if a > 1e-9 else audio


def _seat_vocals(tracks: dict, ride: bool, unmask: bool) -> Optional[np.ndarray]:
    """Der Gesang sitzt vorn: erst wird er auf der Band geritten (ändert die Gesangsspuren), dann macht die Band ihm
    Platz. Rückgabe: was zum trockenen Mix dazukommt, damit die Band leiser wird, wo er laut ist (oder None)."""
    import vocal_mix
    lead = [p for p, (k, _) in tracks.items() if k == "vocals"]
    others = [p for p, (k, _) in tracks.items() if k not in VOCAL_KEYS]
    if not lead or not others:
        return None
    band = _sum([tracks[p][1] for p in others])
    if ride:
        gain = vocal_mix.ride_gain(_sum([tracks[p][1] for p in lead]), band, SAMPLE_RATE)
        for p, (key, audio) in list(tracks.items()):
            if key in ("vocals", "double"):
                tracks[p] = (key, audio * gain[None, :audio.shape[1]])
        log.info("Gesang auf der Band geritten: %+.1f bis %+.1f dB", 20 * np.log10(gain.min()),
                 20 * np.log10(gain.max()))
    if not unmask:
        return None
    vocal = _sum([a for k, a in tracks.values() if k in ("vocals", "double")])
    log.info("Die Band macht dem Gesang Platz (bis %.0f dB)", vocal_mix.UNMASK_DB)
    return vocal_mix.unmask(band, vocal, SAMPLE_RATE) - band


HALL_GAIN = 1.26             # eine eigene Raum-Impulsantwort so laut wie der Algorithmus-Hall (weißes Rauschen)
MAX_REFERENCE_DB = 6.0       # so weit dürfen die Vorbilder einen Pegel höchstens verschieben


def _move(tracks: dict, parts: list, length: int) -> None:
    """Anlauf vor jedem Refrain und breitere Refrains für die Band (ohne Gesang und Effekte)."""
    import mix_movement
    rises = mix_movement.rise_windows(parts)
    width = mix_movement.width_curve(parts, length)
    for path, (key, audio) in tracks.items():
        if key in VOCAL_KEYS or key == "fx":
            continue
        if rises:
            audio = mix_movement.rise(audio, rises)
        tracks[path] = (key, mix_movement.widen(audio, width))


def _replace_band(tracks: dict, path: str, length: int) -> None:
    """Die Band (alles außer Gesang und Effekten) durch eine fertige Fassung ersetzen, genauso laut."""
    band = [p for p, (key, _) in tracks.items() if key not in VOCAL_KEYS and key != "fx"]
    if not band or not os.path.exists(path):
        return
    new = _load(path, length)
    before, after = _loudness(sum(tracks[p][1] for p in band)), _loudness(new)
    if before == float("-inf") or after == float("-inf"):
        return
    for p in band:
        del tracks[p]
    tracks[path] = ("band", new * 10 ** ((before - after) / 20))


def _shape_energy(tracks: dict, sections: list, target_db: float, length: int) -> None:
    """
    Leise und laute Teile so weit auseinander wie im Vorbild: Die Band wird in ruhigen Sektionen leiser (oder
    lauter), die energiereichsten bleiben, wie sie sind. Gemessen wird wie bei den Vorbildern (reference.contrast_db).
    """
    from reference import contrast_db
    energies = [e for _, _, e in sections]
    lo, hi = min(energies), max(energies)
    band = [path for path, (key, _) in tracks.items() if key not in VOCAL_KEYS]
    if hi - lo < 1e-6 or not band:
        return
    # 0 in der lautesten Sektion, 1 in der leisesten; an den Grenzen 0,3 s Übergang
    times, quiet = [], []
    for start, end, energy in sections:
        ramp = min(0.15, (end - start) / 4)
        times += [start + ramp, end - ramp]
        quiet += [(hi - energy) / (hi - lo)] * 2
    curve = np.interp(np.arange(length) / SAMPLE_RATE, times, quiet).astype(np.float32)
    total = np.zeros_like(curve)
    for _ in range(3):
        mono = sum(audio for _, audio in tracks.values()).mean(axis=0)
        delta = target_db - contrast_db(mono, SAMPLE_RATE)
        if abs(delta) < 0.5:
            break
        step = np.clip(total - delta * curve, -MAX_REFERENCE_DB, MAX_REFERENCE_DB) - total
        for path in band:
            key, audio = tracks[path]
            tracks[path] = (key, audio * 10 ** (step / 20))
        total += step
    log.info("Lautstärke-Verlauf wie im Vorbild: ruhigste Sektion %+.1f dB", float(total[int(np.argmax(curve))]))


MAX_TILT_DB = 4.0            # so weit dürfen die Vorbilder die Höhen einer Gruppe heben oder senken
TILT_HZ = 4000.0
GROUP_EXCERPT = 45.0         # wie separation.EXCERPT_SECONDS: gemessen wird im lautesten Abschnitt


def _group_of(key: str) -> str:
    """Die Gruppe, in die Demucs die Spur stecken würde."""
    if key in VOCAL_KEYS:
        return "vocals"
    if key in ("drums", "perc"):
        return "drums"
    return "bass" if key == "bass" else "other"


def _match_groups(tracks: dict, targets: dict) -> None:
    """Gesang, Schlagzeug, Bass und Rest so laut gegen den ganzen Song und so hell wie in den Vorbildern.
    Gemessen wird wie dort (separation.measure) im lautesten Abschnitt; jede Gruppe wandert höchstens
    MAX_REFERENCE_DB lauter oder leiser und bekommt höchstens MAX_TILT_DB mehr oder weniger Höhen."""
    import separation
    from reference import _loudest_start
    groups = {}
    for path, (key, _) in tracks.items():
        if key != "fx" and _group_of(key) in targets:
            groups.setdefault(_group_of(key), []).append(path)
    if not groups:
        return
    length = next(iter(tracks.values()))[1].shape[1]
    n = min(length, int(GROUP_EXCERPT * SAMPLE_RATE))
    start = _loudest_start(sum(a for _, a in tracks.values()).mean(axis=0), SAMPLE_RATE, GROUP_EXCERPT)
    window = slice(start, start + n)

    def measured() -> dict:
        parts = {g: sum(tracks[p][1][:, window] for p in paths) for g, paths in groups.items()}
        rest = [a[:, window] for p, (_, a) in tracks.items() if not any(p in ps for ps in groups.values())]
        if rest:
            parts["_rest"] = sum(rest)
        return separation.measure(parts)

    changes = {}
    now = measured()
    for group, paths in groups.items():
        if group not in now:
            continue
        if group == "vocals" and targets[group].get("bands"):
            curve = _match_curve(sum(tracks[p][1][:, window] for p in paths), targets[group]["bands"])
            if curve is not None:
                for path in paths:
                    key, audio = tracks[path]
                    tracks[path] = (key, curve(audio, SAMPLE_RATE))
                continue                   # die Kurve ersetzt die Höhen-Stufe
        tilt = float(np.clip(targets[group]["tilt"] - now[group]["tilt"], -MAX_TILT_DB, MAX_TILT_DB))
        if abs(tilt) >= 0.5:
            shelf = Pedalboard([HighShelfFilter(TILT_HZ, tilt, 0.7)])
            for path in paths:
                key, audio = tracks[path]
                tracks[path] = (key, shelf(audio, SAMPLE_RATE))
            changes[group] = [0.0, tilt]
    total = {g: 0.0 for g in groups}
    for _ in range(3):
        now = measured()
        steps = {}
        for group in groups:
            if group in now:
                wanted = total[group] + targets[group]["level"] - now[group]["level"]
                steps[group] = float(np.clip(wanted, -MAX_REFERENCE_DB, MAX_REFERENCE_DB)) - total[group]
        if all(abs(step) < 0.5 for step in steps.values()):
            break
        for group, step in steps.items():
            for path in groups[group]:
                key, audio = tracks[path]
                tracks[path] = (key, audio * np.float32(10 ** (step / 20)))
            total[group] += step
    for group, step in total.items():
        changes.setdefault(group, [0.0, 0.0])[0] = step
    log.info("Mix wie die Vorbilder: %s", ", ".join(
        f"{separation.NAMES[g]} {level:+.1f} dB, Höhen {tilt:+.1f} dB" for g, (level, tilt) in changes.items()))


MAX_CURVE_DB = 4.0           # so weit darf die Klangkurve des Vorbild-Gesangs ein Terzband heben oder senken


def _match_curve(audio: np.ndarray, target: list) -> Optional[Pedalboard]:
    """EQ, der die Klangkurve des Gesangs (Terzbänder) der des Vorbild-Gesangs angleicht, höchstens ±4 dB je Band,
    geglättet über die Nachbarbänder. None, wenn kaum etwas zu tun ist."""
    import separation
    ours = separation.bands_db(audio, SAMPLE_RATE)
    diff = np.array(target, dtype=float) - np.array(ours, dtype=float)
    diff = np.convolve(np.pad(diff, 1, mode="edge"), np.ones(3) / 3, "valid")
    gains = np.clip(diff - diff.mean(), -MAX_CURVE_DB, MAX_CURVE_DB)

    def chain(g: np.ndarray) -> list:
        return [PeakFilter(hz, float(x), 4.3) for hz, x in zip(separation.BAND_CENTERS, g) if abs(x) >= 0.5]

    filters = chain(gains)
    if not filters:
        return None
    # benachbarte Bänder addieren sich: die ganze Kurve bleibt innerhalb von ±MAX_CURVE_DB
    impulse = np.zeros((1, 8192), dtype=np.float32)
    impulse[0, 0] = 1.0
    response = 20 * np.log10(np.abs(np.fft.rfft(Pedalboard(filters)(impulse, SAMPLE_RATE)[0])) + 1e-9)
    freqs = np.fft.rfftfreq(8192, 1.0 / SAMPLE_RATE)
    peak = max(abs(float(np.interp(hz, freqs, response))) for hz in separation.BAND_CENTERS)
    if peak > MAX_CURVE_DB:
        gains = gains * (MAX_CURVE_DB / peak)
        filters = chain(gains)
    log.info("Gesang klingt wie im Vorbild: %s", ", ".join(
        f"{hz:.0f} Hz {g:+.1f}" for hz, g in zip(separation.BAND_CENTERS, gains) if abs(g) >= 1.5) or "kleine Schritte")
    return Pedalboard(filters)


def _match_vocal_level(tracks: dict, target_db: float) -> None:
    """Gesang so laut gegen die Band wie in den Vorbildern; geschätzt mit derselben Methode wie dort."""
    import librosa

    from reference import RATE, VOCAL_EXCERPT, _loudest, vocal_ratio_db
    voices = [path for path, (key, _) in tracks.items() if key in VOCAL_KEYS]
    if not voices:
        return
    total = 0.0
    for _ in range(3):
        mono = sum(audio for _, audio in tracks.values()).mean(axis=0)
        excerpt = librosa.resample(_loudest(mono, SAMPLE_RATE, VOCAL_EXCERPT), orig_sr=SAMPLE_RATE, target_sr=RATE)
        delta = target_db - vocal_ratio_db(excerpt, RATE)
        step = float(np.clip(total + delta, -MAX_REFERENCE_DB, MAX_REFERENCE_DB)) - total
        if abs(step) < 0.5:
            break
        for path in voices:
            key, audio = tracks[path]
            tracks[path] = (key, audio * 10 ** (step / 20))
        total += step
    log.info("Gesang %+.1f dB, so laut wie in den Vorbildern", total)


def _master_like(mix: np.ndarray, reference: str, output_pfad: str, target_lufs: float = MASTER_LUFS,
                 limiter_threshold: float = -0.3, true_peak: bool = False) -> bool:
    """
    Mastering nach Vorbild mit matchering: Frequenzgang und Stereobreite wie beim Vorbild-Song. Die Lautheit
    kommt danach auf target_lufs, damit die gewählte Plattform (YouTube, Spotify, ...) auch hier gilt.
    """
    import tempfile
    if not os.path.exists(reference):
        log.warning("Vorbild-Song nicht gefunden: %s, nutze das normale Mastering", reference)
        return False
    try:
        import matchering as mg
        mg.log(warning_handler=lambda text: log.info("matchering: %s", text))
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "mix.wav")
            loud = _loudness(mix)
            gain = 10 ** ((MIX_REFERENCE_LUFS - loud) / 20) if loud != float("-inf") else 1.0
            sf.write(target, (mix * gain).T, SAMPLE_RATE, subtype="FLOAT")
            mg.process(target=target, reference=reference, results=[mg.pcm24(output_pfad)],
                       config=mg.Config(temp_folder=td))
    except Exception as e:
        log.warning("Mastering nach Vorbild fehlgeschlagen (%s), nutze das normale Mastering", e)
        return False
    done, _ = sf.read(output_pfad, always_2d=True, dtype="float32")
    done = _limit_to(done.T, target_lufs, limiter_threshold, true_peak)
    sf.write(output_pfad, done.T, SAMPLE_RATE, subtype="PCM_24")
    log.info("Mix fertig: %s, gemastert nach %s (%.1f LUFS)", output_pfad, os.path.basename(reference),
             _loudness(done))
    return True


def _compressor(values: tuple) -> Compressor:
    threshold, ratio, attack, release = values
    return Compressor(threshold_db=threshold, ratio=ratio, attack_ms=attack, release_ms=release)


def parallel_compress(drums: np.ndarray) -> np.ndarray:
    """I10: zum Schlagzeug eine stark komprimierte Kopie dazu (New Yorker Kompression): leise Schläge und Raum kommen
    nach vorn, die Spitzen bleiben. Gleich laut wie vorher."""
    crushed = _compressor(PARALLEL)(drums, SAMPLE_RATE)
    loud, squashed = _loudness(drums), _loudness(crushed)
    if loud == float("-inf") or squashed == float("-inf"):
        return drums
    out = drums + crushed * np.float32(PARALLEL_MIX * 10 ** ((loud - squashed) / 20))
    return (out * np.float32(10 ** ((loud - _loudness(out)) / 20))).astype(np.float32)


def glue_band(tracks: dict) -> None:
    """I10: ein Bus-Kompressor über die Band (ohne Gesang), wie ein SSL-Bus: was er an der Summe tut, bekommt jede
    Spur der Band anteilig, so bleiben Hall und Panorama, wie sie sind."""
    band = [path for path, (key, _) in tracks.items() if key not in VOCAL_KEYS]
    if not band:
        return
    total = sum(tracks[path][1] for path in band)
    glued = _compressor(GLUE)(total, SAMPLE_RATE)
    from voice_fx import smooth
    n = int(0.01 * SAMPLE_RATE)               # die Verstärkung des Kompressors, über 10 ms geschätzt
    power = smooth(np.sum(total.astype(np.float64) ** 2, axis=0), n)
    gain = smooth(np.sum(glued.astype(np.float64) * total, axis=0), n) / (power + 1e-12)
    gain = np.where(power > 1e-10, np.clip(gain, 0.0, 1.0), 1.0).astype(np.float32)
    for path in band:
        key, audio = tracks[path]
        tracks[path] = (key, audio * gain)


def multiband(mix: np.ndarray) -> np.ndarray:
    """I10: Mehrband-Kompressor: Bässe, Mitten und Höhen werden einzeln verdichtet. Die Bänder ergeben zusammen
    wieder genau das Signal, solange keiner arbeitet (die Mitten sind der Rest)."""
    from scipy.signal import butter, sosfiltfilt
    low = sosfiltfilt(butter(2, CROSSOVER[0], "lowpass", fs=SAMPLE_RATE, output="sos"), mix, axis=1)
    high = sosfiltfilt(butter(2, CROSSOVER[1], "highpass", fs=SAMPLE_RATE, output="sos"), mix, axis=1)
    mid = mix - low - high
    bands = [np.ascontiguousarray(b, dtype=np.float32) for b in (low, mid, high)]
    return sum(_compressor(v)(b, SAMPLE_RATE) for v, b in zip(MULTIBAND, bands)).astype(np.float32)


def master(mix: np.ndarray, compressor_threshold: float = -20.0, compressor_ratio: float = 2.0,
           limiter_threshold: float = -0.3, target_lufs: float = MASTER_LUFS, true_peak: bool = False,
           punch: bool = False) -> np.ndarray:
    """Master-Kompressor, EQ und Limiter auf target_lufs; punch: davor der Mehrband-Kompressor (I10)."""
    return _master(mix, compressor_threshold, compressor_ratio, limiter_threshold, target_lufs, true_peak, punch)[0]


def _master(mix: np.ndarray, compressor_threshold: float, compressor_ratio: float, limiter_threshold: float,
            target_lufs: float, true_peak: bool, punch: bool, like: Optional[Level] = None) -> tuple:
    """master(); like: der Pegel des ganzen Songs, dann mit dessen Verstärkungen statt auf target_lufs.
    Rückgabe: (Mix, Verstärkung vor dem Limiter in dB, Faktor danach)."""
    loud = _loudness(mix)
    if loud == float("-inf"):
        return mix, None, 1.0
    mix = mix * 10 ** ((MIX_REFERENCE_LUFS - (loud if like is None else like.premaster)) / 20)
    chain = Pedalboard([
        HighpassFilter(25),
        Compressor(threshold_db=compressor_threshold, ratio=compressor_ratio, attack_ms=30, release_ms=150),
        PeakFilter(120, 1.0, 0.7),
        PeakFilter(3000, 0.8, 0.8),
        HighShelfFilter(10000, 1.5),
    ])
    out = chain(mix, SAMPLE_RATE)
    if punch:
        out = multiband(out)
    return _limit(out, target_lufs, limiter_threshold, true_peak, like)


def _limit_to(mix: np.ndarray, target_lufs: float, limiter_threshold: float, true_peak: bool = False) -> np.ndarray:
    """Auf target_lufs bringen, ohne über limiter_threshold zu kommen; mit true_peak auch zwischen den Samples
    nicht über TRUE_PEAK_DB."""
    return _limit(mix, target_lufs, limiter_threshold, true_peak)[0]


def _limit(mix: np.ndarray, target_lufs: float, limiter_threshold: float, true_peak: bool = False,
           like: Optional[Level] = None) -> tuple:
    """_limit_to(); like: mit den Verstärkungen des ganzen Songs. Rückgabe: (Mix, Verstärkung vor dem Limiter in
    dB, Faktor danach)."""
    loud = _loudness(mix)
    if loud == float("-inf"):
        return mix, None, 1.0
    if true_peak:
        limiter_threshold = min(limiter_threshold, TRUE_PEAK_DB)
    # Der Limiter verändert die Lautheit selbst, deshalb die Vorverstärkung ein paar Mal nachregeln
    limiter = Limiter(threshold_db=limiter_threshold, release_ms=80)
    if like is not None:
        gain_db = like.gain_db
        limited = limiter(mix * 10 ** (gain_db / 20), SAMPLE_RATE) * np.float32(like.scale)
    else:
        gain_db = target_lufs - loud
        limited = mix
        for _ in range(4):
            limited = limiter(mix * 10 ** (gain_db / 20), SAMPLE_RATE)
            error = target_lufs - _loudness(limited)
            if abs(error) < 0.3:
                break
            gain_db += error
    mix = limited
    before = float(np.max(np.abs(mix)))
    ceiling = 10 ** (limiter_threshold / 20)
    if like is not None:
        mix = _catch_peaks(mix, ceiling)        # ein Teil des Songs behält dessen Pegel, nur die Spitzen werden leiser
    peak = float(np.max(np.abs(mix)))
    if peak > ceiling:
        mix *= ceiling / peak
    if true_peak:
        over = true_peak_db(mix) - TRUE_PEAK_DB
        if over > 0:                    # Spitzen zwischen den Samples: der Limiter sieht nur die Samples
            mix *= 10 ** (-over / 20)
    after = float(np.max(np.abs(mix)))
    scale = (like.scale if like is not None else 1.0) * (after / before if before > 0 else 1.0)
    return mix.astype(np.float32), gain_db, scale


def _catch_peaks(mix: np.ndarray, ceiling: float, ms: float = 5.0) -> np.ndarray:
    """Nur Spitzen über ceiling leiser, weich über ein paar Millisekunden davor und danach: ein Limiter, der das ganze
    Signal kennt. Der Mittelwert über die Minima aus einem gleich breiten Fenster liegt nie über der nötigen Dämpfung."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    size = 2 * int(ms / 1000 * SAMPLE_RATE) + 1
    need = np.minimum(1.0, ceiling / np.maximum(np.max(np.abs(mix), axis=0), 1e-12).astype(np.float64))
    if need.min() >= 1.0:
        return mix
    gain = uniform_filter1d(minimum_filter1d(need, size, mode="nearest"), size, mode="nearest")
    return (mix * gain[None, :]).astype(np.float32)


def true_peak_db(mix: np.ndarray, chunk: int = 10 * SAMPLE_RATE) -> float:
    """Der höchste Pegel auch zwischen den Samples (dBTP), mit vierfacher Überabtastung wie in ITU-R BS.1770.
    Stückweise, damit ein langer Song nicht vierfach in den Speicher muss; jedes Stück sieht ein paar Samples über
    seine Ränder hinaus, damit dort keine falschen Spitzen entstehen."""
    from scipy.signal import resample_poly
    up, pad = TRUE_PEAK_OVERSAMPLING, 64
    mix = np.atleast_2d(mix)
    peak = 0.0
    for start in range(0, mix.shape[-1], chunk):
        lo = max(0, start - pad)
        piece = resample_poly(mix[:, lo:start + chunk + pad], up, 1, axis=-1)
        inner = piece[:, (start - lo) * up:(start - lo + min(chunk, mix.shape[-1] - start)) * up]
        if inner.size:
            peak = max(peak, float(np.max(np.abs(inner))))
    return 20 * np.log10(peak) if peak > 0 else float("-inf")
