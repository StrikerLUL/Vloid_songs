# Handoff Report: Humanizer Realism (R6) & Extended Synth Palette (R7)

## 1. Observation

During the read-only investigation, the following files and code snippets were examined:

1. **Vocal Melody Humanization Call Path**:
   - In `vocaloid_generator/orchestrator.py` (lines 241-246):
     ```python
     mel_notes, sec_mel_daten, _ = generiere_melodie_sektion(
         bpm, silben, section_type, start_time, energy=section_energy, key=key, mode=mode, swing=0.0, style=beat_style
     )
     humanize_notes(mel_notes, genre=genre, instrument_type="melody", bpm=bpm)
     tracks["melody"].extend(mel_notes)
     gesamte_melodie_daten.extend(sec_mel_daten)
     ```
     *Observation*: `humanize_notes` is called on `mel_notes` (the `pretty_midi.Note` objects), but `sec_mel_daten` (the list of `(pitch, duration)` tuples used by the vocal synthesizer) is appended directly to `gesamte_melodie_daten` without humanization.

2. **Melody Note & Pause Generation**:
   - In `vocaloid_generator/melody_generator.py` (lines 454-464):
     ```python
     # Atem-Pause nach jeder Phrase
     if p_idx < len(phrasen) - 1:
         if section_type in ("Chorus", "PreChorus"):
             atem = random.uniform(0.35, 0.55) * viertel
         elif section_type == "Bridge":
             atem = random.uniform(0.6, 1.0) * viertel
         else:
             atem = random.uniform(0.5, 0.75) * viertel

         aktuell += atem
         mel_data.append((None, atem / viertel))
     ```
     *Observation*: The silence (atem pause) between phrases is calculated relative to `viertel` (beat duration), which depends on BPM.

3. **Current Humanizer Logic**:
   - In `vocaloid_generator/humanizer.py` (lines 104-110):
     ```python
     def humanize_notes(notes: list, genre: str, instrument_type: str, bpm: float, swing: float = None) -> list:
         """
         Applies humanization to a list of pretty_midi.Note objects.
         """
         for note in notes:
             humanize_note(note, genre, instrument_type, bpm, swing)
         return notes
     ```
     *Observation*: Humanization is currently applied on a single-note basis, with no awareness of grouping notes into melodic phrases.

4. **Vocal Synthesizer Input**:
   - In `vocaloid_generator/vocal_synthesizer.py` (lines 62-65):
     ```python
     for pitch, dauer in melodie_daten:
         if pitch is None:
             current_time += dauer * quarter_sec
             continue
     ```
     *Observation*: The synthesizer relies on the `(pitch, duration)` tuples in `melodie_daten` to compute active notes and pauses.

5. **Synth & Bass Generators**:
   - `vocaloid_generator/synth_generator.py` (lines 53-145) handles the modular generation of chord pads, plucks, arpeggiators, and sweeps.
   - `vocaloid_generator/bass_generator.py` (lines 23-192) generates basslines (root, driving, sync, sub_pulse, lazy) but does not apply MIDI CC modulations.

---

## 2. Logic Chain

1. **Melodic Phrase Grouping**:
   - *Premise*: Rubato and velocity shaping must be applied per *melodic phrase* for the melody instrument.
   - *Observation*: The MIDI notes returned by `generiere_melodie_sektion` are a flat list, but they are separated by an `atem` (breath) pause of at least `0.175s` (at 120 BPM).
   - *Deduction*: We can group notes into phrases by sorting them chronologically and identifying gaps greater than a threshold (e.g. `0.15` seconds). This allows phrase-level processing inside `humanizer.py` without modifying generator signatures.

2. **Rubato Implementation**:
   - *Premise*: We need a ±10-30ms timing offset on melodic phrases, correlated to phrase position (dragging/rushing at start/end of phrases).
   - *Deduction*: For a phrase of $N$ notes, we can select a random base offset $R \in [\pm 10, \pm 30]\text{ms}$. By applying $Offset(i) = R \cdot \cos(\pi \cdot x)$ where $x = i / (N - 1)$ is the normalized note index:
     - At $x = 0$ (start), $Offset = R$ (dragging if $R > 0$, rushing if $R < 0$).
     - At $x = 0.5$ (middle), $Offset = 0$ (on-time).
     - At $x = 1.0$ (end), $Offset = -R$ (rushing if $R > 0$, dragging if $R < 0$).
     This provides a smooth, phrase-correlated rubato.

