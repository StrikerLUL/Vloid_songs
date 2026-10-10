# mixer.py – Professioneller Vocaloid-Mix mit Pedalboard (VST3 & Studio-Effekte)
import logging
import os
import numpy as np
import soundfile as sf
import pretty_midi
import mido
from pedalboard import Pedalboard, Reverb, Compressor, Limiter, HighpassFilter, Chorus, Gain, load_plugin, LowShelfFilter, PeakFilter
from config import VST3_SYNTH_PFAD, VST3_DRUMS_PFAD, SOUNDFONT_PFAD
import soundfont_renderer

log = logging.getLogger(__name__)

def _lade_vst(pfad):
    if pfad and os.path.exists(pfad):
        try:
            return load_plugin(pfad)
        except Exception as e:
            log.warning(f"VST3 {pfad} konnte nicht geladen werden: {e}")
    return None

def midi_zu_wav(midi_pfad: str, wav_pfad: str, is_drum: bool = False, instrument_type: str = "piano", vst_pfad: str = None, soundfont_pfad: str = None) -> None:
    """
    Konvertiert MIDI zu WAV. Nutzt Fluidsynth mit soundfont_pfad (Standard: SOUNDFONT_PFAD aus der Config)
    und mappt instrument_type auf ein General-MIDI-Programm. Fallback auf den
    internen Basic-Synth mit Pedalboard-Effekten (Chorus & Reverb).
    """
    soundfont_pfad = soundfont_pfad or SOUNDFONT_PFAD
    # 1. Mapping von instrument_type auf General-MIDI-Programme (0-127)
    inst_type_lower = instrument_type.lower()
    
    if "piano" in inst_type_lower:
        program = 1
    elif "guitar" in inst_type_lower:
        program = 25
    elif "bass" in inst_type_lower:
        program = 33
    elif "strings" in inst_type_lower:
        program = 49
    elif "synth" in inst_type_lower:
        program = 81
    elif "brass" in inst_type_lower:
        program = 62
    elif "drum" in inst_type_lower:
        program = 0
    elif "melody" in inst_type_lower:
        program = 81
    else:
        program = 1

    midi_data = pretty_midi.PrettyMIDI(midi_pfad)
    duration = midi_data.get_end_time() + 2.0  # 2 Sekunden Ausklang
    sample_rate = 44100
    num_samples = int(duration * sample_rate)

    # Weisen Sie das Programm allen Nicht-Drum-Instrumenten zu
    for instrument in midi_data.instruments:
        if is_drum or instrument_type.lower() == "drums":
            instrument.is_drum = True
            instrument.program = 0
        else:
            if not instrument.is_drum:
                instrument.program = program

    audio = None

    # Robust check for vst_pfad
    vst_loaded = None
    if vst_pfad is not None:
        if not isinstance(vst_pfad, str):
            log.warning(f"VST-Pfad '{vst_pfad}' ist kein gültiger String.")
        elif not os.path.exists(vst_pfad):
            log.warning(f"VST-Pfad '{vst_pfad}' existiert nicht als Datei.")
        else:
            try:
                vst_loaded = _lade_vst(vst_pfad)
                if vst_loaded is None:
                    log.warning(f"VST-Pfad '{vst_pfad}' konnte nicht via _lade_vst geladen werden.")
            except Exception as e:
                log.warning(f"VST-Laden fehlgeschlagen für '{vst_pfad}': {e}")

    # Attempt VST rendering if plugin successfully loaded
    if vst_loaded is not None:
        try:
            log.info(f"[VST] Rendere {os.path.basename(midi_pfad)} mit VST {vst_pfad}...")
            import mido
            mid = mido.MidiFile(midi_pfad)
            messages = []
            for track in mid.tracks:
                track_time = 0.0
                for msg in track:
                    track_time += msg.time
                    if not msg.is_meta:
                        messages.append(msg.copy(time=track_time))
            messages.sort(key=lambda m: m.time)

            # Create input silence
            input_audio = np.zeros((2, num_samples), dtype=np.float32)
            audio = vst_loaded(input_audio, sample_rate, midi_messages=messages)
            log.info(f"[VST] VST-Rendering erfolgreich für {midi_pfad}.")
        except Exception as e:
            log.warning(f"VST-Rendering fehlgeschlagen: {e}. Fallback auf Standard-Synthese...")
            audio = None

    # 2. Fluidsynth-Rendering versuchen (priorisiert soundfont_renderer)
    if audio is None:
        try:
            if os.path.exists(soundfont_pfad):
                log.info(f"[FluidSynth] Rendere {os.path.basename(midi_pfad)} mit soundfont_renderer...")
                # Map instruments to correct channels and set program numbers
                midi_data = soundfont_renderer.prepare_midi_for_soundfont(
                    midi_data,
                    filename_hint=os.path.basename(midi_pfad),
                    instrument_type_hint=instrument_type
                )
                audio_mono = midi_data.fluidsynth(fs=sample_rate, sf2_path=soundfont_pfad)
                
                # Padding oder Abschneiden
                pad_len = num_samples - len(audio_mono)
                if pad_len > 0:
                    audio_mono = np.pad(audio_mono, (0, pad_len), mode='constant')
                else:
                    audio_mono = audio_mono[:num_samples]
                
                audio = np.vstack((audio_mono, audio_mono)).astype(np.float32)
            else:
                raise FileNotFoundError(f"SoundFont nicht gefunden unter {soundfont_pfad}")
        except Exception as e:
            log.warning(f"Fluidsynth-Rendering via soundfont_renderer failed: {e}. Fallback auf basic synthesis...")
            audio = None

    # 3. Fallback auf pretty_midi.synthesize() + Chorus & Reverb Pedalboard
    if audio is None:
        audio_mono = midi_data.synthesize(fs=sample_rate)
        pad_len = num_samples - len(audio_mono)
        if pad_len > 0:
            audio_mono = np.pad(audio_mono, (0, pad_len), mode='constant')
        else:
            audio_mono = audio_mono[:num_samples]
            
        audio = np.vstack((audio_mono, audio_mono)).astype(np.float32)
        
        board = Pedalboard([
            Chorus(rate_hz=1.5, depth=0.2, centre_delay_ms=7.0, mix=0.4),
            Reverb(room_size=0.6, damping=0.5, wet_level=0.3, dry_level=0.8)
        ])
        audio = board(audio, sample_rate=sample_rate)
        
    # Normalisieren und Skalieren
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.7  # Headroom

    sf.write(wav_pfad, audio.T, sample_rate)
    log.info(f"Konvertiert: {midi_pfad} -> {wav_pfad}")


