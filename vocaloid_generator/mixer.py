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
                  "perc": -28.5, "melody": -21.0, "fx": -27.0, "vocals": -17.0, "harmony": -24.0, "gang": -23.0,
                  "double": -25.0}
DEFAULT_REVERB = {"drums": 0.06, "bass": 0.0, "piano": 0.16, "guitar": 0.12, "strings": 0.28,
                  "synth": 0.2, "brass": 0.15, "bells": 0.35, "choir": 0.4, "counter": 0.24,
                  "perc": 0.08, "melody": 0.2, "fx": 0.3, "vocals": 0.18, "harmony": 0.26, "gang": 0.32,
                  "double": 0.18, "band": 0.03}
# Gesangsdoppelung im Refrain: zwei leicht verstimmte, verzögerte Kopien links und rechts
DOUBLE_CENTS, DOUBLE_DELAYS, DOUBLE_DB = 12, (0.017, 0.026), -9.0
# Echte Doppelung (zweitbeste Fassung im Refrain, vocals_double.wav): so viel leiser als die Hauptstimme, rechts später
REAL_DOUBLE_DB, REAL_DOUBLE_DELAY = -8.0, 0.012
# Gesangsspuren: Hauptstimme, zweite Stimme, der Chor im letzten Refrain („gang“) und die Doppelung; sie hören auf
# den Kanal Gesang
VOCAL_KEYS = ("vocals", "harmony", "gang", "double")
# Studio-Gesangskette: Sättigung (Drive in dB, Anteil) und je Sektion eigener Hall und Delay (Anteil des Sends)
SATURATION_DB, SATURATION_MIX = 6.0, 0.3
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
                vst_state: str = "", samples: bool = False, real_drums: bool = False) -> None:
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
            audio = guitar_amp.play(inst, soundfont_pfad, library, cabinet_ir)
            if audio is not None:
                synths.append(audio)
                midi.instruments.remove(inst)
    if voices and not vst_pfad:
        from synth_engine import render_notes
        own = [i for i in midi.instruments if not i.is_drum and _layer(i.name) in voices]
        synths += [render_notes(i.notes, voices[_layer(i.name)]) for i in own if i.notes]
        midi.instruments = [i for i in midi.instruments if i not in own]
    if samples and not vst_pfad:
        import sample_library
        for inst in [i for i in midi.instruments if sample_library.covers(i)]:
            audio = sample_library.render(inst, SAMPLE_RATE)
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
            import vst_sounds
            vst_sounds.apply(plugin, state)
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
    if "vocals_chor" in name:
        return "gang"
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
        "gang":    [HighpassFilter(200), PeakFilter(350, -3.0, 1.0), PeakFilter(2500, 1.0, 1.0),
                    HighShelfFilter(9000, 1.0), Compressor(threshold_db=-24, ratio=4, attack_ms=8, release_ms=120)],
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
    return np.vstack([audio[0] * np.cos(angle) * np.sqrt(2), audio[1] * np.sin(angle) * np.sqrt(2)])


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
    texture: str = "",
    movement: list = None,
    band: str = None,
    vocal_chain: bool = False,
    vocal_space: list = None,
) -> None:
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
    texture: "lofi" lässt die Band wie von einer alten Bandmaschine klingen, mit Schallplatten-Knistern.
    movement: die Sektionen (mix_movement.Part); dann bewegt sich der Mix: Anlauf vor jedem Refrain, Hall je nach
    Sektion, breitere Refrains.
    band: eine fertige Fassung der Band (WAV, z. B. vom Klang-Veredler); sie ersetzt alle Spuren außer Gesang und
    Effekten, so laut wie diese zusammen.
    vocal_chain: Studio-Kette für den Gesang: leichte Sättigung, eine echte Doppelung (vocals_double.wav) statt der
    verstimmten Kopie und, mit vocal_space [(Start, Ende in Sekunden, Sektionsart)], eigener Hall und Delay je Sektion.
    """
    from settings import DEFAULT_VOLUMES

    levels = {**DEFAULT_LEVELS, **(levels or {})}
    levels["double"] = levels["vocals"] + REAL_DOUBLE_DB
    reverb = {**DEFAULT_REVERB, **(reverb or {})}
    volumes, panning, mutes, solos = volumes or {}, panning or {}, mutes or {}, solos or {}
    paths = [p for p in spur_pfade if os.path.exists(p)]
    if not paths:
        log.error("Kein Mix erstellt: keine Spuren vorhanden.")
        return
    length = max(sf.info(p).frames for p in paths)
    any_solo = any(solos.values())
    real_double = vocal_chain and any(_track_key(p) == "double" for p in paths)

    tracks = {}
    for path in paths:
        key = _track_key(path)
        channel = "vocals" if key in VOCAL_KEYS else key
        audible = (solos.get(channel, False) if any_solo else True) and not mutes.get(channel, False)
        if not audible:
            continue
        audio = _load(path, length)
        loud = _loudness(audio)
        if loud == float("-inf"):
            continue
        fader = volumes.get(channel, DEFAULT_VOLUMES.get(channel, 1.0)) / max(DEFAULT_VOLUMES.get(channel, 1.0), 1e-6)
        audio *= 10 ** ((levels.get(key, -22.0) - loud) / 20) * fader
        if key in VOCAL_KEYS:
            audio = _deess(audio)
        if key in ("vocals", "double") and vocal_chain:
            audio = _saturate(audio)
        audio = _channel_chain("vocals" if key == "double" else key)(audio, SAMPLE_RATE)
        if key == "vocals" and double_windows and not real_double:
            audio = _double(audio, double_windows)
        elif key == "harmony":
            audio = _widen(audio)
        elif key == "double":
            audio = _widen(audio, REAL_DOUBLE_DELAY)
        audio = _pan(audio, panning.get(channel, 0.0))
        tracks[path] = (key, audio)

    if not tracks:
        log.error("Kein Mix erstellt: alle Spuren stumm.")
        return

    if energy_contrast_db is not None and sections:
        _shape_energy(tracks, sections, energy_contrast_db, length)
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

    mix = np.zeros((2, length), dtype=np.float32)
    send = np.zeros_like(mix)
    vocal_send = np.zeros_like(mix)
    plate_send = np.zeros_like(mix)
    space = _vocal_space(vocal_space, length) if vocal_chain and vocal_space else None
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
    hall = Pedalboard([HighpassFilter(250), Reverb(room_size=0.78, damping=0.45, wet_level=1.0, dry_level=0.0, width=1.0),
                       LowpassFilter(9000)])
    mix += hall(send, SAMPLE_RATE)
    if np.any(plate_send):
        plate = Pedalboard([Delay(delay_seconds=0.025, feedback=0.0, mix=1.0), HighpassFilter(350),
                            Reverb(room_size=0.5, damping=0.25, wet_level=1.0, dry_level=0.0, width=0.9),
                            LowpassFilter(11000)])
        mix += plate(plate_send, SAMPLE_RATE)
    if np.any(vocal_send):
        echo = Pedalboard([HighpassFilter(300), Delay(delay_seconds=0.75 * 60.0 / bpm, feedback=0.3, mix=1.0),
                           LowpassFilter(6000)])
        mix += echo(vocal_send, SAMPLE_RATE)

    master_volume = min(max(volumes.get("master", 1.0), 0.05), 1.0)
    target_lufs += 20 * np.log10(master_volume)
    if reference and _master_like(mix, reference, output_pfad, target_lufs, limiter_threshold):
        return
    mix = master(mix, compressor_threshold, compressor_ratio, limiter_threshold, target_lufs=target_lufs)
    sf.write(output_pfad, mix.T, SAMPLE_RATE, subtype="PCM_24")
    log.info("Mix fertig: %s (%.1f LUFS)", output_pfad, _loudness(mix))


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
                 limiter_threshold: float = -0.3) -> bool:
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
    done = _limit_to(done.T, target_lufs, limiter_threshold)
    sf.write(output_pfad, done.T, SAMPLE_RATE, subtype="PCM_24")
    log.info("Mix fertig: %s, gemastert nach %s (%.1f LUFS)", output_pfad, os.path.basename(reference),
             _loudness(done))
    return True


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
    return _limit_to(chain(mix, SAMPLE_RATE), target_lufs, limiter_threshold)


def _limit_to(mix: np.ndarray, target_lufs: float, limiter_threshold: float) -> np.ndarray:
    """Auf target_lufs bringen, ohne über limiter_threshold zu kommen."""
    if _loudness(mix) == float("-inf"):
        return mix
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