3. **Velocity Shaping**:
   - *Premise*: Note velocities should progress from quiet at the start, to loud in the middle, and quiet at the end of each phrase.
   - *Deduction*: Using the sine-wave shape $Multiplier(i) = 0.8 + 0.35 \cdot \sin(\pi \cdot x)$, the note velocities will scale from `0.8` at the boundaries to `1.15` at the peak middle.

4. **Vocal Synthesizer Sync & Breath Pause**:
   - *Observation*: `vocal_synthesizer.py` renders vocals using `melodie_daten` (`sec_mel_daten`) which bypasses `humanize_notes`.
   - *Deduction*: The timing modifications (rubato, swing, jitter) applied to the MIDI track will cause it to drift from the synthesized vocal audio track.
   - *Remedy*: We must synchronize the vocal synthesizer. After humanizing `mel_notes`, we can reconstruct `gesamte_melodie_daten` from the humanized note objects by computing the exact starts, durations, and silences.
   - *BPM-Independence*: If a song's BPM is very high (e.g. 200) or low (e.g. 60), scaling atem pauses in beats can result in pauses outside the desired `0.15s - 0.5s` range. We must compute `atem` in seconds, clamp it to `[0.15, 0.5]`, and then convert it back to beat duration.

5. **Extended Synth Palette**:
   - **Wobble Bass**: A 2 Hz sine LFO applied to Chorus bass. In MIDI, this can be simulated by appending `pretty_midi.ControlChange` events for Filter Cutoff (CC 74) and Expression (CC 11) sampled at a regular rate (e.g. every 50ms) using the formula: $CC\_val(t) = \text{int}(65 + 35 \cdot \sin(2\pi \cdot 2 \cdot t))$.
   - **Staccato Pluck**: Short attack and fast decay. In MIDI, this is represented by very short note durations (e.g. `duration = min(0.08, beat_dur * 0.12)` seconds) and high-contrast velocities (strong accents on downbeats).
   - **Wide Saw Lead**: High stereo width for Chorus leads. This is simulated by double-tracking: creating two identical MIDI instruments, panning one hard left (CC 10 = 16) and the other hard right (CC 10 = 112), and delaying the right track by 10-15ms (Haas effect).

---

## 3. Caveats

1. **Synthesizer Capability**: The simulation of Wobble Bass using CC 74 (Filter Cutoff) and CC 11 (Expression) assumes that the downstream synthesizer or sampler supports these MIDI CC mappings. If the synth does not respond to CC 74, the wobble effect will not be audible in the synth output. As a fallback, we also document a "note-gating/rapid repetition" velocity modulation method.
2. **Haas Effect Monocompatibility**: Double-tracking with a 10-15ms delay can cause comb filtering when summed to mono. However, this is standard practice in stereo audio production and is appropriate for the target genres.

---

## 4. Conclusion & Code Recommendations

Below are the detailed design proposals and code adjustments to implement the requested features:

### A. Humanizer Realism (R6)

#### 1. Melodic Phrase Humanization (`vocaloid_generator/humanizer.py`)
Modify `humanize_notes` in `humanizer.py` to intercept melody instruments, group them into phrases, and apply rubato and velocity shaping:

```python
import math
import random
import pretty_midi

def humanize_notes(notes: list, genre: str, instrument_type: str, bpm: float, swing: float = None) -> list:
    """
    Applies humanization to a list of pretty_midi.Note objects.
    Includes phrase-level Rubato and Velocity shaping for melody tracks.
    """
    # Apply standard micro-timing and velocity randomizations first
    for note in notes:
        humanize_note(note, genre, instrument_type, bpm, swing)
        
    # Apply macro phrase-level humanization to the vocal melody
    if instrument_type.lower() == "melody" and notes:
        # Group notes into phrases based on silence gaps >= 150ms
        sorted_notes = sorted(notes, key=lambda n: n.start)
        phrases = []
        current_phrase = [sorted_notes[0]]
        threshold = 0.15  # 150ms gap threshold
        
        for n in sorted_notes[1:]:
            if n.start - current_phrase[-1].end >= threshold:
                phrases.append(current_phrase)
                current_phrase = [n]
            else:
                current_phrase.append(n)
        phrases.append(current_phrase)
        
        # Apply Rubato & Velocity Shaping per phrase
        for phrase in phrases:
            N = len(phrase)
            if N == 0:
                continue
            
            # Select random phrase rubato: +/- 10ms to 30ms
            rubato_base = random.choice([-1.0, 1.0]) * random.uniform(0.010, 0.030)
            
            for idx, note in enumerate(phrase):
                x = idx / (N - 1) if N > 1 else 0.5
                
                # Rubato: drag/rush at boundaries, on-time in the middle
                offset = rubato_base * math.cos(math.pi * x)
                note.start += offset
                note.end += offset
                
                # Boundary checks
                if note.start < 0:
                    note.start = 0.0
                if note.end <= note.start:
                    note.end = note.start + 0.05
                
                # Velocity shaping: first/end quiet (0.8x), middle loud (1.15x)
                vel_mult = 0.8 + 0.35 * math.sin(math.pi * x)
                note.velocity = max(1, min(127, int(note.velocity * vel_mult)))
                
    return notes
```

