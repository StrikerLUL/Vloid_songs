# orchestrator.py - Main Arrangement and Genre Orchestrator
import os
import pretty_midi
import random
from config import SONG_TEXT_VERSE, SONG_TEXT_PRECHORUS, SONG_TEXT_CHORUS, SONG_TEXT_BRIDGE, OUTPUT_ORDNER

# Import generators
from guitar_generator import generate_guitar
from bass_generator import generate_bass
from piano_generator import generate_piano
from strings_generator import generate_strings
from synth_generator import generate_synth
from brass_generator import generate_brass
from beat_generator import generiere_beat_sektion
from melody_generator import generiere_melodie_sektion
from humanizer import humanize_notes, humanize_ensemble
from chord_generator import get_progression

def apply_velocity_ramp(notes: list, ramp_type: str, start_time: float, duration: float):
    """
    Ramps note velocities:
    - "fade_in": ramp up from 50% to 100% over first 2 seconds (or half the duration, whichever is smaller).
    - "fade_out": ramp down from 100% to 50% over last 2 seconds.
    """
    if not notes:
        return
    
    ramp_limit = min(2.0, duration / 2.0)
    
    if ramp_type == "fade_in":
        ramp_end = start_time + ramp_limit
        for note in notes:
            if start_time <= note.start < ramp_end:
                fraction = (note.start - start_time) / ramp_limit
                factor = 0.5 + 0.5 * fraction
                note.velocity = max(1, min(127, int(note.velocity * factor)))
                
    elif ramp_type == "fade_out":
        section_end = start_time + duration
        ramp_start = section_end - ramp_limit
        for note in notes:
            if ramp_start <= note.start < section_end:
                fraction = (section_end - note.start) / ramp_limit
                factor = 0.5 + 0.5 * fraction
                note.velocity = max(1, min(127, int(note.velocity * factor)))

def get_transition_chord(prev_chord, next_chord, key, mode, start_time) -> list:
    """
    Generate a short transition note (length of 0.25 quarter note) just before the start_time of the next chord,
    using the root pitch of the next chord in octave 3 or 4. Return it as a list containing a pretty_midi.Note.
    """
    if not next_chord:
        return []
    
    import config
    bpm = getattr(config, "BPM", 120)
    
    if isinstance(next_chord, tuple):
        root_name = next_chord[0]
    else:
        root_name = next_chord
        
    offsets = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
        "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
    }
    offset = offsets.get(root_name, 0)
    pitch = 48 + offset  # octave 3
    
    quarter_note = 60.0 / bpm
    note_len = 0.25 * quarter_note
    
    note_start = start_time - note_len
    note_end = start_time
    
    if note_start < 0:
        return []
        
    note = pretty_midi.Note(
        velocity=90,
        pitch=pitch,
        start=note_start,
        end=note_end
    )
    return [note]

def get_section_key(section_type, occurrence, original_key, original_mode, structure=None):
    """
    Returns the key for a given section. Modulates final Chorus by +1 semitone.
    """
    if structure is None:
        import config
        structure = config.SONG_STRUCTURE
    total_occurrences = structure.count(section_type)
    if section_type == "Chorus" and occurrence == total_occurrences:
        chromatic_keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        norm_map = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        norm_key = norm_map.get(original_key, original_key)
        if norm_key in chromatic_keys:
            idx = chromatic_keys.index(norm_key)
            return chromatic_keys[(idx + 1) % 12]
    return original_key


