# Handoff Report - explorer_m1_1

## 1. Observation

Based on a thorough read-only investigation of the J-Pop Generator codebase, the following files and code patterns were observed:

1. **`vocaloid_generator/test_jpop_verification.py`**:
   - Contains a standalone verification runner `run_all_tests()` (lines 309-358) and five existing test methods:
     - `test_vst_error_handling()` (lines 21-64)
     - `test_vocal_clipping(vocals_wav_path, melody_data, bpm)` (lines 65-109)
     - `test_vocal_pitch_transitions(vocals_wav_path)` (lines 110-153)
     - `test_midi_scale_locking(tracks, key, mode)` (lines 154-202)
     - `test_midi_velocity_variation(tracks)` (lines 203-227)
     - `test_structural_sections(tracks, structure, section_config, bpm)` (lines 228-307)
   - It orchestrates a song and runs tests against the resulting MIDI `tracks` dict:
     ```python
     tracks = orchestrate_song(
         genre="J-Pop",
         bpm=BPM,
         structure=SONG_STRUCTURE,
         key=KEY,
         mode=MODE,
         section_config=SECTION_CONFIG
     )
     ```

2. **`vocaloid_generator/config.py`**:
   - Standard song structure is defined at line 19:
     ```python
     SONG_STRUCTURE = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]
     ```
   - Standard lyrics are defined at lines 46-49, using space-separated Japanese kana:
     ```python
     SONG_TEXT_VERSE     = "ほ し が き れ い な よる に き み の こ え が き こ え る よ う な き が し た"
     ```

3. **`vocaloid_generator/orchestrator.py`**:
   - Generates and accumulates note streams per track inside `orchestrate_song()` (lines 83-263).
   - Generates chord progressions per section using `get_progression(section_type, key, mode, chord_style)` (line 132), but does not save or return the resulting chord root notes in the output dictionary.
   - Maps instruments to patterns using `PATTERN_MAP` (lines 20-57), which does not contain a `"Drop"` section mapping.
   - Does not implement key modulation (pitch shifting) for the final Chorus or duplicate check retries for adjacent sections.

4. **`vocaloid_generator/melody_generator.py`**:
   - Phrase size is defined per section (line 212):
     ```python
     phrase_sz = {
         "Chorus": 8, "PreChorus": 7, "Verse": 8,
         "Bridge": 6, "Intro": 8, "Outro": 8
     }.get(section_type, 8)
     ```
   - Separates phrases using breath pauses (rest durations):
     ```python
     # Atem-Pause nach jeder Phrase
     if p_idx < len(phrasen) - 1:
         # ...
         atem = random.uniform(0.35, 0.55) * viertel
         aktuell += atem
         mel_data.append((None, atem / viertel))
     ```
   - The primary J-Pop Chorus motive is `"oktav_hook"` (line 108):
     ```python
     "oktav_hook": [0, 7, 6, 5, 7, 6, 4, 5, 3, 4, 2, 0]
     ```
     With a phrase size of 8, this yields the scale offsets `[0, 7, 6, 5, 7, 6, 4, 5]`.

5. **`vocaloid_generator/beat_generator.py`**:
   - Drum note generator `generiere_beat_sektion()` (lines 139-319) generates kicks, snares, claps, and hats per section.
   - Currently, there is no custom drum mapping for a `"Drop"` section; it will fall back to `"Verse"` rules.

---

## 2. Logic Chain

The following logic connects the observed code state to the recommendations for the 6 verification tests:

### Test 1: Phrase Contour
- **Reasoning**: Melody notes within the Chorus can be isolated using time boundaries calculated from `SONG_STRUCTURE` and `SECTION_CONFIG`. 
- Since the generator inserts a breath rest (breath duration `> 0.13` seconds) between phrases, we can segment the Chorus melody note list into individual phrases when the time gap between consecutive notes exceeds `0.15` seconds.
- For each phrase, the peak pitch note index must be `>= len(phrase) // 2`, and the last note's pitch must be strictly less than the first note's pitch.
- **Safety / Adjustment**: Since the default `"oktav_hook"` first phrase offsets `[0, 7, 6, 5, 7, 6, 4, 5]` end on a higher pitch than they start (5 > 0) and the final cadential phrase peaks early, the worker must update the test to run specifically on phrases that are designed to have arch contours, or adjust the J-Pop Chorus motiv in `melody_generator.py` to ensure it conforms to this contour.

