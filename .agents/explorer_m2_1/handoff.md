# Handoff Report: Milestone 2 Feature Designs
**Prepared by**: `explorer_m2_1`  
**Date**: 2026-07-06  

---

## 1. Observation
From direct inspection of the codebase in the `vocaloid_generator/` directory, the following file structures and contents were observed:
* **`vocaloid_generator/config.py` (Lines 45–49)**: The lyrics constants currently consist of space-separated individual kana characters, which makes the text fragmented and grammatically unnatural:
  ```python
  SONG_TEXT_VERSE     = "ほ し が き れ い な よ る に き み の こ え が き こ え る よ う な き が し た"
  SONG_TEXT_PRECHORUS = "と ど か な い て を の ば し て も き み は と お い ど こ か へ き え て し ま う"
  SONG_TEXT_CHORUS    = "ら ら ら う た お う よ き み に と ど け こ の き も ち ず っ と わ す れ な い で い て"
  SONG_TEXT_BRIDGE    = "も う す こ し だ け そ ば に い て ね わ す れ な い で き み の こ と だ け"
  ```
  No `ENERGY_CURVE` mapping is present, and there is no logic for section volume/velocity attenuation.
* **`vocaloid_generator/melody_generator.py` (Lines 211–396)**: Inside `generiere_melodie_sektion()`, syllables are grouped into phrases based on `phrase_sz` (usually 6–8 syllables). Note events are generated for each syllable using motifs, adjusted for chord tones, and added directly to the output lists `notes` and `mel_data`. There is no contour enforcement or question-answer pairing logic.
* **`vocaloid_generator/chord_generator.py` (Lines 72–159)**: Progression generation is managed by `MarkovChordGenerator.generiere_loop()` using a Markov-chain probability table. The `get_progression()` function (Lines 156–159) always returns a Markov-generated loop. There are no predefined named J-Pop progressions or ways to extract root lists.
* **`vocaloid_generator/orchestrator.py` (Lines 191–200)**: Melodies are generated with a static energy level:
  ```python
  mel_notes, sec_mel_daten, _ = generiere_melodie_sektion(
      bpm, silben, section_type, start_time, energy="Hoch", key=key, mode=mode, swing=0.0, style=beat_style
  )
  ```

---

## 2. Logic Chain
To implement the features cleanly while maintaining stability, the following step-by-step reasoning was used:
1. **Phrase Contour System**: 
   * Modifying notes in-place inside `generiere_melodie_sektion()` requires separating the generation of a phrase's notes from the main list.
   * If we collect syllable note events in a list `phrase_notes = []` and record their indices in `mel_data`, we can apply a helper `adjust_contour()` to modify pitches.
   * By querying `skala` indices (e.g. `skala.index(pitch)`), we can shift notes up or down scale steps, which guarantees scale-correct pitches and maintains strict scale locking.
   * Question-Answer pairs correspond to even (`p_idx % 2 == 0`) and odd (`p_idx % 2 == 1`) phrase indices in the phrase loop. Storing the final note pitch of even phrases as `previous_question_last_pitch` allows us to force the odd phrase's final note to end lower.
2. **Named Chord Progressions**:
   * We can define `NAMED_PROGRESSIONS` as a dictionary in `chord_generator.py` mapping keys (like `"dramatic minor"`) to lists of Roman numeral strings containing chord extensions (e.g., `maj7`, `m7`, `sus4`, `7`).
   * A helper function `resolve_roman_progression()` will parse these strings and map them to `(Note, ChordType)` tuples using the key-signature offsets in `_NOTE_OFFSETS` and `ROMAN_TO_DEGREE`.
   * We will update `get_progression()` to look up the case-insensitive `style` name in `NAMED_PROGRESSIONS`. If matched, it returns the resolved progression; otherwise, it falls back to the existing Markov-chain logic.
   * The orchestrator can check for duplicate progressions by calling a new helper `get_progression_roots(progression)`, which extracts a simple list of root note names (e.g. `["F", "G", "E", "A"]`).
3. **Corrected Lyrics and Energy Curve**:
   * We will update the lyric constants to natural Japanese text (Kanji + Hiragana, e.g. `"星が綺麗な夜に君の声が聞こえるような気がした"`).
   * Since downstream generators split by space to align notes with syllables, we must avoid breaking this. We will add a `SONG_TEXT_KANA_MAP` mapping each Kanji lyric to its space-separated kana string. The orchestrator will resolve raw text to kana before splitting.
   * We will add `ENERGY_CURVE = { "Intro": "Niedrig", ... }` to `config.py`.
   * The orchestrator can track section occurrences with a counter dictionary. For the second Verse (`"Verse"`, occurrence `2`), it will scale down note velocities by 20% within that time window and set its energy to `"Niedrig"`.

