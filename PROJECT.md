# Project: Vocaloid Song Generator Professional J-Pop Quality Upgrade

## Architecture
The Vocaloid/J-Pop MIDI Song Generator is a modular Python-based song generation pipeline. It consists of the following components:
- **Central Settings (`config.py`)**: Key, mode, BPM, song structure, section configuration, and lyrics/vocal properties.
- **Harmonic Composition (`chord_generator.py`)**: Responsible for selecting and voicing chord progressions for different sections of the song.
- **Melody & Phrase Contour System (`melody_generator.py`)**: Generates vocal melodies that follow specific contours based on the section.
- **Rhythmic Beat Engine (`beat_generator.py`)**: Generates MIDI drums.
- **Groove & Ensemble Coordinator (`humanizer.py` & `orchestrator.py`)**: Humanizes notes' start, end, and velocity, and coordinates timing around a shared drum groove.
- **Synthesizer Engine (`synth_generator.py`)**: Produces synthesized lead/pad/pluck parts, including wobble bass, staccato plucks, and wide saw leads, as well as risers.
- **Professional Mixing Desk (`mixer.py`)**: Implements stereo panning, sidechain compression, bass EQ correction, and master channel effects.
- **System Orchestrator (`orchestrator.py`)**: Coordinates the arrangement density, sections, key modulation, transitions, and export to MIDI/audio.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Exploration & Initial Verification | Run initial tests (`test_imports.py`, `test_orchestrator.py`, `test_jpop_verification.py`), check codebase current status, locate components. | None | PLANNED |
| 2 | Vocal Synthesis & Config Overhaul | Replace `generiere_lokale_vocals` with reference code, fix NEUTRINO MusicXMLtoLabel bug, add timeout/fallback, update configuration constants. | M1 | PLANNED |
| 3 | Ensemble Timing & Transitions | Add `humanize_ensemble()` and update orchestrator timing. Implement velocity ramps, riser synth pattern, and transition chords. | M2 | PLANNED |
| 4 | Professional Mixing & Mastering | Fix bass EQ, implement `apply_stereo_pan`, `apply_kick_sidechain`, update master pedalboard, apply JPOP_MIX_LEVELS volume calibration. | M3 | PLANNED |
| 5 | System Integration & Integrity Verification | Verify `main.py` and test suite execution, run Forensic Auditor, and deliver final report. | M4 | PLANNED |

## Interface Contracts
### `vocal_synthesizer.py`
- `generiere_lokale_vocals(melodie_daten, silben, bpm, output_wav_pfad, **kwargs) -> None`
  - Overhaul with the exact reference vocoder + TTS implementation.
- `neutrino_synthese(xml_pfad, output_wav_pfad, neutrino_pfad, model_pfad) -> bool`
  - Ensure MusicXMLtoLabel is in PATH environment, add timeout=120, explicit fallback, proper temp folder cleanup.

### `humanizer.py`
- `humanize_ensemble(tracks: dict, bpm: float, swing: float) -> dict`
  - Coordinates instrument timing around a shared drum groove (Drums lead, Bass/Gtr ±2ms, Piano/Strings ±5ms).
- `humanize_note(note, genre, instrument_type, bpm, swing)`
  - Support "vocal" type with ±2ms jitter and rubato, keeping vocals on the beat.

### `orchestrator.py`
- `apply_velocity_ramp(section_notes: list, ramp_type: str)`
  - Crossfades velocity at section boundaries.
- `get_transition_chord(prev_chord, next_chord, key, mode, start_time) -> list`
  - Generates a short transition note (0.25 duration) for smooth transitions.

### `mixer.py`
- `apply_stereo_pan(audio: np.ndarray, pan: float) -> np.ndarray`
  - Implements panning schema: Drums/Bass/Vocals center (0.0), Piano (-0.25), Guitar (+0.30), Strings (-0.40 / +0.40), Brass (+0.20), Melody (-0.15).
- `apply_kick_sidechain(bass_audio: np.ndarray, drum_audio: np.ndarray, sample_rate: int, threshold: float = 0.3, duck_amount: float = 0.6, release_ms: float = 80.0) -> np.ndarray`
  - Ducks the bass volume in response to kick transients.
- `mische_spuren(spuren: dict, output_wav: str) -> None`
  - Calibrates using `JPOP_MIX_LEVELS`, applies sidechaining/panning/EQ, passes stereo mix through master board.

## Code Layout
The workspace code layout:
- `vocaloid_generator/config.py`
- `vocaloid_generator/vocal_synthesizer.py`
- `vocaloid_generator/humanizer.py`
- `vocaloid_generator/orchestrator.py`
- `vocaloid_generator/synth_generator.py`
- `vocaloid_generator/mixer.py`
- `vocaloid_generator/main.py`
