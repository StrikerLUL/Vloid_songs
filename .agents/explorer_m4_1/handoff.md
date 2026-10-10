# Handoff Report — explorer_m4_1

## 1. Observation

In `vocaloid_generator/config.py` (lines 18–29):
```python
SONG_STRUCTURE = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]

SECTION_CONFIG = {
    "Intro":     {"bars": 4,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 8,  "has_vocals": True},
    "PreChorus": {"bars": 4,  "has_vocals": True},
    "Chorus":    {"bars": 8,  "has_vocals": True},
    "Bridge":    {"bars": 4,  "has_vocals": True},
    "Outro":     {"bars": 4,  "has_vocals": False},
}
```

In `vocaloid_generator/humanizer.py` (lines 96–100):
```python
    if inst_lower in ("drums", "drum"):
        new_vel = note.velocity + random.randint(-var, var)
    else:
        new_vel = base_vel + random.randint(-var, var)
    note.velocity = max(1, min(127, new_vel))
```
*Observation*: Non-drum instrument velocities are completely overwritten with `base_vel` in `humanize_note`, wiping out any velocity adjustments applied before humanization.

In `vocaloid_generator/orchestrator.py` (lines 270–276):
```python
        # Resolve key offset
        key_offsets = {
            "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
            "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
        }
        root_offset = key_offsets.get(key, 0)
        valid_classes = {(root_offset + interval) % 12 for interval in intervals}
```
*Observation*: `STRICT_SCALE_LOCKING` uses the global `key` and `mode` at the end of the file. If key modulation is applied during section generation, the scale locking check will identify the modulated notes as out-of-scale and revert their pitch back to the original scale.

In `vocaloid_generator/beat_generator.py` (lines 280–283):
```python
            # Ghost-Snares
            ghost_prob = 0.42 if is_chorus else 0.25
            if i in [2, 6, 10, 14] and random.random() < ghost_prob:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(38, 56), pitch=SNARE_GHOST, start=t, end=end))
```

---

## 2. Logic Chain

1. **Drop Section & Final Chorus Placement**: 
   - Inserting a 2-bar Drop section right before the final Chorus requires adding `"Drop"` to the `SONG_STRUCTURE` list in `config.py` right before the last `"Chorus"`, and mapping it in `SECTION_CONFIG` as `{"bars": 2, "has_vocals": False}`.
2. **Velocity Overwrite Solution**:
   - Because `humanize_note` overwrites non-drum note velocities, any section-by-section velocity scaling/offset or the +12 final Chorus boost must be applied in a post-processing loop in `orchestrate_song` after all humanization functions have been called.
3. **Scale Locking Correction**:
   - To prevent `STRICT_SCALE_LOCKING` from breaking modulated keys (final Chorus +1 semitone), the scale locking logic must resolve valid note pitch classes using the section-specific key (`sec_key`) stored in `sections_timeline`.
4. **Drop Section Instrument Filtering**:
   - For the Drop section to contain only kick + bass, we must define an `ALLOWED_INSTRUMENTS` map per section type and filter out piano, guitar, strings, synth, and brass. The drum track must be configured to generate only kick drum notes when the section is `"Drop"`.
5. **Conditional Drum Fills & Crescendo**:
   - To make fills transition-aware, `orchestrator.py` must pass a `transition_to_chorus` boolean to `generiere_beat_sektion`. 
   - To implement the PreChorus crescendo, we can multiply all notes in a given bar `takt` of the PreChorus by a scaling factor `0.75 + 0.25 * (takt / (takte - 1))`.

---

## 3. Caveats

