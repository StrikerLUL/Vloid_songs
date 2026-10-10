# test_orchestrator.py - End-to-End Validation Script
import os
import sys
import subprocess
import numpy as np
import pretty_midi

# Ensure the module can import local files
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator import orchestrate_song
from config import OUTPUT_ORDNER

def test_genres_orchestration():
    print("=== TESTING GENRE ORCHESTRATION AND INSTRUMENT MAPS ===")
    
    # 1. Generate and test Rock
    print("\n--- Generating Rock Song ---")
    rock_tracks = orchestrate_song(
        genre="Rock",
        bpm=120,
        structure=["Intro", "Verse", "Chorus", "Outro"],
        key="A",
        mode="minor",
        section_config={
            "Intro": {"bars": 2, "has_vocals": False},
            "Verse": {"bars": 4, "has_vocals": True},
            "Chorus": {"bars": 4, "has_vocals": True},
            "Outro": {"bars": 2, "has_vocals": False}
        }
    )
    
    # Proves/asserts that Rock has guitar and bass but no synth, strings or brass
    assert len(rock_tracks["guitar"]) > 0, "Rock must have guitar notes"
    assert len(rock_tracks["bass"]) > 0, "Rock must have bass notes"
    assert len(rock_tracks["synth"]) == 0, "Rock must not have synth notes"
    assert len(rock_tracks["strings"]) == 0, "Rock must not have strings notes"
    assert len(rock_tracks["brass"]) == 0, "Rock must not have brass notes"
    print("[PASS] Rock instrument constraints verified successfully.")

    # 2. Generate and test EDM
    print("\n--- Generating EDM Song ---")
    edm_tracks = orchestrate_song(
        genre="EDM",
        bpm=128,
        structure=["Intro", "Verse", "Chorus", "Outro"],
        key="C",
        mode="major",
        section_config={
            "Intro": {"bars": 2, "has_vocals": False},
            "Verse": {"bars": 4, "has_vocals": True},
            "Chorus": {"bars": 4, "has_vocals": True},
            "Outro": {"bars": 2, "has_vocals": False}
        }
    )
    
    # Proves/asserts that EDM has synth and bass but no guitar, strings or brass
    assert len(edm_tracks["synth"]) > 0, "EDM must have synth notes"
    assert len(edm_tracks["bass"]) > 0, "EDM must have bass notes"
    assert len(edm_tracks["guitar"]) == 0, "EDM must not have guitar notes"
    assert len(edm_tracks["strings"]) == 0, "EDM must not have strings notes"
    assert len(edm_tracks["brass"]) == 0, "EDM must not have brass notes"
    print("[PASS] EDM instrument constraints verified successfully.")

    # 3. Generate and test Lo-Fi
    print("\n--- Generating Lo-Fi Song ---")
    lofi_tracks = orchestrate_song(
        genre="Lo-Fi",
        bpm=75,
        structure=["Intro", "Verse", "Chorus", "Outro"],
        key="F",
        mode="major",
        section_config={
            "Intro": {"bars": 2, "has_vocals": False},
            "Verse": {"bars": 4, "has_vocals": True},
            "Chorus": {"bars": 4, "has_vocals": True},
            "Outro": {"bars": 2, "has_vocals": False}
        }
    )
    
    # Proves/asserts that Lo-Fi has piano and strings
    assert len(lofi_tracks["piano"]) > 0, "Lo-Fi must have piano notes"
    assert len(lofi_tracks["strings"]) > 0, "Lo-Fi must have strings notes"
    print("[PASS] Lo-Fi instrument constraints verified successfully.")

    print("\n=== TESTING HUMANIZATION (VELOCITIES & TIMING) ===")
    
    # Prove non-uniform velocities and start times
    for genre, tracks in [("Rock", rock_tracks), ("EDM", edm_tracks), ("Lo-Fi", lofi_tracks)]:
        # Let's inspect bass track notes since it is present in all genres
        bass_notes = tracks["bass"]
        assert len(bass_notes) > 0, f"{genre} bass notes should not be empty"
        
        # Extract velocities and start times
        velocities = [n.velocity for n in bass_notes]
        start_times = [n.start for n in bass_notes]
        
        # Verify non-uniform velocities
        unique_vels = set(velocities)
        print(f"[{genre}] Bass note velocities: {velocities[:8]}... Unique velocities count: {len(unique_vels)}")
        assert len(unique_vels) > 1, f"Velocities in {genre} must be non-uniform due to humanization"
        
        # Verify non-uniform start times (micro-timing offsets)
        print(f"[{genre}] Bass note start times: {start_times[:8]}...")
        assert len(set(start_times)) > 1, f"Start times in {genre} must be non-uniform"
        
    print("[PASS] Non-uniform velocities and start times verified for all genres.")

    print("\n=== TESTING VELOCITY & TIMING VARIANCE DIFFERENCES BETWEEN GENRES ===")
    
    # Calculate velocity variance for bass track in Rock, EDM, and Lo-Fi
    rock_vel_var = np.var([n.velocity for n in rock_tracks["bass"]])
    edm_vel_var = np.var([n.velocity for n in edm_tracks["bass"]])
    lofi_vel_var = np.var([n.velocity for n in lofi_tracks["bass"]])
    
    print(f"Velocity Variance - EDM: {edm_vel_var:.2f}, Rock: {rock_vel_var:.2f}, Lo-Fi: {lofi_vel_var:.2f}")
    
    # Assert that variance differs significantly: EDM < Rock < Lo-Fi
    assert edm_vel_var < rock_vel_var, "EDM velocity variance should be smaller than Rock"
    assert rock_vel_var < lofi_vel_var, "Rock velocity variance should be smaller than Lo-Fi"
    print("[PASS] Velocity variance differences verified successfully (EDM < Rock < Lo-Fi).")
    
    # Calculate micro-timing (jitter) variance relative to 16th note grid (0.25 beat)
    def calc_grid_jitter_variance(notes, bpm):
        beat_dur = 60.0 / bpm
        grid = 0.25 * beat_dur
        jitters = []
        for n in notes:
            rem = n.start % grid
            if rem > grid / 2:
                rem -= grid
            jitters.append(rem)
        return np.var(jitters)
        
    rock_timing_var = calc_grid_jitter_variance(rock_tracks["bass"], 120)
    edm_timing_var = calc_grid_jitter_variance(edm_tracks["bass"], 128)
    lofi_timing_var = calc_grid_jitter_variance(lofi_tracks["bass"], 75)
    
    print(f"Timing Jitter Variance - EDM: {edm_timing_var:.6f}, Rock: {rock_timing_var:.6f}, Lo-Fi: {lofi_timing_var:.6f}")
    
    # EDM has 0 jitter. Rock has +/-10ms. Lo-Fi has -15ms to +25ms + swing delay.
    assert edm_timing_var < rock_timing_var, "EDM timing variance should be smaller than Rock"
    assert rock_timing_var < lofi_timing_var, "Rock timing variance should be smaller than Lo-Fi"
    print("[PASS] Timing jitter variance differences verified successfully (EDM < Rock < Lo-Fi).")

    # 4. Verify saved MIDI files on disk
    print("\n--- Verifying MIDI Files on Disk for last run (Lo-Fi) ---")
    piano_midi_path = os.path.join(OUTPUT_ORDNER, "piano.mid")
    assert os.path.exists(piano_midi_path), "piano.mid must exist on disk"
    pm = pretty_midi.PrettyMIDI(piano_midi_path)
    assert len(pm.instruments) == 1, "piano.mid should contain 1 instrument"
    assert len(pm.instruments[0].notes) > 0, "piano.mid instrument should have notes"
    print("[PASS] MIDI file verification on disk successful.")


