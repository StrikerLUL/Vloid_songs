## 2026-07-06T19:35:50Z

You are the Worker for Milestone 5.
Your working directory is: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m5_gen2\
Global Project Plan: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\PROJECT.md

Task:
1. Implement a clean, professional, tab-based layout with exactly 5 tabs in `vocaloid_generator/view/main_view.py` and `vocaloid_generator/view/tabs.py`:
   - **Song Tab**: Key, mode, BPM inputs, song structure reordering (e.g., list of active sections with up/down buttons to reorder, or simple block drag-drop reordering), a preview player (with play/stop buttons using Python's built-in `winsound` on Windows to play `output/final_mix.wav` asynchronously), and a progress bar (and status indicator).
   - **Lyrics Tab**: Section-by-section lyrics editor (with dropdown or tabs to select Verse, Chorus, PreChorus, Bridge, and an edit box) and a syllable count/preview label.
   - **Instrumente Tab**: Per-instrument configuration for each of the 8 instruments: Piano, Bass, Guitar, Strings, Synth, Brass, Drums, Melody. Provide a volume slider (0.0 to 1.0), style/pattern selector dropdown, enabled/disabled checkbox.
   - **Mixer Tab**: Visual faders for each of the 8 instruments + Vocals + Master fader. Panning sliders (-1.0 to 1.0) for each channel. Solo/mute buttons. Master compressor settings (threshold, ratio sliders) and limiter threshold slider.
   - **Settings Tab**: Inputs to configure `NEUTRINO_PFAD`, `SOUNDFONT_PFAD`, `OUTPUT_ORDNER` (with file browser buttons), and Humanizer settings (swing slider, jitter slider, etc.).

2. Create `vocaloid_generator/preset_manager.py`:
   - Define presets/profiles (e.g. "J-Pop Energy", "Kawaii Chiptune", "Ballade", "Rock", "City Pop", "Dark Vocaloid") that configure BPM, Key, Mode, structure, and instrument settings (volumes, panning, active tracks). Clicking a preset in the GUI should apply these settings to the Model, updating all Views.

3. Refactor `vocaloid_generator/model.py`:
   - Extend the model class to store all GUI-related parameters (instrument volumes, panning, mute/solo states, paths, humanizer parameters, master effects settings).
   - Ensure the Observer pattern notifies all registered views on property changes.
   - Implement JSON load/save methods (`load_settings` / `save_settings`) to persist settings to `vocaloid_generator/settings.json`.

4. Refactor `vocaloid_generator/controller.py`:
   - Bind all new inputs from the 5 tabs to the Model.
   - Decouple the background generation thread: instead of using dummy sleep mocks, run the ACTUAL generation pipeline in a background thread by calling `main.py`'s generation logic (or directly calling `orchestrate_song`, `neutrino_synthese`, `soundfont_renderer.render_midi_to_wav` / `midi_zu_wav`, and `mische_spuren` in sequence).
   - Ensure progress updates (status, progress value, logs) are successfully pushed to the thread queue and read by `poll_queue` to update the GUI.

5. Refactor `vocaloid_generator/test_gui.py`:
   - Update `test_view_contains_four_tabs` to `test_view_contains_five_tabs`, asserting that all 5 new tabs (Song, Lyrics, Instrumente, Mixer, Settings) exist and are instantiated correctly.
   - Ensure other GUI/MVC tests continue to pass.

6. Ensure all UI elements run in dark-mode and are responsive.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Handoff:
Write your handoff.md in your working directory and message the orchestrator (conversation ID: 1dff83d9-ecb9-41f7-88bc-abebd5f1ecc5) with a summary when complete.
