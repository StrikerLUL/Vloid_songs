# strings_generator.py - Modular Strings Generator
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

def voice_strings_chord(root_name: str, chord_type: str) -> list:
    """
    Voices chord notes in the string ensemble range (octaves 4 and 5, i.e. MIDI 60 to 83).
    """
    offset = _NOTE_OFFSETS.get(root_name, 0)
    root_midi = 60 + offset  # Octave 4
    intervals = _CHORD_INTERVALS.get(chord_type, [0, 4, 7])
    pitches = []
    for interval in intervals:
        p = root_midi + interval
        while p < 48:
            p += 12
        while p > 83:
            p -= 12
        if p not in pitches:
            pitches.append(p)
    pitches.sort()
    return pitches

def generate_strings(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates string notes simulating legato bowing, pizzicato runs, or crescendos.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    total_bars = len(progression)
    total_duration = total_bars * bar_dur
    
    for bar_idx, chord in enumerate(progression):
        root_name, chord_type = chord
        bar_start = start_time + bar_idx * bar_dur
        pitches = voice_strings_chord(root_name, chord_type)
        
        if pattern_type == "legato":
            # Sustained pads with legato bowing overlap of 20-50ms
            overlap = random.uniform(0.020, 0.050) if bar_idx < total_bars - 1 else 0.0
            dur = bar_dur + overlap
            
            # Use top 3 pitches
            pad_pitches = pitches[:3]
            for p in pad_pitches:
                notes.append(pretty_midi.Note(
                    velocity=65,
                    pitch=p,
                    start=bar_start,
                    end=bar_start + dur
                ))
                
        elif pattern_type == "pizzicato":
            # Short 8th runs
            for i in range(8):
                t = bar_start + i * (beat_dur * 0.5)
                # Short duration (pizzicato)
                dur = beat_dur * 0.2
                p_idx = i % len(pitches)
                p = pitches[p_idx]
                notes.append(pretty_midi.Note(
                    velocity=random.randint(70, 85),
                    pitch=p,
                    start=t,
                    end=t + dur
                ))
                
        elif pattern_type == "build":
            # Sustained pads with crescendo volume slope
            overlap = random.uniform(0.020, 0.050) if bar_idx < total_bars - 1 else 0.0
            dur = bar_dur + overlap
            
            # Calculate volume build-up
            pad_pitches = pitches[:3]
            for p in pad_pitches:
                # Calculate relative position in entire section
                rel_pos = (bar_start - start_time) / total_duration
                # Linearly ramp velocity from 40 to 105
                vel = int(40 + rel_pos * (105 - 40))
                notes.append(pretty_midi.Note(
                    velocity=vel,
                    pitch=p,
                    start=bar_start,
                    end=bar_start + dur
                ))
        else:
            # Fallback simple pad
            for p in pitches[:3]:
                notes.append(pretty_midi.Note(
                    velocity=60,
                    pitch=p,
                    start=bar_start,
                    end=bar_start + bar_dur * 0.95
                ))

    # Apply humanizer
    humanize_notes(notes, genre=genre, instrument_type="strings", bpm=bpm)
    return notes
