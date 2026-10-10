## 2026-07-05T20:16:24Z
You are a software engineer subagent (teamwork_preview_worker).
Your working directory is: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\teamwork_preview_worker_m4_1
Your task is to implement the system integration (Milestone 4) and verification (Milestone 5) for our Vocaloid music orchestrator project.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please carry out these implementation and integration steps:

1. Update `vocaloid_generator/orchestrator.py`
   - Modify `orchestrate_song` to collect `gesamte_melodie_daten` and `gesamte_silben` during section iteration.
   - Return them inside the tracks dictionary using keys `"melody_data"` and `"silben"` so that they are easily accessible to `main.py`.

2. Update `vocaloid_generator/mixer.py`
   - Enhance `midi_zu_wav(midi_pfad: str, wav_pfad: str, is_drum: bool = False, instrument_type: str = "piano")`:
     - Load `SOUNDFONT_PFAD` from config.
     - Map `instrument_type` to a General MIDI program (e.g. piano=1, guitar=25 or 29, bass=33 or 39, strings=49, synth=81 or 89, brass=62, drums=0, melody=81).
     - Assign this program to all non-drum instruments in the MIDI object.
     - Try to render using `midi_data.fluidsynth(fs=44100, sf2_path=SOUNDFONT_PFAD)`.
     - Gracefully catch any exception (e.g., if fluidsynth or pyfluidsynth library/dll is not installed) and fall back to the existing `midi_data.synthesize()` sine-wave renderer with Chorus and Reverb Pedalboard effects.
     - Normalize and scale output audio, then save to `wav_pfad`.
   - Enhance `mische_spuren`:
     - Apply specific Pedalboard effects (HighpassFilter, PeakFilter, Compressor, Reverb) per track depending on the file name (e.g. `drums.wav`, `bass.wav`, `piano.wav`, `guitar.wav`, `strings.wav`, `synth.wav`, `brass.wav`, `vocals.wav`).
     - Sum the signals safely with proper mixing gains.
     - Apply a mastering chain to the final mix: HighpassFilter(30Hz), Compressor, Gain, Limiter(-0.5dB).

3. Update `vocaloid_generator/main.py`
   - Rewrite the main execution block:
     * Read `STYLE` (genre), `BPM`, `SONG_STRUCTURE`, `KEY`, `MODE`, and `SECTION_CONFIG` from config.
     * Call `orchestrate_song` with these parameters to generate all MIDI tracks and retrieve `melody_data` and `silben`.
     * Extract `melody_data` and `silben` for vocal synthesis, run `erstelle_musicxml` and the vocal engine (NEUTRINO or LOCAL) to generate `vocals.wav`.
     * Render each generated instrument MIDI track (`drums.mid`, `piano.mid`, `bass.mid`, `guitar.mid`, `strings.mid`, `synth.mid`, `brass.mid`, `melody.mid`) to WAV using `mixer.midi_zu_wav(..., instrument_type=...)`.
     * Call `mische_spuren` passing all generated track WAV paths and `vocals.wav` to create `final_mix.wav`.
     * Export the final mix to MP3 using `exportiere_song`.

4. Verification and Testing
   - Run the import test script `python vocaloid_generator/test_imports.py` and ensure it runs successfully.
   - Create a test script `vocaloid_generator/test_orchestrator.py` that:
     * Programmatically runs the orchestrator to generate tracks for at least three different genres (e.g., Rock, EDM, Lo-Fi).
     * Loads the resulting MIDI files using `pretty_midi`.
     * Proves/asserts that each genre has a different and genre-appropriate set of instruments (e.g., Rock has guitar and bass but no synth, EDM has synth and bass but no acoustic guitar/brass, Lo-Fi has piano and strings, etc.).
     * Proves/asserts that the MIDI notes in the tracks have non-uniform velocities and start times (demonstrating humanization/micro-timing offsets).
     * Proves/asserts that the timing and velocity variances differ significantly between genres.
     * Runs the modified `main.py` to confirm it generates a full song without errors.
   - Run `python vocaloid_generator/test_orchestrator.py` to execute these E2E tests and verify all acceptance criteria.

Report all file paths, changes made, and test run command outputs. Send a message to the caller (conversation ID: 97b77c60-3e38-4c15-a253-16d643450ae4) when done.