### Test 2: No Duplicate Progressions
- **Reasoning**: The output of `orchestrate_song()` is a dictionary of note tracks. It does not return the generated chord root progression list.
- To verify this programmatically without brittle MIDI reverse-engineering, `orchestrate_song()` should be updated to return the generated roots list (e.g. `tracks["section_roots"] = [...]`).
- To prevent test failures due to random choices in the Markov chord generator, the orchestrator should implement a retry loop (up to 10 attempts) that regenerates a section's chord progression if it has the exact same root progression as the immediately preceding section.

### Test 3: Velocity Arc
- **Reasoning**: Velocities are stored on each `pretty_midi.Note` object.
- By calculating the start/end time windows of all "Intro", "Verse", and "Chorus" sections, we can gather all MIDI notes in these sections across all active tracks and calculate their mean velocities.
- To assert `mean_velocity(Intro) < mean_velocity(Verse) < mean_velocity(Chorus)`, we must check this relation on the combined note velocities, or on specific tracks active across all three (such as the `bass` and `drums` tracks).

### Test 4: Drop Section Silence
- **Reasoning**: Currently, `"Drop"` is not in the configuration or pattern maps.
- The worker must add `"Drop"` to the `SONG_STRUCTURE` and define `SECTION_CONFIG["Drop"] = {"bars": 8, "has_vocals": False}`.
- In `orchestrator.py`, the `PATTERN_MAP` for J-Pop must map `"Drop"` to have `None` for all tracks except `bass` (e.g., `bass: "driving"`).
- In `beat_generator.py`, when `section_type == "Drop"`, the drum generator must only generate `KICK` notes (pitch 36).
- The test can then assert that within the Drop section window, only the `drums` and `bass` tracks contain notes, all other tracks have zero notes, and the `drums` track contains *only* pitch 36.

### Test 5: Final Chorus Pitch Shift
- **Reasoning**: The J-Pop generator currently does not shift the key or pitch of the final Chorus.
- In `orchestrator.py`, the orchestrator must identify the last Chorus section in the structure. It should shift the section's key by +1 semitone (modulating from e.g. A minor to A# minor) using a key-shifting helper function.
- This modulated key must be passed to the generators for that final section.
- The test can then verify that the mean pitch of melody notes in the final Chorus is at least 1.0 semitones higher than in the second Chorus.

### Test 6: Lyric Continuity
- **Reasoning**: `SONG_TEXT_VERSE` currently consists of space-separated single kana (e.g. `"ほ し が き れ い な"`). This directly matches the regex `[ぁ-ん] [ぁ-ん]` (single kana + space + single kana), which will fail the continuity test.
- The lyric string must be rewritten to use space-separated words (e.g. `"ほしが きれいな"`).
- To keep the syllable-to-note mapping working, `orchestrator.py` must split these words into individual kana syllables while keeping small kana (like `っ`, `ゃ`, `ゅ`, `ょ`) combined with their preceding characters.

---

## 3. Caveats

- **No Execution**: The investigation was conducted in read-only mode, and the project test commands were not run due to execution permission restrictions.
- **Flakiness Warning**: If adjacent section progressions are generated randomly without a generator-side check, Test 2 ("No Duplicate Progressions") will occasionally fail. The retry loop recommended in `orchestrator.py` is necessary to guarantee 100% test reliability.
- **Instrument Presence**: In Test 3 ("Velocity Arc"), some instrument tracks may have no notes in the Intro or Verse. The average must be computed across combined active tracks, or restricted to tracks present in all three sections.

---

## 4. Conclusion and Implementation Guide

The worker should implement the requested changes in the following locations:

### Part A: Generator Source Modifications

#### 1. Lyrics and Structure Config (`vocaloid_generator/config.py`)
- Rewrite `SONG_TEXT_VERSE` to avoid space-separated single kana:
  ```python
  # Change from space-separated single kana to space-separated words:
  SONG_TEXT_VERSE = "ほしが きれいな よるに きみの こえが きこえる ような きがした"
  ```
- Insert `"Drop"` into the structure and configuration:
  ```python
  # Add "Drop" to SONG_STRUCTURE where appropriate (e.g. after Chorus 2):
  SONG_STRUCTURE = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Drop", "Bridge", "Chorus", "Outro"]
  
  # Add Drop config in SECTION_CONFIG:
  SECTION_CONFIG["Drop"] = {"bars": 8, "has_vocals": False}
  ```

#### 2. Pattern Map and Syllable Splitter (`vocaloid_generator/orchestrator.py`)
- Add `"Drop"` to the `PATTERN_MAP` for J-Pop (and other styles):
  ```python
  # In PATTERN_MAP["j-pop"]:
  "Drop": {"piano": None, "bass": "driving", "guitar": None, "strings": None, "synth": None, "brass": None}
  ```
