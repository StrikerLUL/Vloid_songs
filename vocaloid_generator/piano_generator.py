# piano_generator.py - Modular Piano Generator
import pretty_midi
import random
from humanizer import humanize_notes

_NOTE_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
}

_CHORD_INTERVALS = {
    "":      [0, 4, 7],
    "m":     [0, 3, 7],
    "7":     [0, 4, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
    "m9":    [0, 3, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "9":     [0, 4, 7, 10, 14],
    "dim":   [0, 3, 6],
    "dim7":  [0, 3, 6, 9],
    "aug":   [0, 4, 8],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "add9":  [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "6":     [0, 4, 7, 9],
    "m6":    [0, 3, 7, 9],
    "11":    [0, 4, 7, 10, 14, 17],
    "m11":   [0, 3, 7, 10, 14, 17],
    "6/9":   [0, 4, 7, 9, 14],
}

def get_inversions(pitch_classes: list, min_midi: int = 60, max_midi: int = 83) -> list:
    """
    Generates standard inversions for the given pitch classes in the range [min_midi, max_midi].
    """
    sorted_classes = sorted(list(set(pitch_classes)))
    n = len(sorted_classes)
    voicings = []
    
    for i in range(n):
        classes_in_order = sorted_classes[i:] + sorted_classes[:i]
        
        for octave in [4, 5]:
            base_pitch = 12 * (octave + 1) + classes_in_order[0]
            if not (min_midi <= base_pitch <= max_midi):
                continue
            
            voicing = [base_pitch]
            current_pitch = base_pitch
            for j in range(1, n):
                cls = classes_in_order[j]
                p = current_pitch + (cls - (current_pitch % 12)) % 12
                if p == current_pitch:
                    p += 12
                voicing.append(p)
                
            if all(min_midi <= p <= max_midi for p in voicing):
                voicings.append(voicing)
                
    return voicings

def voice_leading_distance(v1: list, v2: list) -> float:
    """
    Calculates the voice-leading distance between two voicings.
    """
    if len(v1) == len(v2):
        return sum(abs(a - b) for a, b in zip(v1, v2))
    else:
        c1 = sum(v1) / len(v1)
        c2 = sum(v2) / len(v2)
        return abs(c1 - c2)

def voice_leading_sequence(progression: list, pattern_type: str) -> list:
    """
    Generates a sequence of right-hand voicings that minimize voice-leading distance.
    """
    sequence_voicings = []
    prev_voicing = None
    
    for root_name, chord_type in progression:
        # Determine chord type (extended for jazz chords)
        ctype = chord_type
        if pattern_type == "jazz_ch":
            if chord_type in ("", "maj", "maj7"):
                ctype = "maj9"
            elif chord_type in ("m", "m7"):
                ctype = "m11"
            elif chord_type == "7":
                ctype = "9"
                
        offset = _NOTE_OFFSETS.get(root_name, 0)
        intervals = _CHORD_INTERVALS.get(ctype, [0, 4, 7])
        pitch_classes = [(offset + i) % 12 for i in intervals]
        
        # Get right-hand inversions in octaves 4 and 5 (MIDI 60 to 83)
        inversions = get_inversions(pitch_classes, min_midi=60, max_midi=83)
        
        if not inversions:
            inversions = [[60 + offset, 64 + offset, 67 + offset]]
            
        if prev_voicing is None:
            best_voicing = min(inversions, key=lambda v: abs(sum(v)/len(v) - 71))
        else:
            best_voicing = min(inversions, key=lambda v: voice_leading_distance(v, prev_voicing))
            
        sequence_voicings.append(best_voicing)
        prev_voicing = best_voicing
        
    return sequence_voicings

def generate_piano(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates piano notes with left hand octaves and voice-led right hand chords/arpeggios.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    
    # 1. Compute right hand voicings with optimized voice leading
    rh_voicings = voice_leading_sequence(progression, pattern_type)
    
    for bar_idx, chord in enumerate(progression):
        root_name, chord_type = chord
        bar_start = start_time + bar_idx * bar_dur
        
        # Left Hand (octaves in octave 2-3)
        lh_offset = _NOTE_OFFSETS.get(root_name, 0)
        lh_low = 36 + lh_offset   # Octave 2
        lh_high = 48 + lh_offset  # Octave 3
        
        # Ensure they are in the range [36, 59]
        while lh_low < 36: lh_low += 12
        while lh_low > 47: lh_low -= 12
        while lh_high < 48: lh_high += 12
        while lh_high > 59: lh_high -= 12
        
        rh_pitches = rh_voicings[bar_idx]
        
        if pattern_type in ("chords", "jazz_ch"):
            # Sustained chords on beat 1
            # Left Hand
            notes.append(pretty_midi.Note(velocity=80, pitch=lh_low, start=bar_start, end=bar_start + bar_dur * 0.95))
            notes.append(pretty_midi.Note(velocity=80, pitch=lh_high, start=bar_start, end=bar_start + bar_dur * 0.95))
            # Right Hand
            for p in rh_pitches:
                notes.append(pretty_midi.Note(velocity=85, pitch=p, start=bar_start, end=bar_start + bar_dur * 0.95))
                
        elif pattern_type == "stabs":
            # Syncopated rhythm offsets in 8th notes
            if section_type == "Chorus":
                stab_offsets = [0.0, 1.5, 2.5, 4.0, 5.5, 7.0, 7.5]
            elif section_type == "PreChorus":
                stab_offsets = [0.0, 1.5, 3.0, 4.5, 6.0, 7.0]
            elif section_type == "Verse":
                stab_offsets = [0.0, 2.0, 4.0, 6.0]
            else:
                stab_offsets = [0.0, 4.0]
                
            # Left Hand plays sustained on beat 1 and 3
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_low, start=bar_start, end=bar_start + 1.8 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_high, start=bar_start, end=bar_start + 1.8 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_low, start=bar_start + 2.0 * beat_dur, end=bar_start + 3.8 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_high, start=bar_start + 2.0 * beat_dur, end=bar_start + 3.8 * beat_dur))
            
            # Right Hand plays syncopated stabs
            for off in stab_offsets:
                t = bar_start + off * (beat_dur * 0.5)
                if t >= bar_start + bar_dur:
                    continue
                vel = random.randint(80, 95)
                dur = beat_dur * 0.35
                for p in rh_pitches:
                    notes.append(pretty_midi.Note(velocity=vel, pitch=p, start=t, end=t + dur))
                    
        elif pattern_type == "arpeggio":
            # Flowing 8th notes
            # Left Hand plays sustained octaves on beat 1 and 3
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_low, start=bar_start, end=bar_start + 1.9 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_high, start=bar_start, end=bar_start + 1.9 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_low, start=bar_start + 2.0 * beat_dur, end=bar_start + 3.9 * beat_dur))
            notes.append(pretty_midi.Note(velocity=75, pitch=lh_high, start=bar_start + 2.0 * beat_dur, end=bar_start + 3.9 * beat_dur))
            
            # Right Hand arpeggios
            for idx in range(8):
                t = bar_start + idx * (beat_dur * 0.5)
                p_idx = idx % len(rh_pitches)
                p = rh_pitches[p_idx]
                dur = beat_dur * 0.48
                vel = random.randint(70, 85)
                notes.append(pretty_midi.Note(velocity=vel, pitch=p, start=t, end=t + dur))
                
        else:
            # Fallback simple chords
            notes.append(pretty_midi.Note(velocity=80, pitch=lh_low, start=bar_start, end=bar_start + bar_dur * 0.95))
            notes.append(pretty_midi.Note(velocity=80, pitch=lh_high, start=bar_start, end=bar_start + bar_dur * 0.95))
            for p in rh_pitches:
                notes.append(pretty_midi.Note(velocity=80, pitch=p, start=bar_start, end=bar_start + bar_dur * 0.95))
                
    # Apply humanizer
    humanize_notes(notes, genre=genre, instrument_type="piano", bpm=bpm)
    return notes
