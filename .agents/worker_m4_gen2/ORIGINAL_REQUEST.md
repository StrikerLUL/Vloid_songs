## 2026-07-06T21:32:33Z
You are the Worker for Milestone 4.
Your working directory is: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m4_gen2\
Global Project Plan: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\PROJECT.md

Task:
1. Implement `vocaloid_generator/soundfont_renderer.py`.
   - This script must use `pyfluidsynth` (or call `pretty_midi`'s fluidsynth rendering method) to render MIDI tracks to WAV using `vocaloid_generator/soundfont.sf2`.
   - It must map instruments to the correct MIDI channels and Program Changes (e.g., Drums=Ch9, Bass=Ch1/Prg33, Piano=Ch0/Prg1, Guitar=Ch2/Prg25, Strings=Ch3/Prg49, Synth=Ch4/Prg81, Brass=Ch5/Prg62, Melody=Ch6/Prg81).
   - Ensure the program is set correctly for all MIDI tracks in the `pretty_midi.PrettyMIDI` object.
2. Update `vocaloid_generator/mixer.py`:
   - Import `soundfont_renderer` and prioritize it in the `midi_zu_wav` function, with the existing sine wave synthesis (`midi_data.synthesize(...)`) as a fallback if fluidsynth fails or is missing.
   - Verify that panning (`apply_stereo_pan`), sidechain compression (`apply_kick_sidechain`), and mastering pedalboard are fully compliant with reference mix schemas and calibrated correctly.
3. Validate files for correct syntax.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Handoff:
Write your handoff.md in your working directory and message the orchestrator (conversation ID: 1dff83d9-ecb9-41f7-88bc-abebd5f1ecc5) with a summary when complete.
