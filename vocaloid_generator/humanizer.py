# humanizer.py - Humanizer Utility for J-Pop, Rock, EDM, and Lo-Fi
import pretty_midi
import random

def humanize_note(note: pretty_midi.Note, genre: str, instrument_type: str, bpm: float, swing: float = None, jitter_scale: float = 1.0) -> pretty_midi.Note:
    """
    Applies timing offsets, velocity randomization, swing, and pocket shift
    to a pretty_midi.Note object based on the genre and instrument type.
    jitter_scale multiplies the genre's micro-timing jitter (0 = on the grid, 1 = genre default).
    """
    genre_lower = genre.lower()
    inst_lower = instrument_type.lower()
    
    # 1. Swing Delay Logic
    beat_duration = 60.0 / bpm
    pos_in_beat = (note.start / beat_duration) % 1.0
    
    if 0.4 <= pos_in_beat <= 0.6:
        if swing is not None:
            actual_swing = swing
        else:
            if "j-pop" in genre_lower or "jpop" in genre_lower:
                actual_swing = 0.08
            elif "lo-fi" in genre_lower or "lofi" in genre_lower:
                actual_swing = 0.20
            elif "edm" in genre_lower:
                actual_swing = 0.0
            else:
                actual_swing = 0.0
        
        swing_delay = actual_swing * (beat_duration * 0.5)
        note.start += swing_delay
        note.end += swing_delay

    # 2. Pocket Shift (no pocket shifts for vocal or melody)
    pocket_shift = 0.0
    if inst_lower not in ("vocal", "melody"):
        if "rock" in genre_lower:
            if "bass" in inst_lower or "drum" in inst_lower:
                pocket_shift = 0.015
        elif "lo-fi" in genre_lower or "lofi" in genre_lower:
            if "piano" in inst_lower or "bass" in inst_lower:
                pocket_shift = 0.020
            
    note.start += pocket_shift
    note.end += pocket_shift

    # 3. Jitter (Micro-timing variation)
    if inst_lower in ("vocal", "melody"):
        jitter = random.uniform(-0.002, 0.002)
    elif "j-pop" in genre_lower or "jpop" in genre_lower:
        jitter = random.uniform(-0.003, 0.003)
    elif "rock" in genre_lower:
        jitter = random.uniform(-0.010, 0.010)
    elif "edm" in genre_lower:
        jitter = 0.0
    elif "lo-fi" in genre_lower or "lofi" in genre_lower:
        jitter = random.uniform(-0.015, 0.025)
    else:
        jitter = 0.0
    jitter *= jitter_scale

    note.start += jitter
    note.end += jitter

    if note.start < 0:
        note.start = 0.0
    if note.end <= note.start:
        note.end = note.start + 0.05

    # 4. Velocity Randomization
    if "j-pop" in genre_lower or "jpop" in genre_lower:
        base_vel = random.randint(98, 115)
        var = 4
    elif "rock" in genre_lower:
        base_vel = random.randint(100, 120)
        var = 12
    elif "edm" in genre_lower:
        base_vel = random.randint(105, 118)
        var = 2
    elif "lo-fi" in genre_lower or "lofi" in genre_lower:
        base_vel = random.randint(55, 75)
        var = 15
    else:
        base_vel = 100
        var = 10
    if inst_lower in ("drums", "drum"):
        new_vel = note.velocity + random.randint(-var, var)
    else:
        new_vel = base_vel + random.randint(-var, var)
    note.velocity = max(1, min(127, new_vel))
    
    return note

def humanize_notes(notes: list, genre: str, instrument_type: str, bpm: float, swing: float = None, jitter_scale: float = 1.0) -> list:
    """
    Applies humanization to a list of pretty_midi.Note objects.
    """
    for note in notes:
        humanize_note(note, genre, instrument_type, bpm, swing, jitter_scale)
        
    inst_type_lower = instrument_type.lower()
    if inst_type_lower in ("melody", "vocal") and notes:
        import math
        notes.sort(key=lambda n: n.start)
        
        phrases = []
        current_phrase = [notes[0]]
        threshold = 0.15
        
        for n in notes[1:]:
            if n.start - current_phrase[-1].end >= threshold:
                phrases.append(current_phrase)
                current_phrase = [n]
            else:
                current_phrase.append(n)
        phrases.append(current_phrase)
        
        for phrase in phrases:
            N = len(phrase)
            if N == 0:
                continue
            
            if inst_type_lower == "vocal":
                rubato_base = random.choice([-1.0, 1.0]) * random.uniform(0.005, 0.015)
            else:  # melody
                rubato_base = random.choice([-1.0, 1.0]) * random.uniform(0.010, 0.030)
            
            for idx, note in enumerate(phrase):
                x = idx / (N - 1) if N > 1 else 0.5
                offset = rubato_base * math.cos(math.pi * x)
                note.start += offset
                note.end += offset
                
                if note.start < 0:
                    note.start = 0.0
                if note.end <= note.start:
                    note.end = note.start + 0.05
                
                vel_mult = 0.8 + 0.35 * math.sin(math.pi * x)
                note.velocity = max(1, min(127, int(note.velocity * vel_mult)))
                
    return notes

def humanize_ensemble(tracks: dict, genre: str, bpm: float, swing: float = None, jitter_scale: float = 1.0) -> dict:
    # 1. Humanize "drums" track first via humanize_notes
    if "drums" in tracks and tracks["drums"]:
        humanize_notes(tracks["drums"], genre, "drums", bpm, swing, jitter_scale)
        drum_starts = [n.start for n in tracks["drums"]]
    else:
        drum_starts = []
    
    # 2. For other tracks (specifically "piano", "bass", "guitar", "strings", and "brass"), if drum notes exist:
    target_tracks = ["piano", "bass", "guitar", "strings", "brass"]
    for track_name in target_tracks:
        if track_name in tracks and tracks[track_name]:
            notes = tracks[track_name]
            humanize_notes(notes, genre, track_name, bpm, swing, jitter_scale)
            
            if drum_starts:
                for note in notes:
                    closest_drum_start = min(drum_starts, key=lambda d_start: abs(note.start - d_start))
                    if abs(note.start - closest_drum_start) < 0.100:
                        if track_name in ["bass", "guitar"]:
                            jitter = random.uniform(-0.002, 0.002) * jitter_scale
                        else:  # piano, strings, brass
                            jitter = random.uniform(-0.005, 0.005) * jitter_scale
                        
                        note_dur = note.end - note.start
                        note.start = closest_drum_start + jitter
                        if note.start < 0:
                            note.start = 0.0
                        note.end = note.start + note_dur
                        if note.end <= note.start:
                            note.end = note.start + 0.05
                            
    # 3. Also humanize synth track if present
    if "synth" in tracks and tracks["synth"]:
        humanize_notes(tracks["synth"], genre, "synth", bpm, swing, jitter_scale)
        
    return tracks