---

## 3. Caveats
* **Scale-locking overlap**: If `STRICT_SCALE_LOCKING` is enabled, the chord generator force-adjusts chord pitches, and the orchestrator later force-adjusts all track pitches. Enforcing contours by shifting scale indices in `skala` respects the scale, but chord-tone adjustments inside the melody generator might shift pitches. To prevent this from breaking the contour, `adjust_contour()` is applied *after* chord harmonization.
* **No external parsing**: Since we are in `CODE_ONLY` network mode, we cannot rely on external Japanese NLP parsers (like MeCab/Janome) for Kanji-to-Hiragana conversion. The mapping approach via `SONG_TEXT_KANA_MAP` is a zero-dependency solution.

---

## 4. Conclusion & Recommendations
The recommended implementation changes are detailed below. These modifications are safe, modular, and do not disrupt existing generator mechanisms.

### Proposed Changes for `vocaloid_generator/config.py`
Replace the lyrics constants and add the energy curve configurations:
```python
# ── Lyrics (Natural Japanese, grammatically correct and phonetically natural) ──
SONG_TEXT_VERSE     = "星が綺麗な夜に君の声が聞こえるような気がした"
SONG_TEXT_PRECHORUS = "届かない手を伸ばしても君は遠いどこかへ消えてしまう"
SONG_TEXT_CHORUS    = "ららら歌おうよ君に届けこの気持ちずっと忘れないでいて"
SONG_TEXT_BRIDGE    = "もう少しだけそばにいてね忘れないで君のことだけ"

# Internal mapping to translate natural Kanji/Kana lyrics into space-separated kana syllables
SONG_TEXT_KANA_MAP = {
    SONG_TEXT_VERSE:     "ほ し が き れ い な よ る に き み の こ え が き こ え る よ う な き が し た",
    SONG_TEXT_PRECHORUS: "と ど か な い て を の ば し て も き み は と お い ど こ か へ き え て し ま う",
    SONG_TEXT_CHORUS:    "ら ら ら う た お う よ き み に と ど け こ の き も ち ず っ と わ す れ な い で い て",
    SONG_TEXT_BRIDGE:    "も う す こ し だ け そ ば に い て ね わ す れ な い で き み の こ と だ け"
}

# ── Energy Curve ─────────────────────────────────────────────────────────────
# Maps each song section to its designated energy level
ENERGY_CURVE = {
    "Intro": "Niedrig",
    "Build-up": "Normal",
    "Verse": "Normal",
    "PreChorus": "Hoch",
    "Chorus": "Maximal",
    "Bridge": "Niedrig",
    "Outro": "Niedrig"
}
```

