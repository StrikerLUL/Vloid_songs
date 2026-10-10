# Challenge Report

## Challenge Summary

**Overall risk assessment**: HIGH

Due to Python's module import resolution rules, the J-Pop orchestrator runs with `STRICT_SCALE_LOCKING = False` during the programmatic test suite, which leads to chromatic passing tones being generated and violating the scale locking test. Additionally, fast tempos with large pitch jumps (e.g. octave hooks on 16th notes) exceed the 15.0 Hz voiced pitch jump threshold, and modal scales (phrygian, dorian) fall back to major chords, introducing out-of-scale pitches.

## Challenges

### [High] Challenge 1: Duplicate Config Import Bug Bypass

- **Assumption challenged**: The test suite assumes that setting `vocaloid_generator.config.STRICT_SCALE_LOCKING = True` globally activates scale locking.
- **Attack scenario**: `test_jpop_verification.py` adds both the workspace root and the `vocaloid_generator/` directory to `sys.path`. It imports `vocaloid_generator.config` as the package config. However, `orchestrator.py` and other modules do `import config` which loads the module as the standalone `config` module. These are separate entries in `sys.modules`. Modifying one does not affect the other, leaving `STRICT_SCALE_LOCKING = False` on the instance used by the orchestrator.
- **Blast radius**: Chromatic passing notes are generated, violating the strict scale lock, causing `test_midi_scale_locking` to fail.
- **Mitigation**: Standardize imports or set `STRICT_SCALE_LOCKING = True` on both `sys.modules['config']` and `sys.modules['vocaloid_generator.config']` in test runners.

### [Medium] Challenge 2: Sharp Legato Pitch Jumps on Rapid Short Notes

- **Assumption challenged**: The F0 synthesis assumes that interpolating over `glide_len = min(16, len // 2)` frames prevents voiced pitch jumps >= 15.0 Hz.
- **Attack scenario**: At 160 BPM, a 16th note (0.25 beats) lasts ~93.75ms (18 frames). Thus, `glide_len` is 9 frames. An octave-hook transition of 147.33 Hz (e.g. A4 to D5 in Chorus) over 9 frames results in a frame-to-frame step of 16.37 Hz. This exceeds the 15.0 Hz threshold in `test_vocal_pitch_transitions`.
- **Blast radius**: `test_vocal_pitch_transitions` fails under J-Pop default fast tempo configurations.
- **Mitigation**: Dynamically increase the number of legato glide frames for larger pitch intervals, or increase the threshold in the test script for very short notes.

### [Medium] Challenge 3: Chord Generator Mode Divergence for Modal Scales

- **Assumption challenged**: The J-Pop chord progression generator assumes that non-minor scales (like phrygian or dorian) can safely fall back to Major scale chord transitions.
- **Attack scenario**: If `mode` is `"phrygian"`, `mode == "minor"` resolves to `False`. The Markov generator defaults to Major transitions, generating Major chord progressions relative to the phrygian root (e.g., A maj7, B 7 in E phrygian). These chords contain out-of-scale notes (C#, G#, D#, F#) relative to the E phrygian scale (E, F, G, A, B, C, D).
- **Blast radius**: All instrument tracks generated for phrygian/dorian modes contain out-of-scale notes, failing the scale lock checks.
- **Mitigation**: Implement dedicated Markov transition matrices for modal scales or enforce scale-locking inside `chord_generator.py` for all modes.

### [Low] Challenge 4: Raw NEUTRINO Output Clipping and Click Checks

- **Assumption challenged**: Raw output WAV from the NEUTRINO engine satisfies clipping and boundary anti-click checks.
- **Attack scenario**: The NEUTRINO wrapper `neutrino_synthese` in `vocal_synthesizer.py` does not apply normalization or linear fade-ins/outs at syllable boundaries. If raw NEUTRINO output clips or contains clicks, it will fail `test_vocal_clipping`.
- **Blast radius**: E2E runs using the NEUTRINO engine fail verification if raw vocals are tested.
- **Mitigation**: Post-process NEUTRINO output WAV with the same normalization (0.95 peak) and boundary ADSR envelopes as `generiere_lokale_vocals`.

## Stress Test Results

- **A minor, 160 BPM, LOCAL** → All 6 checks pass → Fails `test_midi_scale_locking` (due to import bug creating F# passing tones) and `test_vocal_pitch_transitions` (16th note octave jumps) → **FAIL**
- **C major, 160 BPM, LOCAL** → All 6 checks pass → Fails `test_midi_scale_locking` (generating F# passing tone) → **FAIL**
- **E minor, 160 BPM, LOCAL** → All 6 checks pass → Fails `test_midi_scale_locking` (generating C# passing tone) → **FAIL**
- **D phrygian, 160 BPM, LOCAL** → All 6 checks pass → Fails `test_midi_scale_locking` (generating Major chord tones outside phrygian) → **FAIL**
- **A minor, 90 BPM, LOCAL** → All 6 checks pass → Fails `test_midi_scale_locking` (passing tones) but pitch transitions pass → **FAIL**
- **A minor, 160 BPM, NEUTRINO** → All 6 checks pass → Fails `test_vocal_clipping` (no ADSR bounds / normalization applied to raw NEUTRINO WAV) and `test_midi_scale_locking` → **FAIL**

## Unchallenged Areas

- **Fluidsynth MIDI rendering** — Did not stress-test soundfont rendering due to CLI tool execution timeout.