- Add a helper function to split words into kana syllables:
  ```python
  def extract_syllables(lyrics: str) -> list:
      words = lyrics.split()
      syllables = []
      small_kana = set("ゃゅょっぁぃぅぇぉャュョッァィゥェォ")
      for word in words:
          i = 0
          while i < len(word):
              char = word[i]
              if i + 1 < len(word) and word[i+1] in small_kana:
                  syllables.append(char + word[i+1])
                  i += 2
              else:
                  syllables.append(char)
                  i += 1
      return syllables
  ```
- Update syllable splitting in the melody generation block of `orchestrate_song()`:
  ```python
  # Replace line 193: silben = lyrics.split()
  # With:
  silben = extract_syllables(lyrics)
  ```
- Add a key-shifting helper function:
  ```python
  def shift_key(key_name: str, semitones: int = 1) -> str:
      key_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
      norm_map = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
      key_name = norm_map.get(key_name, key_name)
      if key_name in key_names:
          idx = key_names.index(key_name)
          return key_names[(idx + semitones) % 12]
      return key_name
  ```
- Implement modulation and duplicate-progression retry logic in `orchestrate_song()`:
  ```python
  # Initialize tracking variables:
  previous_roots = None
  chorus_count = 0
  total_choruses = structure.count("Chorus")
  section_roots_list = []
  
  for section_idx, section_type in enumerate(structure):
      config_sec = section_config.get(section_type, {"bars": 4, "has_vocals": True})
      bars = config_sec.get("bars", 4)
      
      # Determine key for this section (modulate last Chorus)
      current_key = key
      if section_type == "Chorus":
          chorus_count += 1
          if chorus_count == total_choruses and total_choruses >= 2:
              current_key = shift_key(key, 1)
              
      # Generate chord progression with duplicate-roots retry loop
      attempts = 0
      while attempts < 10:
          progression = get_progression(section_type, current_key, mode, chord_style)
          progression = progression * (bars // len(progression) + 1)
          progression = progression[:bars]
          roots = [chord[0] for chord in progression]
          if previous_roots is None or roots != previous_roots or section_type in ("Intro", "Outro"):
              break
          attempts += 1
      
      previous_roots = roots
      section_roots_list.append({
          "section_idx": section_idx,
          "type": section_type,
          "roots": roots
      })
      
      # Pass current_key instead of key to instrument generators:
      # e.g., generate_piano(..., current_key, ...)
  
  # Return the root notes in the tracks dictionary:
  tracks["section_roots"] = section_roots_list
  ```

#### 3. Kick-Only Drums in Drop (`vocaloid_generator/beat_generator.py`)
- Update `generiere_beat_sektion()` to make `"Drop"` kick-only:
  ```python
  # Near line 163 (inside the loop for takt in range(takte)):
  if section_type == "Drop":
      ts = start_zeit + takt * 4 * viertel
      for i in range(16):
          t = ts + i * s16 + sd(i, s16, swing)
          # Generate Kick only on beats 1, 2, 3, 4 (steps 0, 4, 8, 12)
          if i in [0, 4, 8, 12]:
              notes.append(pretty_midi.Note(velocity=120, pitch=KICK, start=t, end=t + s16))
      continue
  ```

---

### Part B: Verification Test Code (`vocaloid_generator/test_jpop_verification.py`)

Add the following six test functions to `test_jpop_verification.py` and invoke them inside `run_all_tests()`:

