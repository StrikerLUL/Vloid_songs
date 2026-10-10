## 2026-07-06T09:10:26Z
You are a teamwork_preview_worker. Your working directory is c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m1_2\.
Your task is to update `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\vocaloid_generator\test_jpop_verification.py` to implement the 6 new programmatic verification tests designed in `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\explorer_m1_1\handoff.md`:

1. Phrase Contour: For the Chorus section melody, assert that the pitch-peak note occurs at index >= len(phrase)//2, and the final note pitch < first note pitch (arch contour verified).
2. No Duplicate Progressions: Generate a full song; assert that no two adjacent sections share the exact same list of root notes.
3. Velocity Arc: Assert that mean_velocity(Intro) < mean_velocity(Verse) < mean_velocity(Chorus) across all instrument tracks.
4. Drop Section Silence: Assert that in the "Drop" section, the only MIDI notes present are on kick and bass channels; all other tracks have zero notes.
5. Final Chorus Pitch Shift: Assert that the mean pitch of notes in Chorus_Final is at least 1 semitone higher than in Chorus_2 (modulation effect).
6. Lyric Continuity: Assert that SONG_TEXT_VERSE contains no space-separated single-kana sequences (i.e., no match for regex [ぁ-ん] [ぁ-ん]).

You should only modify `test_jpop_verification.py`. Do NOT implement the core J-Pop generator features yet. Integrate these 6 new tests into the standalone runner `run_all_tests()`.
After implementing, execute the test suite (e.g. `python test_jpop_verification.py`) and confirm that it fails on the unimplemented features. Capture the failure logs.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your handoff report to `c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m1_2\handoff.md`. When done, report back to the Project Orchestrator at conversation ID af64d191-fd94-45f1-9af8-43013a371330.
