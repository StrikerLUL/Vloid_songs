# guitar_generator.py - Modular Guitar Generator
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

def voice_guitar_chord(root_name: str, chord_type: str) -> list:
    """
    Voices chords in guitar range (octaves 3 and 4, i.e. MIDI 48 to 71).
    """
    offset = _NOTE_OFFSETS.get(root_name, 0)
    root_midi = 48 + offset  # Octave 3
    intervals = _CHORD_INTERVALS.get(chord_type, [0, 4, 7])
    pitches = []
    for interval in intervals:
        p = root_midi + interval
        while p < 48:
            p += 12
        while p > 71:
            p -= 12
        if p not in pitches:
            pitches.append(p)
    pitches.sort()
    return pitches

def apply_strumming_spread(pitches: list, start_time: float, duration: float, velocity: int, direction: str = "down") -> list:
    """
    Applies physical strumming spread: 15-35ms delay between adjacent notes.
    Downstroke: lowest-to-highest pitch.
    Upstroke: highest-to-lowest pitch.
    """
    notes = []
    delay_step = random.uniform(0.015, 0.035)
    ordered_pitches = list(pitches)
    if direction == "up":
        ordered_pitches.reverse()
        
    for idx, p in enumerate(ordered_pitches):
        note_start = start_time + idx * delay_step
        note_end = note_start + duration
        notes.append(pretty_midi.Note(
            velocity=velocity,
            pitch=p,
            start=note_start,
            end=note_end
        ))
    return notes

def generate_guitar(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates guitar notes based on progression and pattern type.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    
    for bar_idx, chord in enumerate(progression):
        root_name, chord_type = chord
        pitches = voice_guitar_chord(root_name, chord_type)
        bar_start = start_time + bar_idx * bar_dur
        
        if pattern_type == "palm_mute":
            # Muted 8th notes, low velocity, short durations
            for i in range(8):
                t = bar_start + i * (beat_dur * 0.5)
                # Palm muting uses the lowest 2-3 notes of the chord
                pm_pitches = pitches[:2] if len(pitches) >= 2 else pitches
                vel = random.randint(45, 60)
                dur = beat_dur * 0.25
                notes.extend(apply_strumming_spread(pm_pitches, t, dur, vel, direction="down"))
                
        elif pattern_type == "power_chords":
            # Sustained root-fifth on beats 1 and 3
            # Root and fifth (or root-fifth-octave)
            pc_pitches = [pitches[0]]
            # Find fifth (7 semitones above root) or next note
            for p in pitches[1:]:
                if (p - pitches[0]) % 12 in (7, 5, 2):  # Power chord intervals
                    pc_pitches.append(p)
                    break
            if len(pc_pitches) < 2 and len(pitches) >= 2:
                pc_pitches.append(pitches[1])
            
            # Beat 1 (offset 0)
            notes.extend(apply_strumming_spread(pc_pitches, bar_start, beat_dur * 1.9, 100, direction="down"))
            # Beat 3 (offset 2)
            notes.extend(apply_strumming_spread(pc_pitches, bar_start + 2 * beat_dur, beat_dur * 1.9, 100, direction="down"))
            
        elif pattern_type == "strummed":
            # 16th-note rhythm strumming pattern
            # Strums defined by: (offset_in_16ths, direction, duration_in_beats)
            strums = [
                (0, "down", 0.5),
                (2, "up", 0.5),
                (4, "down", 0.5),
                (6, "up", 0.25),
                (7, "down", 0.25),
                (8, "down", 0.5),
                (10, "up", 0.5),
                (12, "down", 0.5),
                (14, "up", 0.5)
            ]
            for offset_16, direction, dur_beats in strums:
                t = bar_start + offset_16 * (beat_dur * 0.25)
                vel = random.randint(80, 100)
                notes.extend(apply_strumming_spread(pitches, t, dur_beats * beat_dur, vel, direction=direction))
                
        elif pattern_type == "chill_riff":
            # Arpeggiated pick pattern
            arp_offsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
            for idx, offset_beats in enumerate(arp_offsets):
                t = bar_start + offset_beats * beat_dur
                p_idx = idx % len(pitches)
                p = pitches[p_idx]
                # Let it ring out slightly (duration slightly longer than 8th note)
                dur = beat_dur * 0.7
                vel = random.randint(70, 85)
                notes.append(pretty_midi.Note(
                    velocity=vel,
                    pitch=p,
                    start=t,
                    end=t + dur
                ))
        else:
            # Fallback simple chords on beat 1
            notes.extend(apply_strumming_spread(pitches, bar_start, bar_dur * 0.95, 90, direction="down"))

    # Apply the humanizer to the generated notes
    humanize_notes(notes, genre=genre, instrument_type="guitar", bpm=bpm)
    return notes
