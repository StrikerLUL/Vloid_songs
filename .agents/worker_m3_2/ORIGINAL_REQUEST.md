## 2026-07-06T09:22:35Z

You are a teamwork_preview_worker. Your working directory is c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m3_2\.
Your task is to implement the Sound Design & Humanization features for Milestone 3 according to the designs in `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\explorer_m3_1\handoff.md`:

1. Update `humanizer.py`:
   - Extend `humanize_notes` so that if `instrument_type` is `"melody"`:
     * Sort notes chronologically.
     * Group notes into phrases based on silence gaps >= 150ms.
     * Apply Rubato: ±10-30ms timing offset correlated to note position within the phrase (drag/rush at phrase start/end, on-time in the middle).
     * Apply Velocity shaping: first/end notes quiet (0.8x), middle notes loud (1.15x).

2. Update `melody_generator.py`:
   - Modify the inter-phrase `atem` (breath pause) duration inside `generiere_melodie_sektion` to be calculated in seconds, clamped strictly to `[0.15, 0.5]`, and then converted to beats.

3. Update `orchestrator.py`:
   - Update `PATTERN_MAP` for J-Pop and EDM to map:
     * Chorus `"bass": "wobble"`
     * Chorus `"synth": "wide_saw"`
     * PreChorus `"synth": "staccato_pluck"`
   - Inside `orchestrate_song()`, implement vocal synthesizer synchronization. Reconstruct `gesamte_melodie_daten` from the humanized `tracks["melody"]` notes by sorting, calculating gap-based pauses, and using the exact starts/ends of the humanized notes.
   - When exporting `synth.mid` in `orchestrate_song()`, if the genre is J-Pop or EDM and a Chorus section is present, split the synth notes into hard-panned left and right MIDI instruments, apply a 12ms Haas-effect delay to the right track, and save them in the same `synth.mid` file.

4. Update `bass_generator.py`:
   - Add the `"wobble"` pattern type inside `generate_bass()`. Sample a 2 Hz LFO every 50ms (0.05 seconds) and write MIDI Control Change (CC 74 for Cutoff, CC 11 for Expression) events into the instrument object's `control_changes` list (e.g. `notes.append` notes as normal, and append CCs using `instrument.control_changes.append(pretty_midi.ControlChange(number=74, value=value, time=time))`). Make sure you have access to the instrument or that `generate_bass` can return CCs, or that the CCs can be attached to the notes or generated on the track in `orchestrator.py`!
     * Wait, how are CCs added? Let's check how the instrument is created or if `generate_bass` returns a note list. Yes, `generate_bass` returns a note list. In `orchestrator.py`, the notes are added to `tracks["bass"]`, and when exporting `bass.mid` (in `save_midi_track`), an `Instrument` object is created:
       ```python
       inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
       inst.notes = notes
       ```
       If we want to support control changes on the bass track, we can return the CCs or append them. Or we can update `generate_bass` to return notes, and in `orchestrator.py`, we can also collect or generate CCs for wobble bass, or we can change `generate_bass` signature, or return a class/tuple. But wait, existing function signatures must be preserved!
       "All changes must remain backward-compatible (existing function signatures preserved)."
       If `generate_bass` signature must be preserved, it must return a list of `pretty_midi.Note` objects. If so, how do we return CCs?
       Ah! In `pretty_midi`, each `Note` object does NOT have a control changes list. But wait! Since `pretty_midi.Note` objects are added to a list, we can store the CC events as custom attributes on the `Note` object, or on the list!
       Or wait! The `generate_bass` function can return notes, and inside `orchestrator.py`, when exporting the track `save_midi_track`, we can check if any notes have CC attributes, or we can generate the CCs dynamically in `orchestrator.py` during `orchestrate_song()` or `save_midi_track()`!
       Generating the CCs in `orchestrator.py` for the bass track during Chorus sections where `b_pattern == "wobble"` is much cleaner and doesn't break any signatures!
       Let's suggest that to the worker.

5. Update `synth_generator.py`:
   - Add the `"staccato_pluck"` pattern inside `generate_synth()` with very short durations (e.g. 50ms - 80ms) and dynamic velocity accents.
   - Add the `"wide_saw"` pattern inside `generate_synth()` which generates the notes for the saw lead (sustained or arpeggiated/rhythmic chords).

Verify compiling and run `test_imports.py` and `test_orchestrator.py`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your handoff report to `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m3_2\handoff.md`. When done, report back to the Project Orchestrator at conversation ID af64d191-fd94-45f1-9af8-43013a371330.
