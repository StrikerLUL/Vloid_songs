# brass_generator.py - Modular Brass Generator
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

def voice_brass_chord(root_name: str, chord_type: str) -> list:
    """
    Voices chord notes in the brass range (octaves 3 and 4, i.e. MIDI 48 to 71).
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

def generate_brass(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates brass notes supporting chord stabs and counter-melodies during vocal pauses.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    
    for bar_idx, chord in enumerate(progression):
        root_name, chord_type = chord
        bar_start = start_time + bar_idx * bar_dur
        pitches = voice_brass_chord(root_name, chord_type)
        
        # Get base pitches
        root_midi = pitches[0]
        fifth_midi = pitches[0] + 7
        octave_midi = pitches[0] + 12
        
        if pattern_type == "stabs":
            # Short chord accents
            # Play brief chords on beat 1, beat 2.5 (upbeat), and beat 4
            offsets = [0.0, 1.5, 3.0]
            for off in offsets:
                t = bar_start + off * beat_dur
                dur = beat_dur * 0.30
                vel = 110  # Loud brass stab
                for p in pitches[:3]:
                    notes.append(pretty_midi.Note(
                        velocity=vel,
                        pitch=p,
                        start=t,
                        end=t + dur
                    ))
                    
        elif pattern_type == "accents":
            # Melodic counter-melodies during vocal pauses
            # Let's say vocal pauses happen in even bars of a section, on beats 3 and 4
            if bar_idx % 2 == 1:
                # Play an ascending run: fifth -> root+12 -> fifth+12 -> root+24
                run_pitches = [fifth_midi, octave_midi, fifth_midi + 12, octave_midi + 12]
                offsets = [2.0, 2.5, 3.0, 3.5]
                
                for idx, off in enumerate(offsets):
                    t = bar_start + off * beat_dur
                    p = run_pitches[idx % len(run_pitches)]
                    dur = beat_dur * 0.40
                    vel = random.randint(95, 110)
                    notes.append(pretty_midi.Note(
                        velocity=vel,
                        pitch=p,
                        start=t,
                        end=t + dur
                    ))
            else:
                # Odd bars: play a single warm sustained chord on beat 1 to support the harmony quietly
                for p in pitches[:3]:
                    notes.append(pretty_midi.Note(
                        velocity=65,
                        pitch=p,
                        start=bar_start,
                        end=bar_start + beat_dur * 1.5
                    ))
        else:
            # Fallback simple accents on beat 1
            for p in pitches[:3]:
                notes.append(pretty_midi.Note(
                    velocity=80,
                    pitch=p,
                    start=bar_start,
                    end=bar_start + beat_dur * 0.9
                ))

    # Apply humanizer
    humanize_notes(notes, genre=genre, instrument_type="brass", bpm=bpm)
    return notes