def test_main_execution():
    print("\n=== RUNNING MAIN.PY END-TO-END SONG GENERATION ===")
    
    main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    try:
        # Run main.py using the same python interpreter
        result = subprocess.run(
            [sys.executable, main_py_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("[SUCCESS] main.py completed execution successfully.")
        print("Output logs:")
        print(result.stdout)
        
        # Verify final outputs exist
        final_wav = os.path.join(OUTPUT_ORDNER, "final_mix.wav")
        final_mp3 = os.path.join(OUTPUT_ORDNER, "final_song.mp3")
        assert os.path.exists(final_wav), f"final_mix.wav must exist at {final_wav}"
        assert os.path.exists(final_mp3), f"final_song.mp3 must exist at {final_mp3}"
        print(f"[PASS] Output files created successfully:")
        print(f"  - WAV: {final_wav} (size: {os.path.getsize(final_wav)} bytes)")
        print(f"  - MP3: {final_mp3} (size: {os.path.getsize(final_mp3)} bytes)")
        
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] main.py failed with return code {e.returncode}")
        print("Error stdout:")
        print(e.stdout)
        print("Error stderr:")
        print(e.stderr)
        raise e

def test_dynamic_arrangements_and_modulation():
    print("\n=== Testing Dynamic Arrangement & Modulation (R3 & R4) ===")
    from config import SECTION_CONFIG, KEY, MODE
    from orchestrator import orchestrate_song
    
    # Define a test structure that includes the Drop section for this test
    test_structure = ["Intro", "Verse", "PreChorus", "Chorus", "Drop", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]
    
    # Run the generator with the test structure
    tracks = orchestrate_song(
        genre="J-Pop",
        bpm=160,
        structure=test_structure,
        key=KEY,
        mode=MODE,
        section_config=SECTION_CONFIG
    )
    
    # Calculate times dynamically from structure
    def get_section_times(structure, section_config, bpm):
        viertel_dauer = 60.0 / bpm
        bar_duration = 4 * viertel_dauer
        times = []
        current_time = 0.0
        for section_type in structure:
            bars = section_config.get(section_type, {}).get("bars", 4)
            times.append({
                "type": section_type,
                "start": current_time,
                "end": current_time + bars * bar_duration
            })
            current_time += bars * bar_duration
        return times

    times = get_section_times(test_structure, SECTION_CONFIG, 160)
    
    # 1. Verify Drop Section contains only kick + bass
    drop_sections = [t for t in times if t["type"] == "Drop"]
    assert len(drop_sections) > 0, "Drop section must be present in the test structure"
    drop_sec = drop_sections[0]
    drop_start = drop_sec["start"]
    drop_end = drop_sec["end"]
    print(f"Drop section times: {drop_start:.2f}s to {drop_end:.2f}s")
    
    # Verify no piano, guitar, strings, synth, brass, or melody notes start inside the Drop section
    for track_name in ["piano", "guitar", "strings", "synth", "brass", "melody"]:
        notes_in_drop = [n for n in tracks[track_name] if drop_start <= n.start < drop_end]
        assert len(notes_in_drop) == 0, f"Track {track_name} should be silent during Drop section"
        
    # Verify only Kick is generated for drums in the Drop section
    drop_drums = [n for n in tracks["drums"] if drop_start <= n.start < drop_end]
    for note in drop_drums:
        assert note.pitch == 36, f"Only Kick drum (MIDI 36) allowed in the Drop section, found pitch {note.pitch}"
        
    # 2. Verify Final Chorus Key Modulation (+1 semitone)
    chorus_sections = [t for t in times if t["type"] == "Chorus"]
    assert len(chorus_sections) >= 2, "There must be at least two Chorus sections"
    c2_sec = chorus_sections[1] # second Chorus
    cf_sec = chorus_sections[-1] # final Chorus
    c2_start, c2_end = c2_sec["start"], c2_sec["end"]
    cf_start, cf_end = cf_sec["start"], cf_sec["end"]
    print(f"Second Chorus times: {c2_start:.2f}s to {c2_end:.2f}s")
    print(f"Final Chorus times: {cf_start:.2f}s to {cf_end:.2f}s")
    
    c2_notes = [n.pitch for n in tracks["bass"] if c2_start <= n.start < c2_end]
    cf_notes = [n.pitch for n in tracks["bass"] if cf_start <= n.start < cf_end]
    
    # Since chords modulate up, the average pitch class should shift by 1
    c2_avg = sum(c2_notes) / len(c2_notes) if c2_notes else 0
    cf_avg = sum(cf_notes) / len(cf_notes) if cf_notes else 0
    print(f"Second Chorus Bass Avg Pitch: {c2_avg:.2f}, Final Chorus Bass Avg Pitch: {cf_avg:.2f}")
    assert abs(cf_avg - c2_avg - 1.0) < 0.5, "Final Chorus must be modulated by +1 semitone relative to the second Chorus"
    
    # 3. Verify Final Chorus Velocity Boost (+12)
    # Compare average velocity of bass notes in the second Chorus vs final Chorus
    c2_vels = [n.velocity for n in tracks["bass"] if c2_start <= n.start < c2_end]
    cf_vels = [n.velocity for n in tracks["bass"] if cf_start <= n.start < cf_end]
    c2_avg_vel = sum(c2_vels) / len(c2_vels) if c2_vels else 0
    cf_avg_vel = sum(cf_vels) / len(cf_vels) if cf_vels else 0
    print(f"Second Chorus Bass Avg Velocity: {c2_avg_vel:.2f}, Final Chorus Bass Avg Velocity: {cf_avg_vel:.2f}")
    assert cf_avg_vel > c2_avg_vel + 10.0, "Final Chorus notes must have a ~12 velocity boost"
    
    # 4. Verify Snare Ghost Note Velocity Range (20-40)
    snares = [n for n in tracks["drums"] if n.pitch == 40]  # 40 is SNARE_GHOST
    for note in snares:
        assert 20 <= note.velocity <= 40, f"Ghost snare velocity {note.velocity} is outside [20, 40] range"
        
    print("[PASS] R3 and R4 dynamic and modulation tests passed successfully!")

if __name__ == "__main__":
    test_dynamic_arrangements_and_modulation()
    test_genres_orchestration()
    test_main_execution()
    print("\n=== ALL E2E VERIFICATION TESTS PASSED SUCCESSFULLY ===")
