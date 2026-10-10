# bass_generator.py - Modular Bass Generator
import pretty_midi
import random
from humanizer import humanize_notes

_NOTE_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
}

def get_bass_pitch(root_name: str, octave: int = 1) -> int:
    """
    Operate in octaves 1 and 2 (MIDI 24 to 47).
    """
    offset = _NOTE_OFFSETS.get(root_name, 0)
    p = 12 * (octave + 1) + offset
    while p < 24:
        p += 12
    while p > 47:
        p -= 12
    return p

def generate_bass(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates bass notes operating in octaves 1 and 2 with chromatic passing tones.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    
    for bar_idx, chord in enumerate(progression):
        root_name, chord_type = chord
        bar_start = start_time + bar_idx * bar_dur
        
        # 1. Determine Chromatic Passing Tone
        next_chord = progression[(bar_idx + 1) % len(progression)]
        next_root_name, _ = next_chord
        
        curr_offset = _NOTE_OFFSETS.get(root_name, 0)
        next_offset = _NOTE_OFFSETS.get(next_root_name, 0)
        
        diff = (next_offset - curr_offset) % 12
        if diff > 6:
            diff -= 12
            
        import config
        has_passing_tone = False if getattr(config, "STRICT_SCALE_LOCKING", False) else (abs(diff) in (2, 3))
        passing_pitch = None
        if has_passing_tone:
            # Shift towards the target
            step = 1 if diff > 0 else -1
            passing_pitch = get_bass_pitch(root_name, octave=1) + step
            
        # Get base pitches
        root_midi = get_bass_pitch(root_name, octave=1)
        fifth_midi = get_bass_pitch(root_name, octave=1) + 7
        octave_midi = get_bass_pitch(root_name, octave=2)
        
        # 2. Build Patterns
        if pattern_type == "root":
            # Sustained root note on beat 1 and 3
            # Beat 1 (offset 0)
            notes.append(pretty_midi.Note(
                velocity=100, pitch=root_midi, start=bar_start, end=bar_start + 1.9 * beat_dur
            ))
            # Beat 3 (offset 2)
            b3_start = bar_start + 2.0 * beat_dur
            b3_end = bar_start + 3.9 * beat_dur
            if has_passing_tone:
                # Shorten to make room for passing tone at beat 3.5
                b3_end = bar_start + 3.5 * beat_dur
                notes.append(pretty_midi.Note(
                    velocity=90, pitch=passing_pitch, start=bar_start + 3.5 * beat_dur, end=bar_start + 4.0 * beat_dur
                ))
            notes.append(pretty_midi.Note(
                velocity=100, pitch=root_midi, start=b3_start, end=b3_end
            ))
            
        elif pattern_type == "driving":
            # Straight 8th notes
            for i in range(8):
                t = bar_start + i * 0.5 * beat_dur
                dur = 0.45 * beat_dur
                
                # Check for passing tone at the final 8th note
                if i == 7 and has_passing_tone:
                    p = passing_pitch
                    vel = 95
                else:
                    # Alternate root and octave/fifth for drive
                    if i in (2, 6):
                        p = fifth_midi
                    elif i in (4,):
                        p = octave_midi
                    else:
                        p = root_midi
                    vel = 105 if i % 2 == 0 else 90
                    
                notes.append(pretty_midi.Note(
                    velocity=vel, pitch=p, start=t, end=t + dur
                ))
                
        elif pattern_type == "sync":
            # Offbeat syncopation
            # Offsets: 0.0, 0.5, 1.5, 2.5, 3.5
            offsets = [0.0, 0.5, 1.5, 2.5, 3.5]
            for idx, off in enumerate(offsets):
                t = bar_start + off * beat_dur
                dur = 0.45 * beat_dur if off != 3.5 else 0.5 * beat_dur
                
                if off == 3.5 and has_passing_tone:
                    p = passing_pitch
                    vel = 90
                else:
                    p = root_midi if idx % 2 == 0 else octave_midi
                    vel = 100 if idx == 0 else 85
                    
                notes.append(pretty_midi.Note(
                    velocity=vel, pitch=p, start=t, end=t + dur
                ))
                
        elif pattern_type == "sub_pulse":
            # Sidechained style sub-bass on offbeats
            # Offsets: 0.5, 1.5, 2.5, 3.5
            offsets = [0.5, 1.5, 2.5, 3.5]
            for off in offsets:
                t = bar_start + off * beat_dur
                dur = 0.45 * beat_dur if off != 3.5 else 0.5 * beat_dur
                
                if off == 3.5 and has_passing_tone:
                    p = passing_pitch
                    vel = 95
                else:
                    p = root_midi
                    vel = 110
                    
                notes.append(pretty_midi.Note(
                    velocity=vel, pitch=p, start=t, end=t + dur
                ))
                
        elif pattern_type == "lazy":
            # Loose/laid back, slightly delayed beats 1 and 3
            # Beat 1 (offset 0.1)
            notes.append(pretty_midi.Note(
                velocity=90, pitch=root_midi, start=bar_start + 0.1 * beat_dur, end=bar_start + 1.8 * beat_dur
            ))
            # Beat 3 (offset 2.1)
            b3_start = bar_start + 2.1 * beat_dur
            b3_end = bar_start + 3.8 * beat_dur
            if has_passing_tone:
                b3_end = bar_start + 3.5 * beat_dur
                notes.append(pretty_midi.Note(
                    velocity=85, pitch=passing_pitch, start=bar_start + 3.5 * beat_dur, end=bar_start + 4.0 * beat_dur
                ))
            notes.append(pretty_midi.Note(
                velocity=90, pitch=root_midi, start=b3_start, end=b3_end
            ))
            
        elif pattern_type == "wobble":
            # Sustained notes with a 2 Hz LFO modulating Filter Cutoff and Expression
            f_lfo = 2.0  # 2 Hz
            t_step = 0.05  # Sample LFO every 50ms
            
            # Generate 2 half notes per bar to have longer sustained notes for wobble
            for step in range(2):
                t_start = bar_start + step * 2.0 * beat_dur
                t_end = t_start + 1.95 * beat_dur
                p = root_midi
                
                note = pretty_midi.Note(
                    velocity=100, pitch=p, start=t_start, end=t_end
                )
                notes.append(note)
                
                # Apply modulation during the note duration
                t_curr = t_start
                note_cc = []
                import math
                while t_curr < t_end:
                    lfo_val = math.sin(2 * math.pi * f_lfo * t_curr)
                    # CC_val(t) = int(65 + 35 * lfo_val)
                    value = int(65 + 35 * lfo_val)
                    value = max(0, min(127, value))
                    
                    note_cc.append(pretty_midi.ControlChange(number=74, value=value, time=t_curr))
                    note_cc.append(pretty_midi.ControlChange(number=11, value=value, time=t_curr))
                    t_curr += t_step
                note.control_changes = note_cc
            
        else:
            # Fallback
            notes.append(pretty_midi.Note(
                velocity=95, pitch=root_midi, start=bar_start, end=bar_start + bar_dur * 0.95
            ))
            
    if getattr(config, "STRICT_SCALE_LOCKING", False):
        scale_intervals = {
            "major":       [0, 2, 4, 5, 7, 9, 11],
            "minor":       [0, 2, 3, 5, 7, 8, 10],
            "dorian":      [0, 2, 3, 5, 7, 9, 10],
            "phrygian":    [0, 1, 3, 5, 7, 8, 10],
            "penta_minor": [0, 3, 5, 7, 10],
            "penta_major": [0, 2, 4, 7, 9],
        }
        intervals = scale_intervals.get(mode, scale_intervals["minor"])
        root_offset = _NOTE_OFFSETS.get(key, 0)
        valid_classes = {(root_offset + interval) % 12 for interval in intervals}
        
        for n in notes:
            if (n.pitch % 12) not in valid_classes:
                adjusted = n.pitch
                for diff in range(1, 12):
                    if ((n.pitch - diff) % 12) in valid_classes:
                        adjusted = n.pitch - diff
                        break
                    if ((n.pitch + diff) % 12) in valid_classes:
                        adjusted = n.pitch + diff
                        break
                n.pitch = adjusted

    # Apply humanizer
    humanize_notes(notes, genre=genre, instrument_type="bass", bpm=bpm)
    return notes