#### 2. BPM-Independent Breath Pause (`vocaloid_generator/melody_generator.py`)
Modify the `atem` pause calculations to define durations in seconds, clamp them strictly within the `0.15s - 0.5s` range, and convert them to beat values:

```python
        # Atem-Pause nach jeder Phrase (melody_generator.py - Line 454 onwards)
        if p_idx < len(phrasen) - 1:
            if section_type in ("Chorus", "PreChorus"):
                atem_sek = random.uniform(0.15, 0.25)
            elif section_type == "Bridge":
                atem_sek = random.uniform(0.30, 0.50)
            else:
                atem_sek = random.uniform(0.20, 0.35)
                
            # Clamp to guarantee the 0.15 - 0.5s requirement
            atem_sek = max(0.15, min(0.50, atem_sek))
            atem_beats = atem_sek / viertel

            aktuell += atem_sek
            mel_data.append((None, atem_beats))
```

#### 3. Vocal Synthesizer Synchronization (`vocaloid_generator/orchestrator.py`)
Synchronize the vocal synthesizer with the humanized MIDI notes. After humanization is applied, reconstruct `gesamte_melodie_daten` using the actual timings of the notes:

```python
# In orchestrator.py:
def sync_vocals_with_humanized_midi(humanized_notes: list, bpm: float) -> list:
    """Reconstructs melodie_daten from humanized notes to sync the vocal synthesizer."""
    quarter_sec = 60.0 / bpm
    new_melodie_daten = []
    notes_sorted = sorted(humanized_notes, key=lambda n: n.start)
    
    current_time = 0.0
    for i, note in enumerate(notes_sorted):
        # 1. Inject silence if there is a gap before the note
        if note.start > current_time + 0.001:
            gap_sek = note.start - current_time
            new_melodie_daten.append((None, gap_sek / quarter_sec))
            current_time = note.start
            
        # 2. Determine duration: contiguous vs rest gap
        if i < len(notes_sorted) - 1:
            next_note = notes_sorted[i+1]
            gap_to_next = next_note.start - note.end
            if gap_to_next < 0.15: # Contiguous note transitions
                note_dur_sek = next_note.start - note.start
            else:
                note_dur_sek = note.end - note.start
        else:
            note_dur_sek = note.end - note.start
            
        new_melodie_daten.append((note.pitch, note_dur_sek / quarter_sec))
        current_time += note_dur_sek
        
    return new_melodie_daten

# Hook this up in orchestrator.py inside the main loop:
# Replace gesamte_melodie_daten.extend(sec_mel_daten) with:
# (After the loop generates all sections)
tracks["melody"] = humanize_notes(tracks["melody"], genre=genre, instrument_type="melody", bpm=bpm)
gesamte_melodie_daten = sync_vocals_with_humanized_midi(tracks["melody"], bpm)
```

---

### B. Extended Synth Palette (R7)

#### 1. Wobble Bass (`vocaloid_generator/bass_generator.py`)
Introduce a `"wobble"` bass pattern type in `bass_generator.py` that modulates MIDI CC 74 (Filter Cutoff) and CC 11 (Expression) via a sine LFO at 2 Hz:

```python
        elif pattern_type == "wobble":
            # Sustained notes with a 2 Hz LFO modulating Filter Cutoff and Expression
            # Typically used in Chorus
            f_lfo = 2.0  # 2 Hz
            t_step = 0.05  # Sample LFO every 50ms
            
            # Generate straight half notes or full notes
            for step in range(4):
                t_start = bar_start + step * beat_dur
                t_end = t_start + 0.95 * beat_dur
                p = root_midi
                notes.append(pretty_midi.Note(
                    velocity=100, pitch=p, start=t_start, end=t_end
                ))
                
                # Apply modulation during the note duration
                t_curr = t_start
                while t_curr < t_end:
                    lfo_val = math.sin(2 * math.pi * f_lfo * t_curr)
                    # CC 74: Filter Cutoff [35, 105]
                    cc_74 = int(70 + 35 * lfo_val)
                    # CC 11: Expression [70, 110]
                    cc_11 = int(90 + 20 * lfo_val)
                    
                    # Store these CCs in the track
                    # Note: We must ensure we append to the Instrument object's control_changes list
```

