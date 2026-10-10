# Implementation Request - Professional J-Pop Quality Refactoring

Please implement the following refactoring in the `vocaloid_generator/` directory.

## R1. Overhaul Vocal Synthesis (`vocal_synthesizer.py`)
1. Replace `generiere_lokale_vocals` with the exact target logic provided in the ORIGINAL_REQUEST.md.
2. Update `neutrino_synthese`:
   - Prepend `bin_pfad = os.path.abspath(os.path.join(neutrino_pfad, "bin"))` to `os.environ["PATH"]` to ensure `MusicXMLtoLabel.exe` and `neutrino.exe` are in PATH.
   - Use a temporary directory via `tempfile.TemporaryDirectory()` to create and hold all intermediate/temporary files (`.lab`, `.f0`, `.melspec`, etc.), ensuring proper cleanup.
   - Add `timeout=120` to all `subprocess.run` calls.
   - Ensure it raises an exception if subprocess returns non-zero exit code or fails to generate the output file, so the caller's try-except block falls back to local synthesis.

## R2. Coordinate Ensemble Timing (`humanizer.py` & `orchestrator.py`)
1. In `humanizer.py`, implement `humanize_ensemble(tracks: dict, genre: str, bpm: float, swing: float = None) -> dict`:
   - Humanize "drums" track first via `humanize_notes`.
   - Collect start times of all drum notes.
   - For other tracks (specifically "piano", "bass", "guitar", "strings", and "brass"), if drum notes exist:
     - Apply pocket shifting, swing, jitter, etc. via `humanize_notes` first.
     - For each note, find the closest drum note start time. If the difference is < 100ms, align the note start time to the drum note start time with an added random jitter:
       - Bass/Guitar: ±2ms (`random.uniform(-0.002, 0.002)`)
       - Piano/Strings/Brass: ±5ms (`random.uniform(-0.005, 0.005)`)
2. In `humanizer.py`, update `humanize_note`:
   - Add support for `"vocal"` or `"melody"` instrument type with ±2ms jitter and no pocket shifts.
3. In `humanizer.py`, update `humanize_notes`:
   - Support `"vocal"` or `"melody"` instrument type by grouping notes into phrases (silent gaps >= 150ms), and applying a phrase rubato (±5-15ms for vocal, ±10-30ms for melody) and sine-curve velocity shaping.
4. In `orchestrator.py`, replace the independent calls to `humanize_notes` at the end of `orchestrate_song` with a single call to `humanize_ensemble` (passing `tracks`, `genre`, `bpm`, and `swing=SWING`).

## R3. Improve Song Structure and Transitions (`orchestrator.py` & `synth_generator.py`)
1. In `orchestrator.py`, implement `apply_velocity_ramp(notes: list, ramp_type: str, start_time: float, duration: float)`:
   - "fade_in": ramp velocities up from 50% to 100% over the first 2 seconds of the section (or half the section, whichever is smaller).
   - "fade_out": ramp velocities down from 100% to 50% over the last 2 seconds of the section.
   - Apply this to all generated instrument tracks (except vocals/melody and drums) at every section boundary in the song timeline (fade-out at current section end, fade-in at next section start).
2. In `synth_generator.py`, ensure the "riser" synth pattern is fully supported and is being used correctly in `orchestrator.py`.
3. In `orchestrator.py`, implement `get_transition_chord(prev_chord, next_chord, key, mode, start_time) -> list`:
   - Generate a short transition note (length of 0.25 quarter note) just before the `start_time` of the next chord, using the root pitch of the next chord in octave 3 or 4. Return it as a list containing a `pretty_midi.Note`.
   - Call `get_transition_chord` at chord transition boundaries (or section boundaries) to add transition notes to the bass, piano, or guitar tracks.

## R4. Professional Mix & Master (`mixer.py`)
1. Implement the corrected Bass EQ in `mische_spuren` (remove sub-rumble below 28Hz, LowShelfFilter at 80Hz +2.0dB, Compressor threshold -16.0dB ratio 3.5, PeakFilter at 180Hz +3.0dB Q 1.5). Import `LowShelfFilter` and `PeakFilter` from pedalboard.
2. Implement `apply_stereo_pan(audio: np.ndarray, pan: float) -> np.ndarray` according to the target logic.
3. Apply the J-Pop panning schema in `mische_spuren`:
   - Drums/Bass/Vocals: Center (0.0)
   - Piano: -0.25
   - Guitar: +0.30
   - Strings: split-pan left -0.40 and right +0.40
   - Synth: Haas effect (no additional panning)
   - Brass: +0.20
   - Melody: -0.15
4. Implement sidechain compression `apply_kick_sidechain(bass_audio: np.ndarray, drum_audio: np.ndarray, sample_rate: int, threshold: float = 0.3, duck_amount: float = 0.6, release_ms: float = 80.0) -> np.ndarray` according to the target logic. Apply this sidechaining to duck the bass track to the drum track in `mische_spuren`.
5. Update the master pedalboard chain in `mische_spuren` with the exact master board effects provided in the ORIGINAL_REQUEST.md.
6. Implement `JPOP_MIX_LEVELS` volume calibration (override or multiply the gains of the tracks using `JPOP_MIX_LEVELS` dictionary).

## R5. Configuration Updates (`config.py`)
Update:
- `VOCAL_BREATHINESS` to 0.045
- `VOCAL_VIBRATO_RATE` to 5.2
- `VOCAL_VIBRATO_DEPTH` to 0.018
- `VOCAL_MIX_LEVEL` to 0.22
- `SWING` to 0.12
- `BPM` to 148
- `SONG_STRUCTURE` to `["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]`

Verify all changes compile and run correctly.
