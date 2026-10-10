# Handoff Report

## 1. Observation

- **Duplicate Config Module Import Resolution**:
  In `vocaloid_generator/test_jpop_verification.py` (lines 10-11):
  ```python
  sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
  sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "vocaloid_generator"))
  ```
  This adds both the root and `vocaloid_generator` directory to `sys.path`.
  The test script imports the config module as `vocaloid_generator.config` (lines 13-15):
  ```python
  from vocaloid_generator.config import (
      KEY, MODE, STYLE, SONG_STRUCTURE, SECTION_CONFIG, OUTPUT_ORDNER, BPM
  )
  ```
  And updates the configuration using (lines 321-322):
  ```python
      import vocaloid_generator.config as config
      config.STRICT_SCALE_LOCKING = True
  ```
  However, `vocaloid_generator/orchestrator.py` imports `config` directly (lines 203-204):
  ```python
      import config
      scale_locked = getattr(config, "STRICT_SCALE_LOCKING", False)
  ```
  Since they are loaded under different namespaces, they exist as two separate module objects in `sys.modules`. Thus, modifying `vocaloid_generator.config.STRICT_SCALE_LOCKING = True` leaves `config.STRICT_SCALE_LOCKING = False` inside the orchestrator and instrument generators.

- **Bass Chromatic Passing Tone Generation**:
  In `vocaloid_generator/bass_generator.py` (lines 46-53):
  ```python
          has_passing_tone = False if getattr(config, "STRICT_SCALE_LOCKING", False) else (abs(diff) in (2, 3))
          passing_pitch = None
          if has_passing_tone:
              # Shift towards the target
              step = 1 if diff > 0 else -1
              passing_pitch = get_bass_pitch(root_name, octave=1) + step
  ```
  Under default key `A minor` (Chorus progression VI -> VII -> v -> i, i.e., F -> G -> Em -> Am), the transition F (root 5) to G (root 7) has a difference of 2.
  If `STRICT_SCALE_LOCKING` is `False`, `has_passing_tone` is `True`, and the passing pitch is `F + 1 = F#` (pitch class 6). F# is not in the A minor scale.
  For C major (transition F -> G), the passing pitch is also `F#`, which is not in C major.
  For E minor (transition C -> D), the passing pitch is `C#`, which is not in E minor.

- **Legato Pitch Transitions on Short Notes**:
  In `vocaloid_generator/vocal_synthesizer.py` (lines 183-190):
  ```python
              # --- Legato / Portamento Glide ---
              if prev_pitch_hz is not None:
                  glide_len = min(16, len(f0_vocoded) // 2)
                  if glide_len > 0:
                      for j in range(glide_len):
                          if f0_vocoded[j] > 0:
                              alpha = j / glide_len
                              f0_vocoded[j] = prev_pitch_hz * (1.0 - alpha) + target_hz * alpha
  ```
  At 160 BPM, a 16th note (0.25 beats) has duration 0.09375s. At 5ms frame rate, this yields ~18 frames, setting `glide_len` to 9 frames.
  For an octave transition in Chorus (A4 [440 Hz] to D5 [587.33 Hz]), the step size is `147.33 / 9 = 16.37 Hz`.
  This triggers an assertion failure in `test_jpop_verification.py` (lines 145-148):
  ```python
              # We assert that no frame-to-frame voiced pitch jump exceeds 15.0 Hz (~1.5 semitones/5ms).
              if hz_diff >= 15.0:
                  sharp_jumps += 1
  ```

- **Chord Generator Fallback for Modal Scales**:
  In `vocaloid_generator/chord_generator.py` (lines 108-130):
  If `mode` is `"phrygian"`, `mode == "minor"` is `False`. The generator defaults to Major mode transitions:
  ```python
              else:
                  transitions = cls.TRANSITIONS_MAJOR
  ```
  For E phrygian, this generates chords like A maj7 (A, C#, E, G#) and B 7 (B, D#, F#, A), which contain notes (C#, G#, D#, F#) completely outside the E phrygian scale (E, F, G, A, B, C, D).

- **Raw NEUTRINO Output Normalization**:
  In `vocaloid_generator/vocal_synthesizer.py` (lines 337-380):
  The NEUTRINO engine wrapper `neutrino_synthese` moves raw `tmp_w` directly to output without peak normalization or ADSR fade-ins/outs.

- **GUI Dummy Generation Task**:
  In `vocaloid_generator/controller.py` (lines 204-228):
  The GUI generation method `_run_generation_task` sleep-simulates progress steps and does not invoke `main.py` or the orchestrator engine.

## 2. Logic Chain

1. Due to the duplicate module import bug (Observation 1), the orchestrator and generators use `config.STRICT_SCALE_LOCKING = False` during test runs.
2. Since `STRICT_SCALE_LOCKING` is `False`, the bass generator creates chromatic passing tones (Observation 2). Under A minor, C major, and E minor keys, these passing tones are out-of-scale (e.g. F# in A minor/C major, C# in E minor).
3. Since these out-of-scale notes are not corrected, `test_midi_scale_locking` fails with a scale-locking violation.
4. If the mode is set to a modal scale like phrygian or dorian (Observation 4), the chord generator defaults to Major transitions. This introduces multiple out-of-scale notes (e.g., C#, G# in E phrygian), which are not corrected (since scale locking is False), causing the test to fail.
5. In addition, the F0 legato interpolation on short 16th notes with octave hooks (Observation 3) results in frame-to-frame frequency steps of ~16.37 Hz, which exceeds the 15.0 Hz voiced pitch jump threshold, failing `test_vocal_pitch_transitions` under default J-Pop configurations.
6. Finally, if the NEUTRINO vocal engine is selected (Observation 5), raw WAV files are output without normalization or ADSR boundaries, failing `test_vocal_clipping` when verified.

## 3. Caveats

- CLI commands timed out on permission prompts in this automated subagent context. Thus, all findings are established using rigorous static analysis and tracing.
- The `test_stress.py` script was written to the workspace to allow manual or automated execution by the user to dump these logs under multiple configurations.

## 4. Conclusion

The J-Pop orchestration system fails the verification suite and boundary stress testing under all conditions due to three primary bugs:
1. **[CRITICAL] Duplicate Config Module Namespace Import Bug**: Prevents strict scale locking from being enabled during tests.
2. **[HIGH] Legato Pitch Step Overflow**: Legato glide steps on short notes with octave jumps exceed the 15.0 Hz delta limit.
3. **[HIGH] Chord Generator Fallback for Modal Scales**: Modal scales (phrygian, dorian) fall back to Major transitions, causing major out-of-scale violations.

The system is in a **FAILING** state and requires fixes before it can pass the E2E verification suite.

## 5. Verification Method

To verify these findings, run the following commands in the workspace root:

1. To run the default verification suite (fails due to scale locking & pitch legato):
   ```powershell
   python vocaloid_generator/test_jpop_verification.py
   ```
2. To run the automated stress testing script containing the config import fix and verifying all boundary cases:
   ```powershell
   python vocaloid_generator/test_stress.py
   ```
   Inspect the generated log file:
   `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\teamwork_preview_challenger_m2_1\stress_test_log.txt`