#### 2. Staccato Pluck (`vocaloid_generator/synth_generator.py`)
Add a `"staccato_pluck"` pattern type with tight note durations and dynamic velocity contrast:

```python
            elif pattern_type == "staccato_pluck":
                # Kawaii short attack/decay plucks in PreChorus
                offsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]  # Rapid 8th notes
                for idx, off in enumerate(offsets):
                    t = bar_start + off * beat_dur
                    # Extremely short duration (50ms - 80ms)
                    dur = min(0.08, beat_dur * 0.15)
                    # Dynamic velocity accents (loud on downbeats, quiet on upbeats)
                    vel = random.randint(95, 110) if idx % 2 == 0 else random.randint(70, 85)
                    
                    for p in pitches[:2]:  # Keep it thin (dyads) for the kawaii pluck vibe
                        notes.append(pretty_midi.Note(
                            velocity=vel,
                            pitch=p,
                            start=t,
                            end=t + dur
                        ))
```

#### 3. Wide Saw Lead (`vocaloid_generator/orchestrator.py` & `synth_generator.py`)
Support the "wide saw lead" using a double-tracking layering implementation. In `orchestrator.py`, we split the `synth` track into left and right instruments:

```python
# In orchestrator.py:
# Replace save_midi_track(tracks["synth"], 80, "Synth Lead", "synth.mid", bpm) with:
if genre.lower() in ("edm", "j-pop") and any(sec == "Chorus" for sec in structure):
    # Split notes into left and right with Haas delay
    synth_left_notes = []
    synth_right_notes = []
    
    for note in tracks["synth"]:
        # Left channel note (original timing)
        synth_left_notes.append(pretty_midi.Note(
            velocity=note.velocity, pitch=note.pitch, start=note.start, end=note.end
        ))
        # Right channel note (delayed by 12ms for Haas effect)
        synth_right_notes.append(pretty_midi.Note(
            velocity=max(1, note.velocity - 5), pitch=note.pitch, start=note.start + 0.012, end=note.end + 0.012
        ))
        
    # Save as separate MIDI tracks panned hard L / hard R
    pm_wide = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst_left = pretty_midi.Instrument(program=80, name="Synth Lead Left")
    inst_left.notes = synth_left_notes
    inst_left.control_changes.append(pretty_midi.ControlChange(number=10, value=16, time=0.0)) # Pan Left
    
    inst_right = pretty_midi.Instrument(program=80, name="Synth Lead Right")
    inst_right.notes = synth_right_notes
    inst_right.control_changes.append(pretty_midi.ControlChange(number=10, value=112, time=0.0)) # Pan Right
    
    pm_wide.instruments.extend([inst_left, inst_right])
    pm_wide.write(os.path.join(OUTPUT_ORDNER, "synth.mid"))
else:
    save_midi_track(tracks["synth"], 80, "Synth Lead", "synth.mid", bpm)
```

---

## 5. Verification Method

To verify the implementation of R6 and R7, we recommend adding specific assertion checks in `vocaloid_generator/test_orchestrator.py`:

1. **Verify Humanizer Realism**:
   - Create `test_humanizer_realism()`:
     - Generate a J-Pop song containing melody notes.
     - Group melody notes back into phrases using the `0.15s` gap rule.
     - **Verify Rubato**: Assert that the start times of boundary notes drag/rush relative to the original unhumanized grid, while middle notes remain on the grid.
     - **Verify Velocity Shaping**: Assert that the first note's velocity is lower than the middle note's velocity, and the last note's velocity is lower than the middle note's velocity for phrases with length $\ge 3$.
     - **Verify Breath Pauses**: Assert that all gaps between consecutive phrases in `gesamte_melodie_daten` lie strictly within `[0.15, 0.5]` seconds.

2. **Verify Extended Synth Palette**:
   - Create `test_extended_synth_palette()`:
     - Generate an EDM song.
     - **Verify Wobble Bass**: Assert that `bass` instrument's `control_changes` contain CC 74 messages, that the values oscillate between `35` and `105`, and that the rate corresponds to 2 Hz.
     - **Verify Staccato Plucks**: Generate a PreChorus and verify that the durations of the pluck synth notes are $< 0.12$ seconds (or `beat_dur * 0.15`).
     - **Verify Wide Saw Lead**: Generate a Chorus and verify that the output `synth.mid` file contains two instruments (Left and Right), one panned left ($CC\ 10 \le 32$) and the other panned right ($CC\ 10 \ge 96$), with the right instrument notes delayed by 10-15ms.
