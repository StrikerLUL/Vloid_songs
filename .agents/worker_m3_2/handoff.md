# Handoff Report: Sound Design & Humanization (Milestone 3)

## 1. Observation

During the task execution, the following files and code locations were observed and modified:

1. **`vocaloid_generator/humanizer.py` (lines 104-157)**:
   - Observed that `humanize_notes` previously only looped through notes and called `humanize_note` individually.
   - Verbatim original code:
     ```python
     def humanize_notes(notes: list, genre: str, instrument_type: str, bpm: float, swing: float = None) -> list:
         for note in notes:
             humanize_note(note, genre, instrument_type, bpm, swing)
         return notes
     ```

2. **`vocaloid_generator/melody_generator.py` (lines 454-467)**:
   - Observed that the inter-phrase `atem` breath pause was calculated relative to `viertel` beats without a strict seconds-based clamp.
   - Verbatim original code:
     ```python
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

3. **`vocaloid_generator/orchestrator.py` (lines 20-58, 69-82, 308-376)**:
   - Observed `PATTERN_MAP` defining genre mappings.
   - Observed `save_midi_track` writing notes into a single instrument.
   - Observed MIDI exporting phase in `orchestrate_song` where `synth.mid` is written.

4. **`vocaloid_generator/bass_generator.py` (lines 159-189)**:
   - Observed `generate_bass` containing various pattern conditions (`root`, `driving`, `sync`, etc.).

5. **`vocaloid_generator/synth_generator.py` (lines 131-153)**:
   - Observed `generate_synth` containing various pattern conditions (`riser`, `pad`, `pluck`, `arp`, etc.).

---

## 2. Logic Chain

1. **Vocal Melody Rubato and Velocity Shaping**:
   - *Observation*: Melody notes require phrase grouping to apply rubato (rushing/dragging at start/end of phrases, on-time in the middle) and velocity shaping.
   - *Deduction*: We sort notes in `humanize_notes` chronologically and group them into phrases based on silence gaps $\ge 150\text{ms}$ (0.15 seconds).
   - *Rubato*: Using $Offset(i) = R \cdot \cos(\pi \cdot x)$ where $R \in [\pm 10\text{ms}, \pm 30\text{ms}]$ and $x = i / (N - 1)$, we achieve dragging or rushing at the boundaries ($x \in \{0, 1\}$) and on-time in the middle ($x = 0.5$).
   - *Velocity*: Using a multiplier of $0.8 + 0.35 \cdot \sin(\pi \cdot x)$ scales velocities to be quiet ($0.8\text{x}$) at the boundaries and loud ($1.15\text{x}$) in the middle of each phrase.

2. **Breath Pause Calculations**:
   - *Observation*: Breath pauses in beats scale with BPM, potentially moving outside the required $[0.15\text{s}, 0.5\text{s}]$ limits.
   - *Deduction*: We generate the pause in seconds (`atem_sek`), clamp it strictly to $[0.15, 0.5]$ seconds, and then divide it by `viertel` to obtain the duration in beats for `mel_data`.

3. **Vocal Synthesizer Synchronization**:
   - *Observation*: Re-ordering, shifting, and stretching notes in `humanize_notes` causes drift from the synthesized vocal audio if the raw generator data `gesamte_melodie_daten` is not synchronized.
   - *Deduction*: We reconstruct `gesamte_melodie_daten` after all humanization and post-processing steps. We sort final melody notes chronologically, calculate gap-based silences, and use their exact start and end times to create the sequential `(pitch, duration)` list.

4. **Wobble Bass**:
   - *Observation*: `pretty_midi.Note` objects do not natively store control changes, and `generate_bass` must retain its original signature.
   - *Deduction*: We attach a custom `control_changes` attribute to each `pretty_midi.Note` in `"wobble"` mode.
   - *Modulation*: We sample a 2 Hz LFO every 50ms ($0.05$ seconds), calculate the value using $65 + 35 \cdot \sin(2\pi \cdot 2 \cdot t)$, and append `ControlChange` events (CC 74 for Cutoff, CC 11 for Expression). We then modify `save_midi_track` to extract and write these CCs to the MIDI instrument.

5. **Stereo Wide Saw Lead**:
   - *Observation*: Stereophonic widening is needed for J-Pop and EDM Chorus sections.
   - *Deduction*: We split Chorus synth notes into left and right instruments in `synth.mid`, panning the left hard left (CC 10 = 16) and the right hard right (CC 10 = 112). We apply a 12ms Haas-effect delay to the right track (`start + 0.012`, `end + 0.012`) and scale its velocity slightly down (`velocity - 5`).

---

## 3. Caveats

- **Monocompatibility**: Stereophonic Haas delays can cause comb filtering in mono systems, but this is a standard production trade-off.
- **Synthesizer CC Support**: Audibility of the wobble effect is dependent on downstream synth capability to interpret CC 74 (Filter Cutoff) and CC 11 (Expression).

---

## 4. Conclusion

All requirements for Milestone 3 Sound Design & Humanization have been successfully implemented:
- Extended phrase-based humanization (Rubato & Velocity shaping) in `humanizer.py`.
- BPM-independent clamped breath pause in `melody_generator.py`.
- Pattern maps, vocal synth sync, and Haas stereo double-tracking in `orchestrator.py`.
- LFO-driven Wobble Bass with CC 74/11 in `bass_generator.py` and `orchestrator.py`.
- Kawaii staccato plucks and wide saw lead chords in `synth_generator.py`.

---

## 5. Verification Method

To verify the changes, inspect the modified files and execute tests:
1. **Import and Integration Tests**:
   - Run `pytest test_imports.py` and `pytest test_orchestrator.py` in the `vocaloid_generator/` directory.
2. **Timing & Panning Auditing**:
   - Inspect the exported `synth.mid` file for J-Pop or EDM songs with a Chorus. Verify that two tracks are present with CC 10 (pan) values of 16 and 112 respectively, and that notes on the right track are offset by exactly 12ms.
   - Inspect `bass.mid` for J-Pop or EDM songs with a Chorus. Verify that CC 74 and CC 11 messages are present, oscillating at 2 Hz.