# Define PATTERN_MAP mapping genre -> section -> instrument -> pattern_type
PATTERN_MAP = {
    "j-pop": {
        "Intro": {"piano": "chords", "bass": "root", "guitar": "chill_riff", "strings": "legato", "synth": "pad", "brass": None},
        "Build-up": {"piano": "stabs", "bass": "driving", "guitar": "strummed", "strings": "build", "synth": "riser", "brass": None},
        "Verse": {"piano": "chords", "bass": "sync", "guitar": "palm_mute", "strings": None, "synth": None, "brass": None},
        "PreChorus": {"piano": "stabs", "bass": "driving", "guitar": "strummed", "strings": "legato", "synth": "staccato_pluck", "brass": None},
        "Chorus": {"piano": "stabs", "bass": "wobble", "guitar": "strummed", "strings": "legato", "synth": "wide_saw", "brass": "stabs"},
        "Bridge": {"piano": "chords", "bass": "root", "guitar": "chill_riff", "strings": "legato", "synth": "pad", "brass": None},
        "Outro": {"piano": "chords", "bass": "root", "guitar": None, "strings": "legato", "synth": "pad", "brass": None},
    },
    "rock": {
        "Intro": {"piano": None, "bass": "driving", "guitar": "strummed", "strings": None, "synth": None, "brass": None},
        "Build-up": {"piano": None, "bass": "driving", "guitar": "strummed", "strings": None, "synth": None, "brass": None},
        "Verse": {"piano": None, "bass": "driving", "guitar": "palm_mute", "strings": None, "synth": None, "brass": None},
        "PreChorus": {"piano": None, "bass": "driving", "guitar": "strummed", "strings": None, "synth": None, "brass": None},
        "Chorus": {"piano": None, "bass": "driving", "guitar": "power_chords", "strings": None, "synth": None, "brass": None},
        "Bridge": {"piano": None, "bass": "lazy", "guitar": "chill_riff", "strings": None, "synth": None, "brass": None},
        "Outro": {"piano": None, "bass": "lazy", "guitar": "power_chords", "strings": None, "synth": None, "brass": None},
    },
    "edm": {
        "Intro": {"piano": None, "bass": None, "guitar": None, "strings": None, "synth": "pad", "brass": None},
        "Build-up": {"piano": None, "bass": None, "guitar": None, "strings": None, "synth": "riser", "brass": None},
        "Verse": {"piano": None, "bass": "sub_pulse", "guitar": None, "strings": None, "synth": "pluck", "brass": None},
        "PreChorus": {"piano": "stabs", "bass": "sub_pulse", "guitar": None, "strings": None, "synth": "staccato_pluck", "brass": None},
        "Chorus": {"piano": "stabs", "bass": "wobble", "guitar": None, "strings": None, "synth": "wide_saw", "brass": None},
        "Bridge": {"piano": "chords", "bass": "root", "guitar": None, "strings": None, "synth": "pad", "brass": None},
        "Outro": {"piano": None, "bass": None, "guitar": None, "strings": None, "synth": "pad", "brass": None},
    },
    "lo-fi": {
        "Intro": {"piano": "jazz_ch", "bass": "lazy", "guitar": None, "strings": None, "synth": "pad", "brass": None},
        "Build-up": {"piano": "jazz_ch", "bass": "lazy", "guitar": None, "strings": None, "synth": "pad", "brass": None},
        "Verse": {"piano": "jazz_ch", "bass": "lazy", "guitar": "chill_riff", "strings": None, "synth": "pad", "brass": None},
        "PreChorus": {"piano": "jazz_ch", "bass": "lazy", "guitar": None, "strings": None, "synth": "pad", "brass": None},
        "Chorus": {"piano": "jazz_ch", "bass": "lazy", "guitar": "chill_riff", "strings": "pizzicato", "synth": "pad", "brass": "accents"},
        "Bridge": {"piano": "jazz_ch", "bass": "lazy", "guitar": None, "strings": "legato", "synth": "pad", "brass": None},
        "Outro": {"piano": "jazz_ch", "bass": "lazy", "guitar": None, "strings": "legato", "synth": "pad", "brass": None},
    }
}

LYRICS_MAP = {
    "Intro": SONG_TEXT_CHORUS,
    "Build-up": SONG_TEXT_CHORUS,
    "Verse": SONG_TEXT_VERSE,
    "PreChorus": SONG_TEXT_PRECHORUS,
    "Chorus": SONG_TEXT_CHORUS,
    "Bridge": SONG_TEXT_BRIDGE,
    "Outro": SONG_TEXT_CHORUS,
}