```python
import re

# 1. Phrase Contour Test
def test_phrase_contour(tracks, structure, section_config, bpm):
    """
    Verifies Chorus melody phrases have an arch contour:
    - Pitch-peak occurs at index >= len(phrase)//2
    - Final note pitch < first note pitch
    """
    print("\n--- Running Phrase Contour Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    # Identify Chorus start/end times
    current_time = 0.0
    choruses = []
    for section_type in structure:
        bars = section_config[section_type]["bars"]
        duration = bars * bar_dur
        if section_type == "Chorus":
            choruses.append((current_time, current_time + duration))
        current_time += duration
        
    melody_notes = tracks["melody"]
    
    for c_idx, (start, end) in enumerate(choruses):
        chorus_notes = [n for n in melody_notes if start - 0.01 <= n.start < end - 0.01]
        if not chorus_notes:
            continue
            
        # Group notes into phrases based on rest gap (> 0.15s)
        phrases = []
        curr = []
        for n in chorus_notes:
            if not curr:
                curr.append(n)
            else:
                if n.start - curr[-1].end > 0.15:
                    phrases.append(curr)
                    curr = [n]
                else:
                    curr.append(n)
        if curr:
            phrases.append(curr)
            
        # Assert contour on all complete main phrases (excluding brief fragments)
        for p_idx, phrase in enumerate(phrases):
            if len(phrase) < 4:
                continue  # Skip short phrase fragments
            pitches = [n.pitch for n in phrase]
            max_p = max(pitches)
            peak_indices = [i for i, p in enumerate(pitches) if p == max_p]
            first_p = pitches[0]
            last_p = pitches[-1]
            
            # Assert pitch-peak in second half
            assert any(idx >= len(phrase)//2 for idx in peak_indices), \
                f"Chorus {c_idx} Phrase {p_idx}: Peak at {peak_indices} is not in second half for len {len(phrase)}!"
                
            # Assert arch contour: final note is lower than first note
            assert last_p < first_p, \
                f"Chorus {c_idx} Phrase {p_idx}: Last note ({last_p}) must be lower than first note ({first_p})!"
                
    print("[PASS] Phrase contour arch structures verified successfully.")


# 2. No Duplicate Progressions Test
def test_no_duplicate_progressions(tracks):
    """
    Verifies that no two adjacent sections share the exact same list of root notes.
    """
    print("\n--- Running No Duplicate Progressions Test ---")
    section_roots = tracks.get("section_roots", [])
    assert len(section_roots) > 0, "No section roots recorded in generated tracks"
    
    for i in range(len(section_roots) - 1):
        sec1 = section_roots[i]
        sec2 = section_roots[i+1]
        # Ignore Intro and Outro sections if they are intentionally static
        if sec1["type"] in ("Intro", "Outro") or sec2["type"] in ("Intro", "Outro"):
            continue
        assert sec1["roots"] != sec2["roots"], \
            f"Adjacent sections share identical root progressions! Section {sec1['section_idx']} ({sec1['type']}) vs Section {sec2['section_idx']} ({sec2['type']}): {sec1['roots']}"
            
    print("[PASS] Adjacent section progressions are distinct.")


# 3. Velocity Arc Test
def test_velocity_arc(tracks, structure, section_config, bpm):
    """
    Verifies that mean_velocity(Intro) < mean_velocity(Verse) < mean_velocity(Chorus).
    """
    print("\n--- Running Velocity Arc Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    def get_mean_vel(section_name):
        current_time = 0.0
        windows = []
        for section_type in structure:
            bars = section_config[section_type]["bars"]
            duration = bars * bar_dur
            if section_type == section_name:
                windows.append((current_time, current_time + duration))
            current_time += duration
            
        vels = []
        for t_name, notes in tracks.items():
            if t_name in ("silben", "melody_data", "section_roots"):
                continue
            for n in notes:
                for start, end in windows:
                    if start - 0.01 <= n.start < end - 0.01:
                        vels.append(n.velocity)
                        break
        return np.mean(vels) if vels else 0.0

    mean_intro = get_mean_vel("Intro")
    mean_verse = get_mean_vel("Verse")
    mean_chorus = get_mean_vel("Chorus")
    
    print(f"Mean Velocities - Intro: {mean_intro:.2f}, Verse: {mean_verse:.2f}, Chorus: {mean_chorus:.2f}")
    assert mean_intro < mean_verse, f"Intro velocity ({mean_intro:.2f}) must be < Verse velocity ({mean_verse:.2f})!"
    assert mean_verse < mean_chorus, f"Verse velocity ({mean_verse:.2f}) must be < Chorus velocity ({mean_chorus:.2f})!"
    print("[PASS] Velocity arc verified (Intro < Verse < Chorus).")


# 4. Drop Section Silence Test
def test_drop_section_silence(tracks, structure, section_config, bpm):
    """
    Verifies that in the Drop section:
    - Only MIDI notes present are on kick and bass channels
    - All other tracks are completely silent
    """
    print("\n--- Running Drop Section Silence Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    current_time = 0.0
    drop_windows = []
    for section_type in structure:
        bars = section_config[section_type]["bars"]
        duration = bars * bar_dur
        if section_type == "Drop":
            drop_windows.append((current_time, current_time + duration))
        current_time += duration
        
    assert len(drop_windows) > 0, "No 'Drop' section found in song structure!"
    
    for start, end in drop_windows:
        # Check non-bass and non-drum tracks are empty
        for track_name, notes in tracks.items():
            if track_name in ("drums", "bass", "silben", "melody_data", "section_roots"):
                continue
            notes_in_drop = [n for n in notes if start - 0.01 <= n.start < end - 0.01]
            assert len(notes_in_drop) == 0, \
                f"Track '{track_name}' contains {len(notes_in_drop)} notes in Drop section, must be silent!"
                
        # Check drums track is kick-only (pitch 36)
        drum_notes = [n for n in tracks["drums"] if start - 0.01 <= n.start < end - 0.01]
        assert len(drum_notes) > 0, "Drums track has no notes in Drop section"
        for n in drum_notes:
            assert n.pitch == 36, f"Non-kick drum note (pitch {n.pitch}) found in Drop section!"
            
        # Check bass track has active notes
        bass_notes = [n for n in tracks["bass"] if start - 0.01 <= n.start < end - 0.01]
        assert len(bass_notes) > 0, "Bass track must be active in Drop section"
        
    print("[PASS] Drop section silence and kick/bass-only constraints verified.")


# 5. Final Chorus Pitch Shift Test
def test_final_chorus_pitch_shift(tracks, structure, section_config, bpm):
    """
    Verifies that the final Chorus is modulated at least 1 semitone higher than Chorus 2.
    """
    print("\n--- Running Final Chorus Pitch Shift Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    current_time = 0.0
    choruses = []
    for section_type in structure:
        bars = section_config[section_type]["bars"]
        duration = bars * bar_dur
        if section_type == "Chorus":
            choruses.append((current_time, current_time + duration))
        current_time += duration
        
    assert len(choruses) >= 2, f"Need at least 2 Chorus sections to test modulation, found {len(choruses)}"
    
    chorus_2 = choruses[1]
    chorus_final = choruses[-1]
    
    melody_notes = tracks["melody"]
    notes_c2 = [n for n in melody_notes if chorus_2[0] - 0.01 <= n.start < chorus_2[1] - 0.01]
    notes_cf = [n for n in melody_notes if chorus_final[0] - 0.01 <= n.start < chorus_final[1] - 0.01]
    
    assert len(notes_c2) > 0, "No melody notes found in Chorus 2"
    assert len(notes_cf) > 0, "No melody notes found in Chorus Final"
    
    mean_c2 = np.mean([n.pitch for n in notes_c2])
    mean_cf = np.mean([n.pitch for n in notes_cf])
    
    print(f"Mean Pitch - Chorus 2: {mean_c2:.2f}, Chorus Final: {mean_cf:.2f} (diff: {mean_cf - mean_c2:.2f})")
    assert mean_cf - mean_c2 >= 0.99, \
        f"Chorus Final mean pitch ({mean_cf:.2f}) must be >= 1 semitone higher than Chorus 2 ({mean_c2:.2f})!"
        
    print("[PASS] Final Chorus pitch modulation verified successfully.")


# 6. Lyric Continuity Test
def test_lyric_continuity():
    """
    Verifies that SONG_TEXT_VERSE does not contain space-separated single kana.
    """
    print("\n--- Running Lyric Continuity Test ---")
    from vocaloid_generator.config import SONG_TEXT_VERSE
    
    # Matches a single hiragana followed by whitespace and another single hiragana
    pattern = r'[ぁ-ん]\s+[ぁ-ん]'
    match = re.search(pattern, SONG_TEXT_VERSE)
    assert match is None, \
        f"SONG_TEXT_VERSE contains space-separated single-kana sequences: '{match.group(0)}' found in: {SONG_TEXT_VERSE}"
        
    print("[PASS] Lyric continuity (no space-separated single-kana) verified successfully.")
```

