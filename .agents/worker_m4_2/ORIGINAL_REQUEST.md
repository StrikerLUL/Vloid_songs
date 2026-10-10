## 2026-07-06T09:28:42Z
You are a teamwork_preview_worker. Your working directory is c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m4_2\.
Your task is to implement the Song Structure & Dynamic Arrangement features for Milestone 4 in `config.py`, `beat_generator.py`, and `orchestrator.py` according to the designs in `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\explorer_m4_1\handoff.md`:

1. Update `config.py`:
   - Add `"Drop"` section right before the final `"Chorus"` in `SONG_STRUCTURE`.
   - Set `"Drop"` config in `SECTION_CONFIG` to 2 bars, has_vocals=False.
   - Add `"Drop"` to `ENERGY_CURVE` mapped to `"Niedrig"`.

2. Update `beat_generator.py`:
   - Update `generiere_beat_sektion` signature to accept `transition_to_chorus=False`.
   - Add kick-only generation logic for `"Drop"`.
   - Change ghost snare velocity range to `20-40` (previously 38-56).
   - Only play drum fills in the last bar of a section if `transition_to_chorus` is `True`.
   - Implement a velocity crescendo across bars for the `"PreChorus"` section (using `crescendo_factor` or similar).

3. Update `orchestrator.py`:
   - Implement `get_section_key(section_type, occurrence, original_key, original_mode)` to modulate the final Chorus by +1 semitone (e.g. from A to A# / A# to B).
   - Filter generated instruments per section using `ALLOWED_INSTRUMENTS` density mappings (Intro/Outro: 2, Verse: 4, PreChorus: 5, Chorus: all, Bridge: 3, Drop: kick + bass only).
   - Fix `STRICT_SCALE_LOCKING` to be section-key-aware (look up note starts against section times in `sections_timeline` to check if a note is modulated, and lock it to its respective modulated scale).
   - Implement a post-processing loop at the end of `orchestrate_song()` to apply `SECTION_VELOCITY_OFFSETS` (including the final Chorus +12 boost) to all track notes, ensuring they aren't overwritten by the humanizer's defaults.

Run `python test_imports.py` and `python test_orchestrator.py` to ensure compiling and executing works.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your handoff report to `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m4_2\handoff.md`. When done, report back to the Project Orchestrator at conversation ID af64d191-fd94-45f1-9af8-43013a371330.