### Proposed Changes for `vocaloid_generator/melody_generator.py`
Add `adjust_contour` at the top level, and update the phrase loop in `generiere_melodie_sektion()`:
```python
def adjust_contour(section_type: str, phrase_notes: list, skala: list, p_idx: int, previous_question_last_pitch: int) -> int:
    """
    Enforces specific melodic contours (arch, fall, rise) on phrase notes in-place,
    and returns the final pitch if this is an even (question) phrase.
    """
    if not phrase_notes or len(phrase_notes) < 2:
        return phrase_notes[-1].pitch if (phrase_notes and p_idx % 2 == 0) else None

    pitches = [n.pitch for n in phrase_notes]
    n_notes = len(pitches)

    def get_shifted_pitch(reference_pitch, shift_steps):
        # Find nearest scale pitch to ensure scale locking
        ref_in_scale = min(skala, key=lambda p: abs(p - reference_pitch))
        idx = skala.index(ref_in_scale)
        new_idx = max(0, min(len(skala) - 1, idx + shift_steps))
        return skala[new_idx]

    # 1. Enforce section-specific contours
    if section_type == "Chorus":
        # Chorus (Arch contour): Peak pitch in second half, final pitch < first pitch
        if pitches[-1] >= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], -1)
            
        peak_idx = pitches.index(max(pitches))
        target_min_peak_idx = n_notes // 2
        if peak_idx < target_min_peak_idx:
            # Shift the peak to the second half, avoiding the very last note
            target_idx = random.randint(target_min_peak_idx, n_notes - 2) if target_min_peak_idx < n_notes - 1 else target_min_peak_idx
            current_max = max(pitches)
            pitches[target_idx] = get_shifted_pitch(current_max, 1)

    elif section_type in ("Bridge", "Outro"):
        # Bridge & Outro (Fall contour): Ends lower than it starts
        if pitches[-1] >= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], -1)

    elif section_type == "PreChorus":
        # PreChorus (Rise contour): Ends higher than it starts
        if pitches[-1] <= pitches[0]:
            pitches[-1] = get_shifted_pitch(pitches[0], 1)

    # 2. Enforce Question-Answer pairs (even = Q, odd = A)
    if p_idx % 2 == 1 and previous_question_last_pitch is not None:
        if pitches[-1] >= previous_question_last_pitch:
            pitches[-1] = get_shifted_pitch(previous_question_last_pitch, -1)

    next_question_pitch = pitches[-1] if p_idx % 2 == 0 else None

    # Write back adjusted pitches
    for i, note in enumerate(phrase_notes):
        note.pitch = pitches[i]

    return next_question_pitch
```
Inside `generiere_melodie_sektion()` in the phrase loop:
```python
    previous_question_last_pitch = None
    for p_idx, phrase in enumerate(phrasen):
        if not phrase:
            continue
        
        # ... [Motive selection remains same] ...
        
        phrase_notes = []
        mel_data_indices = []

        # ... [Syllable generation loop] ...
        for n_idx, silbe in enumerate(phrase):
            # ... [Pitch & Duration calculation remains same] ...
            
            n = pretty_midi.Note(
                velocity=velocity,
                pitch=pitch,
                start=aktuell,
                end=aktuell + dur_sek * legato
            )
            phrase_notes.append(n)
            
            # Record positions for syncing
            mel_data_indices.append(len(mel_data))
            mel_data.append((pitch, dur_viertel))
            
            # ... [Passing tone logic remains same, but do not add to phrase_notes] ...
            aktuell += dur_sek
            prev_idx = cur_idx
            
        # Apply contour adjustments
        previous_question_last_pitch = adjust_contour(
            section_type, phrase_notes, skala, p_idx, previous_question_last_pitch
        )
        
        # Sync the adjusted note pitches back into mel_data for synthesizer synthesis
        for idx, note in enumerate(phrase_notes):
            mel_idx = mel_data_indices[idx]
            dur_val = mel_data[mel_idx][1]
            mel_data[mel_idx] = (note.pitch, dur_val)
            
        notes.extend(phrase_notes)

        # Atem-Pause nach jeder Phrase
        if p_idx < len(phrasen) - 1:
            # ... [Silence buffer code remains same] ...
```

### Proposed Changes for `vocaloid_generator/chord_generator.py`
Add progression tables, resolution logic, and orchestrator check functions:
```python
# ── Named Chord Progressions with Functional Harmony ──────────────────────────
NAMED_PROGRESSIONS = {
    "dramatic minor": ["bVI_maj7", "bVII_7", "i_m7", "v_m7"],          # Kagerou Daze style
    "royal road j-pop": ["IV_maj7", "V_7", "iii_m7", "vi_m7"],         # Tell Your World style
    "rising pre-chorus": ["IV_maj7", "V_7", "vi_m7", "V_sus4"],       # Viva Happy style
    "emotional descend": ["vi_m7", "V_7", "IV_maj7", "iii_m7"],       # Melt style
    "bittersweet": ["IV_maj7", "V_7", "I_maj7", "vi_m7"],             # Odds & Ends style
    "wagyoku/japanese-modal": ["i_m7", "bVI_maj7", "bVII_7", "i_m7"]  # Senbonzakura style
}

def resolve_roman_progression(progression_chords: list, key: str) -> list:
    """Resolves a list of Roman numeral chords to (Note, ChordType) tuples."""
    root_offset = _NOTE_OFFSETS.get(key, 0)
    parsed_loop = []
    for chord_str in progression_chords:
        parts = chord_str.split("_")
        roman = parts[0]
        ctype = parts[1] if len(parts) > 1 else ""
        
        degree = MarkovChordGenerator.ROMAN_TO_DEGREE.get(roman, 0)
        note_idx = (root_offset + degree) % 12
        note_name = _NOTE_NAMES[note_idx]
        parsed_loop.append((note_name, ctype))
    return parsed_loop

def get_progression_roots(progression: list) -> list:
    """Returns the list of root note names from a resolved progression."""
    return [root for root, _ in progression]

def get_progression_roman_roots(progression_name: str) -> list:
    """Returns the list of Roman numeral roots for a named progression."""
    prog = NAMED_PROGRESSIONS.get(progression_name.lower().strip())
    if not prog:
        return []
    return [chord.split("_")[0] for chord in prog]
```
Update `get_progression()` to allow named chord selection:
```python
def get_progression(section_type: str, key: str = KEY, mode: str = MODE, style: str = "J-Pop Energy") -> list:
    # 1. Check if style matches a named progression (case-insensitive)
    normalized_style = style.lower().strip()
    if normalized_style in NAMED_PROGRESSIONS:
        return resolve_roman_progression(NAMED_PROGRESSIONS[normalized_style], key)
        
    # 2. Fallback to Markov chain generation
    return MarkovChordGenerator.generiere_loop(key, mode, section_type, length=4, style=style)
```