def lade_und_padde(pfad: str, ziel_samples: int) -> np.ndarray:
    if not os.path.exists(pfad):
        return np.zeros((2, ziel_samples), dtype=np.float32)
    data, sr = sf.read(pfad, always_2d=True)
    data = data.T  # Shape: (channels, samples)
    if data.shape[0] == 1:
        data = np.vstack((data, data))
    
    samples = data.shape[1]
    if samples < ziel_samples:
        data = np.pad(data, ((0, 0), (0, ziel_samples - samples)), mode='constant')
    elif samples > ziel_samples:
        data = data[:, :ziel_samples]
    return data.astype(np.float32)

JPOP_MIX_LEVELS = {
    "drums":   0.85,
    "bass":    0.78,
    "piano":   0.55,
    "guitar":  0.50,
    "strings": 0.45,
    "synth":   0.60,
    "brass":   0.40,
    "vocals":  1.00,
    "melody":  0.65,
}

def apply_stereo_pan(audio: np.ndarray, pan: float) -> np.ndarray:
    """pan = -1.0 (links) bis +1.0 (rechts)"""
    left_gain = np.sqrt(0.5 * (1.0 - pan))
    right_gain = np.sqrt(0.5 * (1.0 + pan))
    result = audio.copy()
    result[0] *= left_gain
    result[1] *= right_gain
    return result

def apply_kick_sidechain(bass_audio: np.ndarray, drum_audio: np.ndarray, 
                          sample_rate: int, 
                          threshold: float = 0.3, 
                          duck_amount: float = 0.6,
                          release_ms: float = 80.0) -> np.ndarray:
    release_samples = int(release_ms / 1000.0 * sample_rate)
    mono_drums = np.mean(drum_audio, axis=0)
    
    envelope = np.zeros(len(mono_drums))
    for i in range(len(mono_drums)):
        if abs(mono_drums[i]) > threshold:
            envelope[i] = 1.0
        elif i > 0:
            envelope[i] = envelope[i-1] * (1.0 - 1.0/release_samples)
    
    gain = 1.0 - (envelope * (1.0 - duck_amount))
    
    bass_ducked = bass_audio.copy()
    bass_ducked[0] *= gain
    bass_ducked[1] *= gain
    return bass_ducked

