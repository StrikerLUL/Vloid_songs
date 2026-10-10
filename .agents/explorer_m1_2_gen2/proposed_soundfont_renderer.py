# proposed_soundfont_renderer.py
# Standalone renderer to convert MIDI files to WAV using FluidSynth and SoundFont.sf2

import os
import sys
import argparse
import pretty_midi
import soundfile as sf
import numpy as np

# Add project root to path to load config
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)
# Also add vocaloid_generator subdirectory
vocaloid_gen_path = os.path.join(project_root, "vocaloid_generator")
if vocaloid_gen_path not in sys.path:
    sys.path.append(vocaloid_gen_path)

try:
    from config import SOUNDFONT_PFAD
except ImportError:
    SOUNDFONT_PFAD = "soundfont.sf2"

def render_midi(midi_path: str, wav_path: str, sf2_path: str = None, instrument_type: str = "piano", sample_rate: int = 44100):
    if sf2_path is None:
        sf2_path = SOUNDFONT_PFAD
        
    print(f"MIDI Path: {midi_path}")
    print(f"WAV Path: {wav_path}")
    print(f"SoundFont Path: {sf2_path}")
    print(f"Instrument Type: {instrument_type}")
    
    if not os.path.exists(midi_path):
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")
    if not os.path.exists(sf2_path):
        raise FileNotFoundError(f"SoundFont not found: {sf2_path}")
        
    # Map instrument type to General MIDI program (0-127)
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

    midi_data = pretty_midi.PrettyMIDI(midi_path)
    duration = midi_data.get_end_time() + 2.0  # 2 seconds ringout
    num_samples = int(duration * sample_rate)

    is_drum = "drum" in inst_type_lower
    for instrument in midi_data.instruments:
        if is_drum:
            instrument.is_drum = True
            instrument.program = 0
        else:
            if not instrument.is_drum:
                instrument.program = program

    print(f"Rendering via FluidSynth...")
    try:
        audio_mono = midi_data.fluidsynth(fs=sample_rate, sf2_path=sf2_path)
        
        # Pad or crop
        pad_len = num_samples - len(audio_mono)
        if pad_len > 0:
            audio_mono = np.pad(audio_mono, (0, pad_len), mode='constant')
        else:
            audio_mono = audio_mono[:num_samples]
            
        audio_stereo = np.vstack((audio_mono, audio_mono)).astype(np.float32)
        
        # Apply standard headroom
        peak = np.max(np.abs(audio_stereo))
        if peak > 0:
            audio_stereo = audio_stereo / peak * 0.7
            
        sf.write(wav_path, audio_stereo.T, sample_rate)
        print(f"[SUCCESS] Rendered to {wav_path}")
        return True
    except Exception as e:
        print(f"[FAIL] FluidSynth rendering failed: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render MIDI to WAV using FluidSynth and SoundFont")
    parser.add_argument("--midi", required=True, help="Path to input MIDI file")
    parser.add_argument("--wav", required=True, help="Path to output WAV file")
    parser.add_argument("--soundfont", default=None, help="Path to SoundFont .sf2 file")
    parser.add_argument("--instrument", default="piano", help="Instrument type (piano, guitar, bass, strings, synth, brass, drums, melody)")
    parser.add_argument("--sr", type=int, default=44100, help="Sample rate (default: 44100)")
    
    args = parser.parse_args()
    try:
        success = render_midi(args.midi, args.wav, args.soundfont, args.instrument, args.sr)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
