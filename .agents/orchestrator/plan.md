# Plan: J-Pop Production Refinement & Professional Mixing Overhaul

## Architecture
- **Vocal Synthesizer (`vocal_synthesizer.py`)**: Replace local vocal generation with the provided reference vocoder + TTS logic. Improve NEUTRINO path and execution handling (MusicXMLtoLabel in PATH, 120s timeout, fallback, temp files).
- **Groove Coordinator (`humanizer.py` & `orchestrator.py`)**: Implement ensemble-wide timing coordination (`humanize_ensemble`) anchored on the drum groove. Vocals get a specific timing treatment (jitter and rubato) keeping them on beat.
- **Transitions and Structure (`orchestrator.py` & `synth_generator.py`)**: Add velocity ramps for smooth transitions, a riser synthesizer pattern for build-ups, and transition chords (short 0.25-quarter-note fillers).
- **Mixing Desk (`mixer.py`)**: Implement J-Pop stereo panning, kick sidechain compression on the bass track, bass EQ corrections, and the updated Master Board chain. Calibrate volumes using `JPOP_MIX_LEVELS`.
- **System Configuration (`config.py`)**: Apply target parameters (BPM 148, Swing 0.12, updated song structure, and vocal parameters).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Initial Verification | Explore existing implementation, identify locations of targets, verify initial test execution state. | None | PLANNED |
| 2 | Vocal Synthesis & Config Overhaul | Implement the reference `generiere_lokale_vocals` and fix NEUTRINO bugs in `vocal_synthesizer.py`. Update `config.py` parameters. | M1 | PLANNED |
| 3 | Ensemble Timing & Transitions | Implement `humanize_ensemble` in `humanizer.py` / `orchestrator.py`. Add velocity ramps, riser synth, and transition chords. | M2 | PLANNED |
| 4 | Professional Mixing & Mastering | Fix bass EQ, implement stereo panning, kick-bass sidechain, master pedalboard, and mix level calibration in `mixer.py`. | M3 | PLANNED |
| 5 | System Integration & Integrity Verification | Verify `main.py` execution, run the existing and any new tests, perform Forensic Auditor integrity check. | M4 | PLANNED |