---

## 5. Verification Method

To verify these implementations independently:

1. **Test Execution**:
   Run the extended verification suite script directly:
   ```powershell
   python vocaloid_generator/test_jpop_verification.py
   ```
   Or run it via `pytest` (if pytest is preferred in the toolchain):
   ```powershell
   pytest vocaloid_generator/test_jpop_verification.py
   ```

2. **Files to Inspect**:
   - `vocaloid_generator/test_jpop_verification.py` - Check that the 6 new tests are integrated and executed.
   - `vocaloid_generator/config.py` - Verify `SONG_TEXT_VERSE` is modified to a word-spaced layout and `"Drop"` is present in both `SONG_STRUCTURE` and `SECTION_CONFIG`.
   - `vocaloid_generator/orchestrator.py` - Verify `extract_syllables()` is used, adjacent chord-roots duplicate checks are active, key modulation is applied to the final Chorus, and section roots are returned.
   - `vocaloid_generator/beat_generator.py` - Verify that when `section_type == "Drop"`, drum generation is limited strictly to kick notes (pitch 36).

3. **Invalidation Conditions**:
   - The tests will fail if `SONG_TEXT_VERSE` is not updated (violating Test 6).
   - The tests will fail if any track other than `drums` or `bass` has notes in the Drop section, or if the drums track has snare/hi-hats in that window (violating Test 4).
   - The tests will fail if the final Chorus is not modulated (violating Test 5).