- We assume that `config.SONG_STRUCTURE` is the source of truth for the arrangement, and that occurrences are 1-indexed (e.g. the first chorus is occurrence 1, the second is occurrence 2, etc.).
- We assume the final Chorus is identified as the last occurrence of `"Chorus"` in `SONG_STRUCTURE`.
- Scale locking uses predefined scale intervals. We assume that the modulated key uses the same mode (e.g., A minor modulations to A# minor, maintaining the minor mode).
- Since we are in a read-only investigation, we did not execute the code modifications on the filesystem, but we provided exact diffs.

---

## 4. Conclusion & Recommended Implementation Diffs

### File: `vocaloid_generator/config.py`
Add `"Drop"` before the last `"Chorus"` in `SONG_STRUCTURE`, configure it in `SECTION_CONFIG`, and add it to `ENERGY_CURVE`.

```python
# c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\vocaloid_generator\config.py

# Update SONG_STRUCTURE:
SONG_STRUCTURE = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Drop", "Chorus", "Outro"]

# Update SECTION_CONFIG:
SECTION_CONFIG = {
    "Intro":     {"bars": 4,  "has_vocals": False},
    "Build-up":  {"bars": 4,  "has_vocals": False},
    "Verse":     {"bars": 8,  "has_vocals": True},
    "PreChorus": {"bars": 4,  "has_vocals": True},
    "Chorus":    {"bars": 8,  "has_vocals": True},
    "Bridge":    {"bars": 4,  "has_vocals": True},
    "Drop":      {"bars": 2,  "has_vocals": False},  # 2-bar Drop section, no vocals
    "Outro":     {"bars": 4,  "has_vocals": False},
}

# Update ENERGY_CURVE:
ENERGY_CURVE = {
    "Intro": "Niedrig",
    "Build-up": "Normal",
    "Verse": "Normal",
    "PreChorus": "Hoch",
    "Chorus": "Maximal",
    "Bridge": "Niedrig",
    "Drop": "Niedrig",
    "Outro": "Niedrig"
}
```

---

### File: `vocaloid_generator/beat_generator.py`
1. Update `generiere_beat_sektion` signature to accept `transition_to_chorus`.
2. Add kick-only generation for `"Drop"`.
3. Update ghost snare velocity range to `20-40`.
4. Conditionally apply fills in the last bar only if `transition_to_chorus` is `True`.
5. Apply a velocity crescendo across bars for `"PreChorus"`.

```python
# Proposed replacement for generiere_beat_sektion in beat_generator.py

def generiere_beat_sektion(bpm, takte, section_type, start_zeit, swing=SWING, style="J-Pop Energy", transition_to_chorus=False):
    s16     = 60.0 / bpm / 4
    viertel = 60.0 / bpm
    notes   = []

    is_chiptune = (style in ("Kawaii Chiptune", "Chiptune J-Pop"))
    is_chorus  = section_type in ("Chorus", "PreChorus", "Build-up")
    is_verse   = section_type in ("Verse", "Bridge")
    is_intro   = section_type == "Intro"
    is_outro   = section_type == "Outro"
    is_drop    = section_type == "Drop"

    # Markov Rhythmus generieren
    loop_kicks, loop_hats = MarkovDrumGenerator.generate_rhythm_loop(takte, section_type, is_chiptune)

    # Crash am Sektionsanfang
    if section_type in ("Chorus", "Verse", "PreChorus", "Bridge", "Build-up"):
        vel = 127 if (is_chorus or is_chiptune) else 112
        notes.append(pretty_midi.Note(velocity=vel, pitch=CRASH,
                                       start=start_zeit, end=start_zeit + viertel))

    fill_styles = [_fill_standard, _fill_snare_roll, _fill_sixteenth_kicks]

    for takt in range(takte):
        ts       = start_zeit + takt * 4 * viertel
        is_last  = (takt == takte - 1)
        takt_4   = takt % 4
        
        curr_kick_pat = loop_kicks[takt]
        curr_hat_pat = loop_hats[takt]

        # Calculate crescendo factor for PreChorus
        if section_type == "PreChorus" and takte > 1:
            crescendo_factor = 0.75 + 0.25 * (takt / (takte - 1))
        else:
            crescendo_factor = 1.0

        # ── Drop Section (Kick-only) ──
        if is_drop:
            for i in range(16):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16
                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))
            continue

        # ── Chiptune-spezifische Drum-Struktur ──
        if is_chiptune:
            if is_intro:
                if takt == 0:
                    notes.append(pretty_midi.Note(velocity=68, pitch=CRASH2, start=ts, end=ts + viertel * 2))
                if is_last:
                    for i in range(12, 16):
                        t = ts + i * s16
                        notes.append(pretty_midi.Note(velocity=60 + (i-12)*15, pitch=SNARE, start=t, end=t + s16 * 0.9))
                continue

            if is_last and transition_to_chorus:
                _fill_snare_roll(ts, s16, viertel, notes, is_chorus=True)
                continue

            for i in range(16):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16

                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))

                if section_type in ("Build-up", "Chorus", "Verse", "PreChorus"):
                    if i in [4, 12]:
                        notes.append(pretty_midi.Note(velocity=124, pitch=SNARE, start=t, end=end))
                        notes.append(pretty_midi.Note(velocity=118, pitch=CLAP, start=t + 0.003, end=end))
                    if i in [2, 6, 10, 14] and random.random() < 0.35:
                        notes.append(pretty_midi.Note(velocity=random.randint(20, 40), pitch=SNARE_GHOST, start=t, end=end))
                elif section_type == "Bridge":
                    if i == 8:
                        notes.append(pretty_midi.Note(velocity=110, pitch=SNARE, start=t, end=end))
                        notes.append(pretty_midi.Note(velocity=95, pitch=CLAP, start=t + 0.003, end=end))
                elif is_outro:
                    if is_last and i >= 4:
                        continue
                    if i in [4, 12]:
                        notes.append(pretty_midi.Note(velocity=115, pitch=SNARE, start=t, end=end))

                hat_pitch, hat_vel = curr_hat_pat[i]
                if hat_pitch:
                    notes.append(pretty_midi.Note(velocity=hat_vel, pitch=hat_pitch, start=t, end=end))
                    if is_chorus and i % 4 == 2 and random.random() < 0.4:
                        notes.append(pretty_midi.Note(velocity=75, pitch=COWBELL, start=t, end=end))
                    if is_chorus and i % 2 == 1:
                        notes.append(pretty_midi.Note(velocity=70, pitch=SHAKER, start=t, end=end))

            # Apply PreChorus crescendo
            if crescendo_factor < 1.0:
                for note in notes:
                    if ts <= note.start < ts + 4 * viertel:
                        note.velocity = max(1, min(127, int(note.velocity * crescendo_factor)))
            continue

        # ── Standard J-Pop Rhythmus ──
        if is_last and transition_to_chorus:
            fill_fn = random.choice(fill_styles)
            for i in range(8):
                t   = ts + i * s16 + sd(i, s16, swing)
                end = t + s16
                if curr_kick_pat[i]:
                    notes.append(pretty_midi.Note(velocity=115 + random.randint(-5, 5), pitch=KICK, start=t, end=end))
                if i == 4:
                    notes.append(pretty_midi.Note(velocity=122 if is_chorus else 115, pitch=SNARE, start=t, end=end))
                hat_pitch, hat_vel = curr_hat_pat[i]
                if hat_pitch:
                    notes.append(pretty_midi.Note(velocity=hat_vel, pitch=hat_pitch, start=t, end=end))
            
            fill_fn(ts, s16, viertel, notes, is_chorus)
            continue

        for i in range(16):
            t   = ts + i * s16 + sd(i, s16, swing)
            end = t + s16

            if i in [14, 15] and is_chorus:
                notes.append(pretty_midi.Note(velocity=random.randint(80, 95), pitch=HIHAT_CL, start=t, end=end))
                continue

            if curr_kick_pat[i]:
                vel = 120 + random.randint(-4, 4) if is_chorus else 110 + random.randint(-4, 4)
                notes.append(pretty_midi.Note(velocity=vel, pitch=KICK, start=t, end=end))

            if i in [4, 12]:
                vel = 124 if is_chorus else 115
                notes.append(pretty_midi.Note(velocity=vel, pitch=SNARE, start=t, end=end))
            
            # Snare ghost notes velocity 20-40
            ghost_prob = 0.42 if is_chorus else 0.25
            if i in [2, 6, 10, 14] and random.random() < ghost_prob:
                notes.append(pretty_midi.Note(
                    velocity=random.randint(20, 40), pitch=SNARE_GHOST, start=t, end=end))

            if i in [4, 12] and is_chorus:
                if random.random() < 0.70:
                    notes.append(pretty_midi.Note(velocity=random.randint(90, 105), pitch=CLAP, start=t + 0.002, end=end))

            hat_pitch, hat_vel = curr_hat_pat[i]
            if is_verse or is_intro or is_outro:
                if i % 2 == 0:
                    notes.append(pretty_midi.Note(velocity=random.randint(72, 85), pitch=RIDE, start=t, end=end))
                elif random.random() < 0.18:
                    notes.append(pretty_midi.Note(velocity=random.randint(52, 62), pitch=HIHAT_CL, start=t, end=end))
            else:
                if hat_pitch:
                    v = max(0, min(127, hat_vel + random.randint(-8, 8)))
                    end_hat = t + s16 * 1.5 if hat_pitch == HIHAT_OP else end
                    notes.append(pretty_midi.Note(velocity=v, pitch=hat_pitch, start=t, end=end_hat))

            if i in [6, 14] and not is_last:
                notes.append(pretty_midi.Note(velocity=random.randint(52, 65), pitch=HIHAT_FOOT, start=t, end=end))

            if is_chorus and i % 4 == 2:
                notes.append(pretty_midi.Note(velocity=random.randint(55, 70), pitch=SHAKER, start=t, end=end))

        # Apply PreChorus crescendo
        if crescendo_factor < 1.0:
            for note in notes:
                if ts <= note.start < ts + 4 * viertel:
                    note.velocity = max(1, min(127, int(note.velocity * crescendo_factor)))

    return notes
```

---

### File: `vocaloid_generator/orchestrator.py`
Add `get_section_key` helper, implement `ALLOWED_INSTRUMENTS` filtering, update `STRICT_SCALE_LOCKING` to be section-key-aware, and apply post-humanization velocity offsets and the +12 final Chorus boost.

```python
# Helper to be added near the top of orchestrator.py
def get_section_key(section_type, occurrence, original_key, original_mode):
    """
    Returns the key for a given section. Modulates final Chorus by +1 semitone.
    """
    import config
    total_occurrences = config.SONG_STRUCTURE.count(section_type)
    if section_type == "Chorus" and occurrence == total_occurrences:
        chromatic_keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        norm_map = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        norm_key = norm_map.get(original_key, original_key)
        if norm_key in chromatic_keys:
            idx = chromatic_keys.index(norm_key)
            return chromatic_keys[(idx + 1) % 12]
    return original_key


# Allowed instruments mapping inside orchestrate_song:
ALLOWED_INSTRUMENTS = {
    "Intro":     ["piano", "bass"],
    "Outro":     ["piano", "bass"],
    "Verse":     ["piano", "bass", "guitar", "drums"],
    "PreChorus": ["piano", "bass", "guitar", "strings", "drums"],
    "Chorus":    ["piano", "bass", "guitar", "strings", "synth", "brass", "drums"],
    "Bridge":    ["piano", "bass", "strings"],
    "Drop":      ["bass", "drums"],  # Kick + Bass only (Kick-only drums is enforced in beat_generator)
}


# Velocity Offsets mapping:
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
```

```diff
@@ -134,10 +134,16 @@
     
     section_roots = []
     section_counts = {}
     second_verse_start = None
     second_verse_end = None
+    sections_timeline = []
     
     for section_idx, section_type in enumerate(structure):
         config_sect = section_config.get(section_type, {"bars": 4, "has_vocals": True})
         bars = config_sect.get("bars", 4)
         has_vocals = config_sect.get("has_vocals", True)
         
         # Track occurrence counts
         section_counts[section_type] = section_counts.get(section_type, 0) + 1
         occurrence = section_counts[section_type]
         
+        # Determine modulated key for this section
+        sec_key = get_section_key(section_type, occurrence, key, mode)
+        
+        # Track timeline for scale locking and velocity post-processing
+        sections_timeline.append({
+            "section_type": section_type,
+            "start": start_time,
+            "end": start_time + bars * bar_duration,
+            "idx": section_idx,
+            "key": sec_key,
+            "mode": mode
+        })
+
         if section_type == "Verse" and occurrence == 2:
             second_verse_start = start_time
             second_verse_end = start_time + bars * bar_duration
 
         # Get and wrap/slice chord progression
         previous_roots = section_roots[-1]["roots"] if section_roots else None
         progression = None
         for attempt in range(10):
-            prog = get_progression(section_type, key, mode, chord_style)
+            prog = get_progression(section_type, sec_key, mode, chord_style)
             if genre.lower() == "j-pop":
                 if section_type == "Chorus":
-                    prog = get_progression(section_type, key, mode, "dramatic minor" if mode == "minor" else "royal road j-pop")
+                    prog = get_progression(section_type, sec_key, mode, "dramatic minor" if mode == "minor" else "royal road j-pop")
                 elif section_type == "PreChorus":
-                    prog = get_progression(section_type, key, mode, "rising pre-chorus")
+                    prog = get_progression(section_type, sec_key, mode, "rising pre-chorus")
                 elif section_type == "Verse":
-                    prog = get_progression(section_type, key, mode, "emotional descend" if mode == "minor" else "bittersweet")
+                    prog = get_progression(section_type, sec_key, mode, "emotional descend" if mode == "minor" else "bittersweet")
                 elif section_type == "Bridge":
-                    prog = get_progression(section_type, key, mode, "wagyoku/japanese-modal" if mode == "minor" else "bittersweet")
+                    prog = get_progression(section_type, sec_key, mode, "wagyoku/japanese-modal" if mode == "minor" else "bittersweet")
             
             roots = [r for r, _ in prog]
             if previous_roots is None or roots != previous_roots or attempt == 9:
@@ -194,37 +208,44 @@
         sect_patterns = genre_config[sect_key]
         
+        # Get allowed instruments based on density mapping
+        allowed = ALLOWED_INSTRUMENTS.get(section_type, ["piano", "bass", "guitar", "strings", "synth", "brass", "drums"])
+        
         # Generate modular instruments
         # 1. Piano
         p_pattern = sect_patterns.get("piano")
-        if p_pattern:
-            tracks["piano"].extend(generate_piano(progression, p_pattern, section_type, bpm, key, mode, start_time, genre))
+        if p_pattern and "piano" in allowed:
+            tracks["piano"].extend(generate_piano(progression, p_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 2. Bass
         b_pattern = sect_patterns.get("bass")
-        if b_pattern:
-            tracks["bass"].extend(generate_bass(progression, b_pattern, section_type, bpm, key, mode, start_time, genre))
+        if b_pattern and "bass" in allowed:
+            tracks["bass"].extend(generate_bass(progression, b_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 3. Guitar
         g_pattern = sect_patterns.get("guitar")
-        if g_pattern:
-            tracks["guitar"].extend(generate_guitar(progression, g_pattern, section_type, bpm, key, mode, start_time, genre))
+        if g_pattern and "guitar" in allowed:
+            tracks["guitar"].extend(generate_guitar(progression, g_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 4. Strings
         s_pattern = sect_patterns.get("strings")
-        if s_pattern:
-            tracks["strings"].extend(generate_strings(progression, s_pattern, section_type, bpm, key, mode, start_time, genre))
+        if s_pattern and "strings" in allowed:
+            tracks["strings"].extend(generate_strings(progression, s_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 5. Synth
         syn_pattern = sect_patterns.get("synth")
-        if syn_pattern:
-            tracks["synth"].extend(generate_synth(progression, syn_pattern, section_type, bpm, key, mode, start_time, genre))
+        if syn_pattern and "synth" in allowed:
+            tracks["synth"].extend(generate_synth(progression, syn_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 6. Brass
         br_pattern = sect_patterns.get("brass")
-        if br_pattern:
-            tracks["brass"].extend(generate_brass(progression, br_pattern, section_type, bpm, key, mode, start_time, genre))
+        if br_pattern and "brass" in allowed:
+            tracks["brass"].extend(generate_brass(progression, br_pattern, section_type, bpm, sec_key, mode, start_time, genre))
             
         # 7. Drums (beat_generator)
-        drum_notes = generiere_beat_sektion(bpm, bars, section_type, start_time, swing=0.0, style=beat_style)
-        humanize_notes(drum_notes, genre=genre, instrument_type="drums", bpm=bpm)
-        tracks["drums"].extend(drum_notes)
+        if "drums" in allowed:
+            next_sect = structure[section_idx + 1] if section_idx + 1 < len(structure) else None
+            transition_to_chorus = (next_sect == "Chorus")
+            drum_notes = generiere_beat_sektion(bpm, bars, section_type, start_time, swing=0.0, style=beat_style, transition_to_chorus=transition_to_chorus)
+            humanize_notes(drum_notes, genre=genre, instrument_type="drums", bpm=bpm)
+            tracks["drums"].extend(drum_notes)
         
         # Retrieve section energy from config
@@ -244,7 +265,7 @@
             silben = lyrics_kana.split()
             mel_notes, sec_mel_daten, _ = generiere_melodie_sektion(
-                bpm, silben, section_type, start_time, energy=section_energy, key=key, mode=mode, swing=0.0, style=beat_style
+                bpm, silben, section_type, start_time, energy=section_energy, key=sec_key, mode=mode, swing=0.0, style=beat_style
             )
             humanize_notes(mel_notes, genre=genre, instrument_type="melody", bpm=bpm)
             tracks["melody"].extend(mel_notes)
@@ -269,22 +290,29 @@
-        intervals = scale_intervals.get(mode, scale_intervals["minor"])
-        
         # Resolve key offset
         key_offsets = {
             "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
             "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
         }
-        root_offset = key_offsets.get(key, 0)
-        valid_classes = {(root_offset + interval) % 12 for interval in intervals}
         
         for track_name, notes in tracks.items():
             if track_name in ("drums", "silben", "melody_data", "section_roots") or not notes:
                 continue
             for n in notes:
-                if (n.pitch % 12) not in valid_classes:
-                    adjusted = n.pitch
-                    for diff in range(1, 12):
-                        if ((n.pitch - diff) % 12) in valid_classes:
-                            adjusted = n.pitch - diff
-                            break
-                        if ((n.pitch + diff) % 12) in valid_classes:
-                            adjusted = n.pitch + diff
-                            break
-                    n.pitch = adjusted
+                # Determine section to apply correct key scale locking
+                for sec in sections_timeline:
+                    if sec["start"] - 0.005 <= n.start < sec["end"] - 0.005:
+                        sec_intervals = scale_intervals.get(sec["mode"], scale_intervals["minor"])
+                        sec_root_offset = key_offsets.get(sec["key"], 0)
+                        sec_valid_classes = {(sec_root_offset + interval) % 12 for interval in sec_intervals}
+                        
+                        if (n.pitch % 12) not in sec_valid_classes:
+                            adjusted = n.pitch
+                            for diff in range(1, 12):
+                                if ((n.pitch - diff) % 12) in sec_valid_classes:
+                                    adjusted = n.pitch - diff
+                                    break
+                                if ((n.pitch + diff) % 12) in sec_valid_classes:
+                                    adjusted = n.pitch + diff
+                                    break
+                            n.pitch = adjusted
+                        break
 
     # Central Humanization of all tracks to guarantee velocity and timing dynamics
@@ -306,4 +334,22 @@
 
+    # Post-processing: Scale velocity offsets and final Chorus boost (+12)
+    final_chorus_idx = -1
+    for idx, sec in enumerate(structure):
+        if sec == "Chorus":
+            final_chorus_idx = idx
+
+    for track_name, note_list in tracks.items():
+        if track_name in ("silben", "melody_data", "section_roots"):
+            continue
+        for note in note_list:
+            for sec in sections_timeline:
+                if sec["start"] - 0.005 <= note.start < sec["end"] - 0.005:
+                    offset = SECTION_VELOCITY_OFFSETS.get(sec["section_type"], 0)
+                    if sec["section_type"] == "Chorus" and sec["idx"] == final_chorus_idx:
+                        offset += 12
+                    note.velocity = max(1, min(127, note.velocity + offset))
+                    break
```

---

## 5. Verification Method

### 1. Automated Integration Tests
An implementer should add the following unit test to `vocaloid_generator/test_orchestrator.py` to verify all components of R3 and R4:

```python
def test_dynamic_arrangements_and_modulation():
    print("\n=== Testing Dynamic Arrangement & Modulation (R3 & R4) ===")
    from config import SONG_STRUCTURE, SECTION_CONFIG, KEY, MODE
    from orchestrator import orchestrate_song
    
    # Run the generator with the current structure config
    tracks = orchestrate_song(
        genre="J-Pop",
        bpm=160,
        structure=SONG_STRUCTURE,
        key=KEY,
        mode=MODE,
        section_config=SECTION_CONFIG
    )
    
    # 1. Verify Drop Section contains only kick + bass
    # Drop is at index 9 in structure: ["Intro", "Build-up", ..., "Bridge", "Drop", "Chorus", "Outro"]
    # Let's verify start/end time of Drop.
    # Intro (4 bars), Build-up (4 bars), Verse (8 bars), PreChorus (4 bars), Chorus (8 bars),
    # Verse (8 bars), PreChorus (4 bars), Chorus (8 bars), Bridge (4 bars) => 44 bars total before Drop.
    # Each bar is 4 * (60.0 / 160) = 1.5 seconds.
    drop_start = 44 * 1.5
    drop_end = 46 * 1.5
    
    # Verify no piano, guitar, strings, synth, brass, or melody notes start inside the Drop section
    for track_name in ["piano", "guitar", "strings", "synth", "brass", "melody"]:
        notes_in_drop = [n for n in tracks[track_name] if drop_start <= n.start < drop_end]
        assert len(notes_in_drop) == 0, f"Track {track_name} should be silent during Drop section"
        
    # Verify only Kick is generated for drums in the Drop section
    drop_drums = [n for n in tracks["drums"] if drop_start <= n.start < drop_end]
    for note in drop_drums:
        assert note.pitch == 36, "Only Kick drum (MIDI 36) allowed in the Drop section"
        
    # 2. Verify Final Chorus Key Modulation (+1 semitone)
    # The final Chorus is the last occurrence. We compare note pitches between the second and final Chorus.
    # Second Chorus starts at bar 28: Intro(4)+Build-up(4)+Verse(8)+PreChorus(4)+Chorus(8)+Verse(8)+PreChorus(4) = 40 bars.
    # Second Chorus starts at 40 * 1.5 = 60.0s.
    # Final Chorus starts at bar 46: 46 * 1.5 = 69.0s.
    c2_notes = [n.pitch for n in tracks["bass"] if 60.0 <= n.start < 72.0]
    cf_notes = [n.pitch for n in tracks["bass"] if 69.0 <= n.start < 81.0]
    
    # Since chords modulate up, the average pitch class should shift by 1
    c2_avg = sum(c2_notes) / len(c2_notes) if c2_notes else 0
    cf_avg = sum(cf_notes) / len(cf_notes) if cf_notes else 0
    print(f"Second Chorus Bass Avg Pitch: {c2_avg:.2f}, Final Chorus Bass Avg Pitch: {cf_avg:.2f}")
    assert abs(cf_avg - c2_avg - 1.0) < 0.5, "Final Chorus must be modulated by +1 semitone relative to the second Chorus"
    
    # 3. Verify Final Chorus Velocity Boost (+12)
    # Compare average velocity of bass notes in the second Chorus vs final Chorus
    c2_vels = [n.velocity for n in tracks["bass"] if 60.0 <= n.start < 72.0]
    cf_vels = [n.velocity for n in tracks["bass"] if 69.0 <= n.start < 81.0]
    c2_avg_vel = sum(c2_vels) / len(c2_vels) if c2_vels else 0
    cf_avg_vel = sum(cf_vels) / len(cf_vels) if cf_vels else 0
    print(f"Second Chorus Bass Avg Velocity: {c2_avg_vel:.2f}, Final Chorus Bass Avg Velocity: {cf_avg_vel:.2f}")
    assert cf_avg_vel > c2_avg_vel + 10.0, "Final Chorus notes must have a ~12 velocity boost"
    
    # 4. Verify Snare Ghost Note Velocity Range (20-40)
    snares = [n for n in tracks["drums"] if n.pitch == 40]  # 40 is SNARE_GHOST
    for note in snares:
        assert 20 <= note.velocity <= 40, f"Ghost snare velocity {note.velocity} is outside [20, 40] range"
        
    print("[PASS] R3 and R4 dynamic and modulation tests passed successfully!")
```

### 2. Manual Verification
Run the standard validation command:
```powershell
python test_orchestrator.py
```
This confirms that the generator produces valid MIDI output files without syntax or import errors. Open the resulting MIDI tracks in a DAW or MIDI visualizer to check:
- The last bar of the Bridge transitions into the Drop section, containing only a kick pattern and a bass line.
- The transition from the Drop section into the final Chorus has a drum fill.
- The final Chorus key change is audibly and visually pitched 1 semitone higher than all preceding sections.