def save_midi_track(notes: list, program: int, name: str, filename: str, bpm: float, is_drum: bool = False):
    """
    Saves a track to a MIDI file in the output folder.
    """
    os.makedirs(OUTPUT_ORDNER, exist_ok=True)
    filepath = os.path.join(OUTPUT_ORDNER, filename)
    
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
    inst.notes = notes
    for note in notes:
        if hasattr(note, "control_changes"):
            inst.control_changes.extend(note.control_changes)
    inst.control_changes.sort(key=lambda cc: cc.time)
    pm.instruments.append(inst)
    pm.write(filepath)
    print(f"Saved {name} with {len(notes)} notes to {filepath}")

def orchestrate_song(genre: str, bpm: float, structure: list, key: str, mode: str, section_config: dict) -> dict:
    """
    Coordinates instrument generation per section, humanizes all tracks,
    and exports them to separate MIDI files in the output folder.
    """
    print(f"Orchestrating song - Genre: {genre}, BPM: {bpm}, Key: {key}-{mode}")
    
    # 1. Map genre to styles for chord & beat generators
    chord_style_map = {
        "j-pop": "J-Pop Energy",
        "rock": "Rock",
        "edm": "Kawaii Chiptune",
        "lo-fi": "City Pop"
    }
    import config
    chord_style = getattr(config, "CHORD_STYLE", chord_style_map.get(genre.lower(), "J-Pop Energy"))
    
    beat_style_map = {
        "j-pop": "J-Pop Energy",
        "rock": "Rock",
        "edm": "Kawaii Chiptune",
        "lo-fi": "Ballade"
    }
    beat_style = beat_style_map.get(genre.lower(), "J-Pop Energy")
    
    # Accumulated notes for each track
    tracks = {
        "piano": [],
        "bass": [],
        "guitar": [],
        "strings": [],
        "synth": [],
        "brass": [],
        "drums": [],
        "melody": []
    }
    
    gesamte_melodie_daten = []
    gesamte_silben = []
    
    start_time = 0.0
    viertel_dauer = 60.0 / bpm
    bar_duration = 4 * viertel_dauer
    
    all_chords = []
    section_roots = []
    section_counts = {}
    second_verse_start = None
    second_verse_end = None
    sections_timeline = []
    
    ALLOWED_INSTRUMENTS = {
        "Intro":     ["piano", "bass"],
        "Outro":     ["piano", "bass"],
        "Verse":     ["piano", "bass", "guitar", "drums"],
        "PreChorus": ["piano", "bass", "guitar", "strings", "drums"],
        "Chorus":    ["piano", "bass", "guitar", "strings", "synth", "brass", "drums"],
        "Bridge":    ["piano", "bass", "strings"],
        "Drop":      ["bass", "drums"],
    }
    
    for section_idx, section_type in enumerate(structure):
        config_sect = section_config.get(section_type, {"bars": 4, "has_vocals": True})
        bars = config_sect.get("bars", 4)
        has_vocals = config_sect.get("has_vocals", True)
        
        # Track occurrence counts
        section_counts[section_type] = section_counts.get(section_type, 0) + 1
        occurrence = section_counts[section_type]
        
        # Determine modulated key for this section
        sec_key = get_section_key(section_type, occurrence, key, mode, structure=structure)
        
        # Track timeline for scale locking and velocity post-processing
        sections_timeline.append({
            "section_type": section_type,
            "start": start_time,
            "end": start_time + bars * bar_duration,
            "idx": section_idx,
            "key": sec_key,
            "mode": mode
        })
        
        if section_type == "Verse" and occurrence == 2:
            second_verse_start = start_time
            second_verse_end = start_time + bars * bar_duration

        # Get and wrap/slice chord progression
        previous_roots = section_roots[-1]["roots"] if section_roots else None
        progression = None
        for attempt in range(10):
            prog = get_progression(section_type, sec_key, mode, chord_style)
            if genre.lower() == "j-pop":
                if section_type == "Chorus":
                    prog = get_progression(section_type, sec_key, mode, "dramatic minor" if mode == "minor" else "royal road j-pop")
                elif section_type == "PreChorus":
                    prog = get_progression(section_type, sec_key, mode, "rising pre-chorus")
                elif section_type == "Verse":
                    prog = get_progression(section_type, sec_key, mode, "emotional descend" if mode == "minor" else "bittersweet")
                elif section_type == "Bridge":
                    prog = get_progression(section_type, sec_key, mode, "wagyoku/japanese-modal" if mode == "minor" else "bittersweet")
            
            roots = [r for r, _ in prog]
            if previous_roots is None or roots != previous_roots or attempt == 9:
                progression = prog
                break

        from chord_generator import get_progression_roots
        section_roots.append({
            "section_idx": section_idx,
            "type": section_type,
            "roots": get_progression_roots(progression)
        })

        progression = progression * (bars // len(progression) + 1)
        progression = progression[:bars]
        
        # Resolve pattern map config for current genre and section
        genre_lower = genre.lower()
        if genre_lower not in PATTERN_MAP:
            genre_lower = "j-pop"
        genre_config = PATTERN_MAP[genre_lower]
        
        # Sektionen aus dem Config-Dictionary holen
        sect_key = section_type
        # Falls Sektionstyp nicht vorhanden, passenden Standard oder existierende Sektion wählen
        if sect_key not in genre_config:
            if section_type == "Build-up" and "Verse" in genre_config:
                sect_key = "Verse"
            elif section_type == "PreChorus" and "Verse" in genre_config:
                sect_key = "Verse"
            else:
                sect_key = "Verse" if "Verse" in genre_config else list(genre_config.keys())[0]
        sect_patterns = genre_config[sect_key]
        
        # Get allowed instruments based on density mapping
        allowed = ALLOWED_INSTRUMENTS.get(section_type, ["piano", "bass", "guitar", "strings", "synth", "brass", "drums"])
        
        # Generate modular instruments
        # 1. Piano
        p_pattern = sect_patterns.get("piano")
        if p_pattern and "piano" in allowed:
            tracks["piano"].extend(generate_piano(progression, p_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 2. Bass
        b_pattern = sect_patterns.get("bass")
        if b_pattern and "bass" in allowed:
            tracks["bass"].extend(generate_bass(progression, b_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 3. Guitar
        g_pattern = sect_patterns.get("guitar")
        if g_pattern and "guitar" in allowed:
            tracks["guitar"].extend(generate_guitar(progression, g_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 4. Strings
        s_pattern = sect_patterns.get("strings")
        if s_pattern and "strings" in allowed:
            tracks["strings"].extend(generate_strings(progression, s_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 5. Synth
        syn_pattern = sect_patterns.get("synth")
        if syn_pattern and "synth" in allowed:
            tracks["synth"].extend(generate_synth(progression, syn_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 6. Brass
        br_pattern = sect_patterns.get("brass")
        if br_pattern and "brass" in allowed:
            tracks["brass"].extend(generate_brass(progression, br_pattern, section_type, bpm, sec_key, mode, start_time, genre))
            
        # 7. Drums (beat_generator)
        if "drums" in allowed:
            next_sect = structure[section_idx + 1] if section_idx + 1 < len(structure) else None
            transition_to_chorus = (next_sect == "Chorus")
            drum_notes = generiere_beat_sektion(bpm, bars, section_type, start_time, swing=0.0, style=beat_style, transition_to_chorus=transition_to_chorus)
            humanize_notes(drum_notes, genre=genre, instrument_type="drums", bpm=bpm)
            tracks["drums"].extend(drum_notes)
        
        # Retrieve section energy from config
        import config
        base_energy = getattr(config, "ENERGY_CURVE", {}).get(section_type, "Normal")
        section_energy = base_energy
        if section_type == "Verse" and occurrence == 2:
            section_energy = "Niedrig"

        # 8. Melody
        if has_vocals:
            lyrics = LYRICS_MAP.get(section_type, SONG_TEXT_VERSE)
            import config
            lyrics_kana = getattr(config, "SONG_TEXT_KANA_MAP", {}).get(lyrics, lyrics)
            silben = lyrics_kana.split()
            mel_notes, sec_mel_daten, _ = generiere_melodie_sektion(
                bpm, silben, section_type, start_time, energy=section_energy, key=sec_key, mode=mode, swing=0.0, style=beat_style
            )
            humanize_notes(mel_notes, genre=genre, instrument_type="melody", bpm=bpm)
            tracks["melody"].extend(mel_notes)
            gesamte_melodie_daten.extend(sec_mel_daten)
            gesamte_silben.extend(silben)
            
        for bar_idx in range(bars):
            chord_start = start_time + bar_idx * bar_duration
            all_chords.append((progression[bar_idx], chord_start))
            
        start_time += bars * bar_duration

    # Central Scale Locking & Central Humanization
    import config
    scale_locked = getattr(config, "STRICT_SCALE_LOCKING", False)
    
    if scale_locked:
        scale_intervals = {
            "major":       [0, 2, 4, 5, 7, 9, 11],
            "minor":       [0, 2, 3, 5, 7, 8, 10],
            "dorian":      [0, 2, 3, 5, 7, 9, 10],
            "phrygian":    [0, 1, 3, 5, 7, 8, 10],
            "penta_minor": [0, 3, 5, 7, 10],
            "penta_major": [0, 2, 4, 7, 9],
        }
        
        # Resolve key offset
        key_offsets = {
            "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
            "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
        }
        
        for track_name, notes in tracks.items():
            if track_name in ("drums", "silben", "melody_data", "section_roots") or not notes:
                continue
            for n in notes:
                # Find closest section in timeline
                sec = min(sections_timeline, key=lambda s: abs(n.start - (s["start"] + s["end"]) / 2))
                sec_intervals = scale_intervals.get(sec["mode"], scale_intervals["minor"])
                sec_root_offset = key_offsets.get(sec["key"], 0)
                sec_valid_classes = {(sec_root_offset + interval) % 12 for interval in sec_intervals}
                
                if (n.pitch % 12) not in sec_valid_classes:
                    adjusted = n.pitch
                    for diff in range(1, 12):
                        if ((n.pitch - diff) % 12) in sec_valid_classes:
                            adjusted = n.pitch - diff
                            break
                        if ((n.pitch + diff) % 12) in sec_valid_classes:
                            adjusted = n.pitch + diff
                            break
                    n.pitch = adjusted

    # Add transition notes
    for i in range(1, len(all_chords)):
        prev_chord = all_chords[i-1][0]
        next_chord = all_chords[i][0]
        t_boundary = all_chords[i][1]
        
        if tracks["bass"]:
            tracks["bass"].extend(get_transition_chord(prev_chord, next_chord, key, mode, t_boundary))
        if tracks["piano"]:
            t_notes = get_transition_chord(prev_chord, next_chord, key, mode, t_boundary)
            for tn in t_notes:
                tn.pitch += 12  # shift to octave 4
            tracks["piano"].extend(t_notes)
        if tracks["guitar"]:
            t_notes = get_transition_chord(prev_chord, next_chord, key, mode, t_boundary)
            for tn in t_notes:
                tn.pitch += 12  # shift to octave 4
            tracks["guitar"].extend(t_notes)

    # Apply velocity ramps at section boundaries
    for sec in sections_timeline:
        sec_start = sec["start"]
        sec_dur = sec["end"] - sec["start"]
        for track_name in ["piano", "bass", "guitar", "strings", "synth", "brass"]:
            notes = tracks[track_name]
            apply_velocity_ramp(notes, "fade_in", sec_start, sec_dur)
            apply_velocity_ramp(notes, "fade_out", sec_start, sec_dur)

    # Central Humanization of all tracks to guarantee velocity and timing dynamics
    import config
    humanize_ensemble(tracks, genre, bpm, swing=config.SWING)

    # Post-processing: Scale velocity down by 25% for the second Verse
    if second_verse_start is not None and second_verse_end is not None:
        for track_name, note_list in tracks.items():
            if track_name in ("silben", "melody_data", "section_roots"):
                continue
            for note in note_list:
                if second_verse_start <= note.start < second_verse_end:
                    note.velocity = max(40, int(note.velocity * 0.75))

    # Apply SECTION_VELOCITY_OFFSETS (including the final Chorus +12 boost)
    SECTION_VELOCITY_OFFSETS = {
        "Intro": -15,
        "Outro": -15,
        "Verse": -10,
        "Bridge": -10,
        "Drop": -10,
        "PreChorus": -5,
        "Build-up": -5,
        "Chorus": 0,
    }
    
    final_chorus_idx = -1
    for idx, sec in enumerate(structure):
        if sec == "Chorus":
            final_chorus_idx = idx

    for track_name, note_list in tracks.items():
        if track_name in ("silben", "melody_data", "section_roots"):
            continue
        for note in note_list:
            # Find closest section in timeline
            sec = min(sections_timeline, key=lambda s: abs(note.start - (s["start"] + s["end"]) / 2))
            offset = SECTION_VELOCITY_OFFSETS.get(sec["section_type"], 0)
            if sec["section_type"] == "Chorus" and sec["idx"] == final_chorus_idx:
                offset += 12
            note.velocity = max(1, min(127, note.velocity + offset))

    # 8. Vocal Synthesizer Synchronization (Reconstruct gesamte_melodie_daten from humanized melody)
    melody_notes = tracks["melody"]
    melody_notes.sort(key=lambda n: n.start)
    
    gesamte_melodie_daten = []
    current_time = 0.0
    quarter_sec = 60.0 / bpm
    for note in melody_notes:
        if note.start > current_time + 0.001:
            gap_sek = note.start - current_time
            gesamte_melodie_daten.append((None, gap_sek / quarter_sec))
            current_time = note.start
        elif note.start < current_time:
            note.start = current_time
            if note.end <= note.start:
                note.end = note.start + 0.05
        
        note_dur_sek = note.end - note.start
        gesamte_melodie_daten.append((note.pitch, note_dur_sek / quarter_sec))
        current_time = note.end

    # Program assignments
    # Bass: J-Pop and EDM use Synth Bass (program 39), others electric fingered bass (program 34)
    bass_prog = 39 if genre.lower() in ("j-pop", "edm") else 34
    
    # Save all tracks to MIDI files
    save_midi_track(tracks["piano"], 0, "Acoustic Grand Piano", "piano.mid", bpm)
    save_midi_track(tracks["bass"], bass_prog, "Bass", "bass.mid", bpm)
    save_midi_track(tracks["guitar"], 27, "Clean Guitar", "guitar.mid", bpm)
    save_midi_track(tracks["strings"], 48, "String Ensemble", "strings.mid", bpm)
    
    # Haas-effect stereo widening for J-Pop/EDM if Chorus is present
    has_chorus = any(sec == "Chorus" for sec in structure)
    if genre.lower() in ("j-pop", "edm") and has_chorus:
        synth_filepath = os.path.join(OUTPUT_ORDNER, "synth.mid")
        pm_wide = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        
        # Left channel instrument (original notes)
        inst_left = pretty_midi.Instrument(program=80, name="Synth Lead Left")
        inst_left.notes = [
            pretty_midi.Note(
                velocity=note.velocity, pitch=note.pitch, start=note.start, end=note.end
            )
            for note in tracks["synth"]
        ]
        # Pan Left (CC 10 = 16)
        inst_left.control_changes.append(pretty_midi.ControlChange(number=10, value=16, time=0.0))
        
        # Right channel instrument (delayed by 12ms = 0.012s, slightly quieter velocity for Haas effect)
        inst_right = pretty_midi.Instrument(program=80, name="Synth Lead Right")
        inst_right.notes = [
            pretty_midi.Note(
                velocity=max(1, note.velocity - 5), pitch=note.pitch, start=note.start + 0.012, end=note.end + 0.012
            )
            for note in tracks["synth"]
        ]
        # Pan Right (CC 10 = 112)
        inst_right.control_changes.append(pretty_midi.ControlChange(number=10, value=112, time=0.0))
        
        pm_wide.instruments.extend([inst_left, inst_right])
        pm_wide.write(synth_filepath)
        print(f"Saved double-tracked Synth Lead (Haas effect) to {synth_filepath}")
    else:
        save_midi_track(tracks["synth"], 80, "Synth Lead", "synth.mid", bpm)
        
    save_midi_track(tracks["brass"], 61, "Brass Section", "brass.mid", bpm)
    save_midi_track(tracks["drums"], 0, "Drums", "drums.mid", bpm, is_drum=True)
    save_midi_track(tracks["melody"], 81, "Melody Synth", "melody.mid", bpm)
    
    tracks["melody_data"] = gesamte_melodie_daten
    tracks["silben"] = gesamte_silben
    tracks["section_roots"] = section_roots
    
    return tracks