def get_jpop_mix_multiplier(name: str) -> float:
    name_lower = name.lower()
    if "drum" in name_lower or "beat" in name_lower:
        return JPOP_MIX_LEVELS["drums"]
    elif "bass" in name_lower:
        return JPOP_MIX_LEVELS["bass"]
    elif "piano" in name_lower:
        return JPOP_MIX_LEVELS["piano"]
    elif "guitar" in name_lower:
        return JPOP_MIX_LEVELS["guitar"]
    elif "strings" in name_lower:
        return JPOP_MIX_LEVELS["strings"]
    elif "synth" in name_lower:
        return JPOP_MIX_LEVELS["synth"]
    elif "brass" in name_lower:
        return JPOP_MIX_LEVELS["brass"]
    elif "vocal" in name_lower or "stimme" in name_lower:
        return JPOP_MIX_LEVELS["vocals"]
    elif "melody" in name_lower:
        return JPOP_MIX_LEVELS["melody"]
    return 1.0

def mische_spuren(
    spur_pfade: list,
    lautstaerken: list,
    output_pfad: str,
    volumes: dict = None,
    panning: dict = None,
    mutes: dict = None,
    solos: dict = None,
    compressor_threshold: float = -20.0,
    compressor_ratio: float = 2.0,
    limiter_threshold: float = -0.3
) -> None:
    """
    Professioneller Mixdown mit Pedalboard (Studio-Qualität):
    - Spezifische Effekte (HighpassFilter, PeakFilter, Compressor, Reverb) pro Track.
    - Saubere Summierung mit Misch-Gains und J-Pop Volume Calibration.
    - Mastering-Chain auf dem finalen Mix.
    """
    sample_rate = 44100
    
    # 1. Ermittle maximale Länge
    max_samples = 0
    valid_paths = []
    for pfad in spur_pfade:
        if os.path.exists(pfad):
            info = sf.info(pfad)
            if info.frames > max_samples:
                max_samples = info.frames
            valid_paths.append(pfad)
            
    if max_samples == 0:
        log.error("Kein Mix erstellt – keine Spuren geladen.")
        return

    # Check if any track is soloed
    any_solo = False
    if solos:
        for k, v in solos.items():
            if v:
                any_solo = True
                break

    # 2. Spuren laden, kalibrieren, und auf exakt gleiche Länge bringen
    tracks = {}
    for pfad, vol in zip(spur_pfade, lautstaerken):
        name = os.path.basename(pfad)
        if pfad in valid_paths:
            audio = lade_und_padde(pfad, max_samples)
            # Gain mit J-Pop Mix Level kalibrieren
            mult = get_jpop_mix_multiplier(name)
            
            # Map name to instrument key
            inst_key = name.replace(".wav", "").lower()
            if "beat" in inst_key:
                inst_key = "drums"
            
            # Determine volume from visual faders if provided
            current_vol = vol
            if volumes and inst_key in volumes:
                current_vol = volumes[inst_key]
                
            # Determine if track is muted or soloed
            is_audible = True
            if any_solo:
                is_audible = bool(solos.get(inst_key, False))
            if mutes and mutes.get(inst_key, False):
                is_audible = False
                
            multiplier = (current_vol * mult) if is_audible else 0.0
            audio *= multiplier
            tracks[name] = audio

    # 3. Track-spezifische Effekte anwenden
    for name, audio in tracks.items():
        name_lower = name.lower()
        effects = []
        
        if "drum" in name_lower or "beat" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=40),
                Compressor(threshold_db=-15.0, ratio=3.0, attack_ms=10.0, release_ms=100.0)
            ])
        elif "bass" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=28),  # Nur Sub-Rumble unter 28Hz entfernen
                LowShelfFilter(cutoff_frequency_hz=80, gain_db=2.0),  # Bass-Boost
                Compressor(threshold_db=-16.0, ratio=3.5, attack_ms=5.0, release_ms=100.0),
                PeakFilter(cutoff_frequency_hz=180, gain_db=3.0, q=1.5)  # Punch
            ])
        elif "piano" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=80),
                PeakFilter(cutoff_frequency_hz=2000, gain_db=-2.0, q=0.7),
                Reverb(room_size=0.6, damping=0.5, wet_level=0.15, dry_level=0.85)
            ])
        elif "guitar" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=100),
                PeakFilter(cutoff_frequency_hz=3000, gain_db=-3.0, q=1.0),
                Reverb(room_size=0.5, damping=0.5, wet_level=0.12, dry_level=0.88)
            ])
        elif "strings" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=120),
                Reverb(room_size=0.8, damping=0.4, wet_level=0.25, dry_level=0.75)
            ])
        elif "synth" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=150),
                PeakFilter(cutoff_frequency_hz=2500, gain_db=-3.0, q=1.0),
                Reverb(room_size=0.7, damping=0.5, wet_level=0.2, dry_level=0.8)
            ])
        elif "brass" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=110),
                PeakFilter(cutoff_frequency_hz=3500, gain_db=-2.0, q=1.0),
                Reverb(room_size=0.6, damping=0.5, wet_level=0.15, dry_level=0.85)
            ])
        elif "vocals" in name_lower or "stimme" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=120),
                PeakFilter(cutoff_frequency_hz=3500, gain_db=3.0, q=1.0),
                Compressor(threshold_db=-18.0, ratio=4.0, attack_ms=3.0, release_ms=50.0),
                Reverb(room_size=0.7, damping=0.3, wet_level=0.18, dry_level=0.9)
            ])
        elif "melody" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=150),
                PeakFilter(cutoff_frequency_hz=3000, gain_db=-4.0, q=1.0),
                Reverb(room_size=0.7, damping=0.6, wet_level=0.20, dry_level=0.85)
            ])
        elif "chord" in name_lower:
            effects.extend([
                HighpassFilter(cutoff_frequency_hz=100),
                PeakFilter(cutoff_frequency_hz=2500, gain_db=-5.0, q=0.7),
                Reverb(room_size=0.6, damping=0.5, wet_level=0.15, dry_level=0.85)
            ])
        
        if effects:
            board = Pedalboard(effects)
            audio = board(audio, sample_rate)

        # Stereo Panning Schema
        inst_key = name.replace(".wav", "").lower()
        if "beat" in inst_key:
            inst_key = "drums"
            
        if panning and inst_key in panning:
            pan_val = panning[inst_key]
            audio = apply_stereo_pan(audio, pan_val)
        else:
            # Fallback to default panning schema
            if "drum" in name_lower or "beat" in name_lower:
                audio = apply_stereo_pan(audio, 0.0)
            elif "bass" in name_lower:
                audio = apply_stereo_pan(audio, 0.0)
            elif "vocals" in name_lower or "stimme" in name_lower:
                audio = apply_stereo_pan(audio, 0.0)
            elif "piano" in name_lower:
                audio = apply_stereo_pan(audio, -0.25)
            elif "guitar" in name_lower:
                audio = apply_stereo_pan(audio, 0.30)
            elif "strings" in name_lower:
                # split-pan left -0.40 and right +0.40
                left_gain_L = np.sqrt(0.5 * (1.0 - (-0.40)))
                right_gain_L = np.sqrt(0.5 * (1.0 + (-0.40)))
                left_gain_R = np.sqrt(0.5 * (1.0 - (0.40)))
                right_gain_R = np.sqrt(0.5 * (1.0 + (0.40)))
                new_left = audio[0] * left_gain_L + audio[1] * left_gain_R
                new_right = audio[0] * right_gain_L + audio[1] * right_gain_R
                audio = np.vstack((new_left, new_right))
            elif "synth" in name_lower:
                # Haas effect (no additional panning)
                pass
            elif "brass" in name_lower:
                audio = apply_stereo_pan(audio, 0.20)
            elif "melody" in name_lower:
                audio = apply_stereo_pan(audio, -0.15)

        tracks[name] = audio

    # 4. Sidechain-Kompression: Bass an Drums/Beat ducken
    drum_key = None
    bass_key = None
    for k in tracks.keys():
        k_lower = k.lower()
        if "drum" in k_lower or "beat" in k_lower:
            drum_key = k
        elif "bass" in k_lower:
            bass_key = k

    if drum_key and bass_key:
        log.info(f"[Sidechain] Ducke Bass ({bass_key}) zu Drums ({drum_key})...")
        tracks[bass_key] = apply_kick_sidechain(tracks[bass_key], tracks[drum_key], sample_rate)

    # 5. Summe bilden
    final_mix = np.zeros((2, max_samples), dtype=np.float32)
    for audio in tracks.values():
        final_mix += audio

    # 6. Mastering Chain
    log.info("Wende Mastering an...")
    final_mix *= 0.30  # Headroom
    
    master_board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=22),
        Compressor(threshold_db=compressor_threshold, ratio=compressor_ratio, attack_ms=30.0, release_ms=200.0),
        PeakFilter(cutoff_frequency_hz=200, gain_db=1.5, q=0.5),
        PeakFilter(cutoff_frequency_hz=3500, gain_db=1.0, q=0.8),
        PeakFilter(cutoff_frequency_hz=10000, gain_db=0.8, q=1.0),
        Gain(gain_db=6.0),
        Limiter(threshold_db=limiter_threshold)
    ])
    
    final_mix = master_board(final_mix, sample_rate)
    
    # Export
    sf.write(output_pfad, final_mix.T, sample_rate)
    log.info(f"[OK] Professioneller Mix: {output_pfad}")
