## 2026-07-06T19:26:33Z

<USER_REQUEST>
You are the Worker for Milestone 2.
Your working directory is: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m2_gen2\
Global Project Plan: c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\PROJECT.md

Task:
1. Implement `setup_neutrino.py` at the project root `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\setup_neutrino.py`.
   - This script must copy Voice-Library files from the source directories inside `めろう（NEUTRINO-Library）-v3.1` (either under `めろう（NEUTRINO-Library）/MERROW` or `speaker/` if it exists) to the destination directory `NEUTRINO-windows-v3.1/NEUTRINO/model/MERROW/`.
   - It should log the files copied and handle directory creation.
2. Update `vocaloid_generator/vocal_synthesizer.py`:
   - Fix the critical bug where `neutrino.exe` is called with incorrect parameters. The 5th positional argument must be the model directory (`model_pfad`), not the WAV output file path.
     - So `subprocess.run` list should be: `[neu_exe, os.path.abspath(full_l), os.path.abspath(tim_l), os.path.abspath(f0_f), os.path.abspath(mel_f), model_pfad, "-n", "4", "-t"]`
   - Ensure the function `neutrino_synthese` checks that the output files `.f0` and `.melspec` are successfully generated.
   - Since `neutrino.exe` won't generate the WAV directly with 5 parameters, make sure that `neutrino_synthese` synthesizes the wav file using the local vocoder logic (`pyworld.synthesize`) on the generated `f0` and `melspec` files, OR verify if `neutrino.exe` writes a wav directly. If it doesn't, use `pyworld` to synthesize the wav file from the f0 and melspec data.
   - Implement robust fallback to `pyttsx3`/local vocals rendering if NEUTRINO is missing or fails (with try-except block).
   - Ensure `MusicXMLtoLabel` bin directory is added to the PATH env.
   - Clean up temporary files properly.
3. Update `vocaloid_generator/config.py`:
   - Apply configuration upgrades:
     - `VOCAL_BREATHINESS = 0.045`
     - `VOCAL_VIBRATO_RATE = 5.2`
     - `VOCAL_VIBRATO_DEPTH = 0.018`
     - `VOCAL_MIX_LEVEL = 0.22`
     - `SWING = 0.12`
     - `BPM = 148`
     - `SONG_STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]`
     - Ensure all sections are defined correctly in `SECTION_CONFIG`.

4. Run the dry-run setup script and basic tests to verify they compile and run.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Handoff:
Write your handoff.md in your working directory and message the orchestrator (conversation ID: 1dff83d9-ecb9-41f7-88bc-abebd5f1ecc5) with a summary when complete.
</USER_REQUEST>