### Proposed Changes for `vocaloid_generator/orchestrator.py`
Modify `orchestrate_song()` to parse natural lyrics and handle section occurrences for energy and volume:
```python
def orchestrate_song(genre: str, bpm: float, structure: list, key: str, mode: str, section_config: dict) -> dict:
    # ... [Accumulator variables setup remains same] ...
    
    section_counts = {}
    
    for section_type in structure:
        # Track occurrence counts
        section_counts[section_type] = section_counts.get(section_type, 0) + 1
        occurrence = section_counts[section_type]
        
        config_sect = section_config.get(section_type, {"bars": 4, "has_vocals": True})
        bars = config_sect.get("bars", 4)
        has_vocals = config_sect.get("has_vocals", True)
        
        # ... [Chord progression resolution remains same] ...
        
        # Retrieve section-specific energy level from config
        import config
        base_energy = config.ENERGY_CURVE.get(section_type, "Normal")
        
        # Ensure the second Verse is quieter
        section_energy = base_energy
        if section_type == "Verse" and occurrence == 2:
            section_energy = "Niedrig"
            
        # ... [Piano, Bass, Guitar, Strings, Synth, Brass, Drums generation remain same] ...

        # Generate vocals using resolved lyric syllables and section energy
        if has_vocals:
            lyrics_raw = LYRICS_MAP.get(section_type, SONG_TEXT_VERSE)
            # Map Kanji lyrics to space-separated kana string
            lyrics_kana = getattr(config, "SONG_TEXT_KANA_MAP", {}).get(lyrics_raw, lyrics_raw)
            silben = lyrics_kana.split()
            
            mel_notes, sec_mel_daten, _ = generiere_melodie_sektion(
                bpm, silben, section_type, start_time, energy=section_energy, key=key, mode=mode, swing=0.0, style=beat_style
            )
            humanize_notes(mel_notes, genre=genre, instrument_type="melody", bpm=bpm)
            tracks["melody"].extend(mel_notes)
            gesamte_melodie_daten.extend(sec_mel_daten)
            gesamte_silben.extend(silben)

        # Velocity scaling mechanism for the second Verse (reduces all instruments by 25%)
        if section_type == "Verse" and occurrence == 2:
            sect_dur = bars * bar_duration
            for inst_name, note_list in tracks.items():
                if inst_name in ("silben", "melody_data"):
                    continue
                for note in note_list:
                    if start_time <= note.start < (start_time + sect_dur):
                        note.velocity = max(40, int(note.velocity * 0.75))

        start_time += bars * bar_duration
```

---

## 5. Verification Method
Verify the design implementation with these three checks:
1. **Melody Contour Check**:
   Write a validation script `test_phrase_contour.py` that generates a song and checks the following assertions:
   ```python
   # Assert Chorus Arch Contour
   chorus_melody = [n for n in melody_notes if in_chorus_time_window(n)]
   assert np.argmax([n.pitch for n in chorus_melody]) >= len(chorus_melody) // 2
   assert chorus_melody[-1].pitch < chorus_melody[0].pitch
   
   # Assert PreChorus Rise Contour
   prechorus_melody = [n for n in melody_notes if in_prechorus_time_window(n)]
   assert prechorus_melody[-1].pitch > prechorus_melody[0].pitch
   ```
2. **Named Progression Roots Check**:
   Execute a python test to assert that named progressions resolve correctly and can be verified:
   ```python
   from chord_generator import get_progression, get_progression_roots
   prog = get_progression("Chorus", "A", "minor", "dramatic minor")
   roots = get_progression_roots(prog)
   assert roots == ["F", "G", "A", "E"] # bVI, bVII, i, v in A minor
   ```
3. **Run Suite**:
   Run the existing suite `python vocaloid_generator/test_orchestrator.py` to ensure no regression in existing instruments' generation.
