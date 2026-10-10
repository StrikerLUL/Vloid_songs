# synth_generator.py - Modular Synth Generator
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

def voice_synth_chord(root_name: str, chord_type: str, octave: int = 5) -> list:
    """
    Voices chord notes in high synth range (octave 5-6, i.e. MIDI 72 to 95).
    """
    offset = _NOTE_OFFSETS.get(root_name, 0)
    root_midi = 12 * (octave + 1) + offset
    intervals = _CHORD_INTERVALS.get(chord_type, [0, 4, 7])
    pitches = []
    for interval in intervals:
        p = root_midi + interval
        while p < 72:
            p += 12
        while p > 95:
            p -= 12
        if p not in pitches:
            pitches.append(p)
    pitches.sort()
    return pitches

def generate_synth(progression: list, pattern_type: str, section_type: str, bpm: float, key: str, mode: str, start_time: float, genre: str = "J-Pop") -> list:
    """
    Generates synth lines supporting pads, plucks, 16th-note arpeggios, and riser sweeps.
    """
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    notes = []
    total_bars = len(progression)
    
    if pattern_type == "riser":
        # Riser sweep plays upwards pitch-crescendo over the whole section length
        total_steps = total_bars * 16
        start_pitch = 48  # C3
        end_pitch = 96    # C7
        
        for step_idx in range(total_steps):
            t = start_time + step_idx * (beat_dur * 0.25)
            # Calculate pitch
            p = int(start_pitch + (step_idx / total_steps) * (end_pitch - start_pitch))
            # Calculate volume crescendo
            vel = int(45 + (step_idx / total_steps) * (115 - 45))
            dur = beat_dur * 0.22
            notes.append(pretty_midi.Note(
                velocity=vel,
                pitch=p,
                start=t,
                end=t + dur
            ))
            
    else:
        for bar_idx, chord in enumerate(progression):
            root_name, chord_type = chord
            bar_start = start_time + bar_idx * bar_dur
            pitches = voice_synth_chord(root_name, chord_type)
            
            if pattern_type == "pad":
                # Warm sustained chord pad
                for p in pitches[:3]:
                    notes.append(pretty_midi.Note(
                        velocity=60,
                        pitch=p,
                        start=bar_start,
                        end=bar_start + bar_dur * 0.98
                    ))
                    
            elif pattern_type == "pluck":
                # Short retro plucky chords on offbeats of 8th notes
                # Offsets: 0.5, 1.5, 2.5, 3.5 beats
                offsets = [0.5, 1.5, 2.5, 3.5]
                for off in offsets:
                    t = bar_start + off * beat_dur
                    vel = random.randint(85, 100)
                    dur = beat_dur * 0.20
                    for p in pitches[:3]:
                        notes.append(pretty_midi.Note(
                            velocity=vel,
                            pitch=p,
                            start=t,
                            end=t + dur
                        ))
                        
            elif pattern_type == "arp":
                # 16th-note arpeggiator
                arp_seq = pitches + [p + 12 for p in pitches[:2]]
                pattern_map = [0, 2, 1, 3, 0, 2, 4, 3, 1, 3, 2, 4, 0, 1, 2, 3]
                
                for step_idx in range(16):
                    t = bar_start + step_idx * (beat_dur * 0.25)
                    p_idx = pattern_map[step_idx % len(pattern_map)] % len(arp_seq)
                    p = arp_seq[p_idx]
                    dur = beat_dur * 0.18
                    vel = random.randint(70, 85)
                    notes.append(pretty_midi.Note(
                        velocity=vel,
                        pitch=p,
                        start=t,
                        end=t + dur
                    ))
            elif pattern_type == "staccato_pluck":
                # Kawaii short attack/decay plucks in PreChorus
                offsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]  # Rapid 8th notes
                for idx, off in enumerate(offsets):
                    t = bar_start + off * beat_dur
                    dur = max(0.05, min(0.08, beat_dur * 0.15))
                    vel = random.randint(95, 110) if idx % 2 == 0 else random.randint(70, 85)
                    for p in pitches[:2]:
                        notes.append(pretty_midi.Note(
                            velocity=vel,
                            pitch=p,
                            start=t,
                            end=t + dur
                        ))
            elif pattern_type == "wide_saw":
                # Wide saw lead: energetic sustained chords in Chorus
                for p in pitches[:3]:
                    notes.append(pretty_midi.Note(
                        velocity=105,
                        pitch=p,
                        start=bar_start,
                        end=bar_start + bar_dur * 0.98
                    ))
            else:
                # Fallback simple chord stabs on beat 1 and 3
                for off in [0.0, 2.0]:
                    t = bar_start + off * beat_dur
                    for p in pitches[:3]:
                        notes.append(pretty_midi.Note(
                            velocity=75,
                            pitch=p,
                            start=t,
                            end=t + beat_dur * 1.8
                        ))

    # Apply humanizer
    humanize_notes(notes, genre=genre, instrument_type="synth", bpm=bpm)
    return notes
