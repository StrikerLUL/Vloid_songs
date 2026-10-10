# soundfont_renderer.py – Rendert MIDI-Dateien mit SoundFont via Fluidsynth
import os
import numpy as np
import pretty_midi
import soundfile as sf

# Try importing fluidsynth to check package presence
try:
    import fluidsynth
except ImportError:
    fluidsynth = None

def get_inst_type(inst: pretty_midi.Instrument, filename_hint: str = "") -> str:
    """
    Identifiziert den Instrumententyp basierend auf Name, Dateipfad-Hint oder Program Change.
    """
    name = (inst.name or "").lower()
    hint = filename_hint.lower()
    
    if inst.is_drum or "drum" in name or "beat" in hint or "drum" in hint:
        return "drums"
    if "bass" in name or "bass" in hint:
        return "bass"
    if "piano" in name or "piano" in hint:
        return "piano"
    if "guitar" in name or "guitar" in hint:
        return "guitar"
    if "strings" in name or "strings" in hint:
        return "strings"
    if "synth" in name or "synth" in hint:
        return "synth"
    if "brass" in name or "brass" in hint:
        return "brass"
    if "melody" in name or "melody" in hint:
        return "melody"
    
    p = inst.program
    if 32 <= p <= 39:
        return "bass"
    if 24 <= p <= 31:
        return "guitar"
    if 48 <= p <= 55:
        return "strings"
    if 60 <= p <= 79:
        if 60 <= p <= 63:
            return "brass"
        return "synth"
    if 80 <= p <= 87:
        return "melody"
    return "piano"

def prepare_midi_for_soundfont(midi_data: pretty_midi.PrettyMIDI, filename_hint: str = "", instrument_type_hint: str = None) -> pretty_midi.PrettyMIDI:
    """
    Ordnet die Instrumente in der PrettyMIDI-Instanz so an, dass sie exakt den gewünschten
    MIDI-Kanälen und Program Changes zugeordnet werden:
    Ch0: Piano (Prg 1)
    Ch1: Bass (Prg 33)
    Ch2: Guitar (Prg 25)
    Ch3: Strings (Prg 49)
    Ch4: Synth (Prg 81)
    Ch5: Brass (Prg 62)
    Ch6: Melody (Prg 81)
    Ch7: Synth Haas right / Dummy
    Ch8: Dummy
    Ch9: Drums (Prg 0, is_drum=True)
    Ch10-15: Dummies
    """
    slots = []
    for ch in range(16):
        if ch == 9:
            inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums PlaceHolder")
        else:
            prog = 1
            if ch == 0: prog = 1
            elif ch == 1: prog = 33
            elif ch == 2: prog = 25
            elif ch == 3: prog = 49
            elif ch == 4: prog = 81
            elif ch == 5: prog = 62
            elif ch == 6: prog = 81
            elif ch == 7: prog = 81
            inst = pretty_midi.Instrument(program=prog, is_drum=False, name=f"Ch{ch} PlaceHolder")
        slots.append(inst)

    for inst in midi_data.instruments:
        if instrument_type_hint:
            itype = instrument_type_hint.lower()
        else:
            itype = get_inst_type(inst, filename_hint)

        if "drum" in itype:
            ch = 9
            program = 0
            is_drum = True
        elif "bass" in itype:
            ch = 1
            program = 33
            is_drum = False
        elif "piano" in itype:
            ch = 0
            program = 1
            is_drum = False
        elif "guitar" in itype:
            ch = 2
            program = 25
            is_drum = False
        elif "strings" in itype:
            ch = 3
            program = 49
            is_drum = False
        elif "synth" in itype:
            # Check if Ch4 is already taken (Haas right/left)
            if slots[4].notes and not slots[7].notes:
                ch = 7
            else:
                ch = 4
            program = 81
            is_drum = False
        elif "brass" in itype:
            ch = 5
            program = 62
            is_drum = False
        elif "melody" in itype:
            ch = 6
            program = 81
            is_drum = False
        else:
            ch = 0
            program = 1
            is_drum = False

        # Kopiere Noten und Metadaten in das Ziel-Slot
        slots[ch].program = program
        slots[ch].is_drum = is_drum
        slots[ch].notes.extend(inst.notes)
        slots[ch].control_changes.extend(inst.control_changes)
        slots[ch].pitch_bends.extend(inst.pitch_bends)
        if inst.name:
            slots[ch].name = inst.name

    midi_data.instruments = slots
    return midi_data

def render_midi_to_wav(midi_pfad: str, wav_pfad: str, soundfont_pfad: str, instrument_type: str = None, is_drum: bool = False, sample_rate: int = 44100) -> None:
    """
    Rendert eine MIDI-Datei zu einer WAV-Datei unter Verwendung des angegebenen SoundFonts.
    Priorisiert das korrekte Kanal-Mapping und die Program Changes.
    """
    if not os.path.exists(soundfont_pfad):
        raise FileNotFoundError(f"SoundFont nicht gefunden unter: {soundfont_pfad}")
        
    midi_data = pretty_midi.PrettyMIDI(midi_pfad)
    
    # 1. Mapping und Programme zuweisen
    filename_hint = os.path.basename(midi_pfad)
    midi_data = prepare_midi_for_soundfont(midi_data, filename_hint=filename_hint, instrument_type_hint=instrument_type)
    
    # 2. fluidsynth aufrufen
    audio_mono = midi_data.fluidsynth(fs=sample_rate, sf2_path=soundfont_pfad)
    
    # Padding für Ausklang
    duration = midi_data.get_end_time() + 2.0
    num_samples = int(duration * sample_rate)
    pad_len = num_samples - len(audio_mono)
    if pad_len > 0:
        audio_mono = np.pad(audio_mono, (0, pad_len), mode='constant')
    else:
        audio_mono = audio_mono[:num_samples]
        
    audio_stereo = np.vstack((audio_mono, audio_mono)).astype(np.float32)
    
    # Normalisieren mit Headroom
    peak = np.max(np.abs(audio_stereo))
    if peak > 0:
        audio_stereo = audio_stereo / peak * 0.7
        
    sf.write(wav_pfad, audio_stereo.T, sample_rate)
