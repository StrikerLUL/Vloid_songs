# proposed_test_jpop_verification.py - Programmatic Verification Test Script for J-Pop Generator
import os
import sys
import numpy as np
import pretty_midi
import soundfile as sf
import pyworld as pw

# Ensure we can import the vocaloid_generator modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "vocaloid_generator"))

from config import (
    KEY, MODE, STYLE, SONG_STRUCTURE, SECTION_CONFIG, OUTPUT_ORDNER, BPM
)
from orchestrator import orchestrate_song, PATTERN_MAP
from mixer import midi_zu_wav
from vocal_synthesizer import generiere_lokale_vocals

# ── 1. VST Error Handling / Typecheck Test ───────────────────────────────────
def test_vst_error_handling():
    """
    Verifies that midi_zu_wav executes without TypeError when vst_pfad is
    invalid (non-existent path), missing (None), or invalid type (integer),
    logging a warning instead of crashing.
    """
    print("\n--- Running VST Error Handling / Typecheck Test ---")
    test_mid = "temp_test_vst.mid"
    test_wav = "temp_test_vst.wav"
    
    # Create a tiny test MIDI file with a single note
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
    pm.instruments.append(inst)
    pm.write(test_mid)
    
    try:
        # Case A: vst_pfad is missing (None)
        print("Testing with vst_pfad=None...")
        midi_zu_wav(test_mid, test_wav, is_drum=False, instrument_type="piano", vst_pfad=None)
        assert os.path.exists(test_wav), "WAV must be generated when vst_pfad is None"
        os.remove(test_wav)
        
        # Case B: vst_pfad is invalid (non-existent path string)
        print("Testing with invalid vst_pfad string...")
        midi_zu_wav(test_mid, test_wav, is_drum=False, instrument_type="piano", vst_pfad="nonexistent_vst_path.vst3")
        assert os.path.exists(test_wav), "WAV must be generated when vst_pfad is invalid string"
        os.remove(test_wav)
        
        # Case C: vst_pfad is invalid type (integer) - Typecheck validation
        print("Testing with invalid vst_pfad type (int)...")
        midi_zu_wav(test_mid, test_wav, is_drum=False, instrument_type="piano", vst_pfad=12345)
        assert os.path.exists(test_wav), "WAV must be generated when vst_pfad is invalid type"
        print("[PASS] VST Error Handling/Typecheck test completed successfully.")
        
    except Exception as e:
        pytest_fail = f"[FAIL] VST error handling failed: {e}"
        print(pytest_fail)
        raise e
    finally:
        if os.path.exists(test_mid): os.remove(test_mid)
        if os.path.exists(test_wav): os.remove(test_wav)

# ── 2. Vocal Synthesis Clipping Test ─────────────────────────────────────────
def test_vocal_clipping(vocals_wav_path, melody_data, bpm):
    """
    Verifies that the generated vocal WAV file has no hard digital clipping 
    overall, and checks that syllable boundaries have clean fade-in/out to prevent clicks.
    """
    print("\n--- Running Vocal Synthesis Clipping Test ---")
    assert os.path.exists(vocals_wav_path), f"Vocals WAV not found at {vocals_wav_path}"
    
    audio, sr = sf.read(vocals_wav_path)
    if len(audio.shape) > 1:
        audio = audio[:, 0]  # Take first channel
        
    # Check A: Absolute peak amplitude is strictly < 1.0 (with safe headroom, e.g., <= 0.95)
    max_amp = np.max(np.abs(audio))
    print(f"Max absolute amplitude: {max_amp:.4f}")
    assert max_amp < 1.0, f"Vocal audio is clipping! Max amplitude is {max_amp}"
    assert max_amp <= 0.96, f"Vocal audio exceeds the normalized headroom: {max_amp}"
    
    # Check B: Sudden click/discontinuity check using first-order difference
    diffs = np.abs(np.diff(audio))
    max_diff = np.max(diffs)
    print(f"Max sample-to-sample difference (click check): {max_diff:.4f}")
    assert max_diff < 0.95, f"Digital click/discontinuity detected! Max sample diff is {max_diff}"
    
    # Check C: Boundary anti-click fade-in/out check
    # Syllable boundaries are at cumulative sample counts based on duration
    quarter_sec = 60.0 / bpm
    current_sample = 0
    for idx, (pitch, dauer) in enumerate(melody_data):
        target_frames_len = int(dauer * quarter_sec * sr)
        if pitch is not None and target_frames_len > 50:
            # Check the first sample and last sample of the syllable
            start_val = np.abs(audio[current_sample])
            end_val = np.abs(audio[current_sample + target_frames_len - 1])
            
            # Anti-click fades in vocal_synthesizer.py pad and multiply by np.linspace(0, 1) / (1, 0).
            # The edge values should be very close to zero (e.g., < 0.05).
            assert start_val < 0.05, f"No fade-in at syllable start (idx {idx}, sample {current_sample}): value is {start_val}"
            assert end_val < 0.05, f"No fade-out at syllable end (idx {idx}, sample {current_sample + target_frames_len - 1}): value is {end_val}"
            
        current_sample += target_frames_len
        
    print("[PASS] Vocal synthesis clipping and click-prevention verified successfully.")

# ── 3. Vocal Pitch Transitions Test ──────────────────────────────────────────
def test_vocal_pitch_transitions(vocals_wav_path):
    """
    Verifies that the vocal pitch contour has smooth legato transitions 
    instead of raw, stepped jumps at note-to-note transitions.
    """
    print("\n--- Running Vocal Pitch Transitions Test ---")
    assert os.path.exists(vocals_wav_path), f"Vocals WAV not found at {vocals_wav_path}"
    
    audio, sr = sf.read(vocals_wav_path)
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    audio = audio.astype(np.float64)
    
    # Extract fundamental frequency (F0) using PyWorld
    _f0, t = pw.dio(audio, sr)
    f0 = pw.stonemask(audio, _f0, t, sr)
    
    voiced_indices = np.where(f0 > 0)[0]
    assert len(voiced_indices) > 0, "No voiced content detected in vocal track to verify pitch"
    
    # Find pitch transitions between consecutive voiced frames (5ms steps)
    sharp_jumps = 0
    total_transitions = 0
    
    for i in range(len(voiced_indices) - 1):
        idx1 = voiced_indices[i]
        idx2 = voiced_indices[i+1]
        
        # Check if they are adjacent in time (continuous voicing)
        if idx2 == idx1 + 1:
            total_transitions += 1
            hz_diff = abs(f0[idx2] - f0[idx1])
            # A stepped digital jump between notes (e.g. C4 to D4) would jump instantly 
            # by 32Hz in 1 frame. A smooth legato glide limits the frame-to-frame delta.
            # We assert that no frame-to-frame voiced pitch jump exceeds 35.0 Hz (~3.5 semitones/5ms).
            if hz_diff >= 35.0:
                sharp_jumps += 1
                print(f"Sharp pitch jump detected at {t[idx1]:.3f}s: {f0[idx1]:.2f}Hz -> {f0[idx2]:.2f}Hz (diff: {hz_diff:.2f}Hz)")
                
    print(f"Verified {total_transitions} voiced transitions. Sharp jumps detected: {sharp_jumps}")
    assert sharp_jumps == 0, f"Pitch transitions must be smooth. Detected {sharp_jumps} stepped jumps!"
    print("[PASS] Vocal pitch contour legato transitions verified successfully.")

# ── 4. MIDI Scale-locking Test ───────────────────────────────────────────────
def test_midi_scale_locking(tracks, key, mode):
    """
    Verifies that all generated MIDI notes in the melodic/harmonic tracks 
    belong strictly to the specified key/scale (A minor, C major, etc.).
    """
    print(f"\n--- Running MIDI Scale-locking Test (Key: {key} {mode}) ---")
    
    # Scale pitch classes offsets relative to the root
    scale_intervals = {
        "major":       [0, 2, 4, 5, 7, 9, 11],
        "minor":       [0, 2, 3, 5, 7, 8, 10],
        "dorian":      [0, 2, 3, 5, 7, 9, 10],
        "phrygian":    [0, 1, 3, 5, 7, 8, 10],
        "penta_minor": [0, 3, 5, 7, 10],
        "penta_major": [0, 2, 4, 7, 9],
    }
    
    key_offsets = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
        "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
    }
    
    root_offset = key_offsets[key]
    intervals = scale_intervals[mode]
    valid_classes = {(root_offset + interval) % 12 for interval in intervals}
    
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    valid_note_names = [note_names[pc] for pc in sorted(list(valid_classes))]
    print(f"Scale notes for {key} {mode}: {valid_note_names}")
    
    # Verify each track except drums (which uses MIDI pitches for percussion triggers)
    excluded_tracks = {"drums", "silben", "melody_data"}
    
    for track_name, notes in tracks.items():
        if track_name in excluded_tracks or not notes:
            continue
            
        print(f"Verifying track '{track_name}' ({len(notes)} notes)...")
        for idx, note in enumerate(notes):
            pitch_class = note.pitch % 12
            # Prohibit any out-of-scale pitches when strict scale locking is enabled
            assert pitch_class in valid_classes, (
                f"Scale-locking violation in track '{track_name}' at note index {idx}: "
                f"Note pitch {note.pitch} ({note_names[pitch_class]}) is outside the scale!"
            )
            
    print("[PASS] MIDI scale-locking validation passed. All pitches belong to the scale.")

# ── 5. MIDI Velocity Variation Test ──────────────────────────────────────────
def test_midi_velocity_variation(tracks):
    """
    Checks that notes in all generated tracks have humanized velocity variation
    and are not uniform (meaning velocity variance > 0).
    """
    print("\n--- Running MIDI Velocity Variation Test ---")
    excluded_tracks = {"silben", "melody_data"}
    
    for track_name, notes in tracks.items():
        if track_name in excluded_tracks or not notes:
            continue
            
        velocities = [n.velocity for n in notes]
        unique_vels = set(velocities)
        variance = np.var(velocities)
        
        print(f"Track '{track_name}': {len(notes)} notes, {len(unique_vels)} unique velocities, variance = {variance:.2f}")
        
        # Verify that velocities vary across notes (more than 1 unique velocity, non-zero variance)
        assert len(unique_vels) > 1, f"Velocities in track '{track_name}' are uniform! Humanization failed."
        assert variance > 0.5, f"Velocity variance in track '{track_name}' is too low ({variance:.2f})."
        
    print("[PASS] MIDI velocity variation verified. All tracks exhibit velocity dynamics.")

# ── 6. J-Pop Structural Sections Test ────────────────────────────────────────
def test_structural_sections(tracks, structure, section_config, bpm):
    """
    Confirms distinct J-Pop structural sections (Intro, Verse, Chorus, etc.) 
    are present in the generated MIDI and follow the track arrangement rules.
    """
    print("\n--- Running J-Pop Structural Sections Test ---")
    
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    # Calculate boundaries for each section in seconds
    current_time = 0.0
    sections = []
    for section_type in structure:
        bars = section_config[section_type]["bars"]
        duration = bars * bar_dur
        sections.append({
            "type": section_type,
            "start": current_time,
            "end": current_time + duration,
            "has_vocals": section_config[section_type]["has_vocals"]
        })
        current_time += duration
        
    print(f"Arrangement timeline: {len(sections)} sections, total duration = {current_time:.2f} seconds.")
    for s in sections:
        print(f"  - {s['type']}: {s['start']:.2f}s to {s['end']:.2f}s (Vocals: {s['has_vocals']})")
        
    # Verify arrangement rules per section window based on PATTERN_MAP
    genre_patterns = PATTERN_MAP["j-pop"]
    
    for sect in sections:
        s_type = sect["type"]
        s_start = sect["start"]
        s_end = sect["end"]
        s_has_vocals = sect["has_vocals"]
        
        # Check A: Vocal Melody presence/absence
        melody_notes = [n for n in tracks["melody"] if s_start - 0.01 <= n.start < s_end - 0.01]
        if s_has_vocals:
            assert len(melody_notes) > 0, (
                f"Section '{s_type}' ({s_start:.2f}-{s_end:.2f}s) expects vocals, "
                f"but melody track has no notes starting in this window."
            )
        else:
            assert len(melody_notes) == 0, (
                f"Section '{s_type}' ({s_start:.2f}-{s_end:.2f}s) expects NO vocals, "
                f"but melody track contains {len(melody_notes)} notes starting in this window."
            )
            
        # Check B: Instrument arrangement matches PATTERN_MAP for J-Pop
        # Resolve section config key (like in orchestrator.py fallback rules)
        sect_key = s_type
        if sect_key not in genre_patterns:
            if s_type in ("Build-up", "PreChorus"):
                sect_key = "Verse"
            else:
                sect_key = "Verse"
                
        sect_patterns = genre_patterns[sect_key]
        
        for inst, pattern_name in sect_patterns.items():
            if inst not in tracks:
                continue
            inst_notes = [n for n in tracks[inst] if s_start - 0.01 <= n.start < s_end - 0.01]
            
            if pattern_name is None:
                assert len(inst_notes) == 0, (
                    f"Instrument '{inst}' must be inactive in section '{s_type}' ({s_start:.2f}-{s_end:.2f}s), "
                    f"but has {len(inst_notes)} notes starting in this window."
                )
            else:
                assert len(inst_notes) > 0, (
                    f"Instrument '{inst}' must be active (pattern: {pattern_name}) in section '{s_type}' ({s_start:.2f}-{s_end:.2f}s), "
                    f"but has 0 notes starting in this window."
                )
                
    print("[PASS] J-Pop structural sections and arrangement rules verified successfully.")

# ── 7. Phrase Contour Test ──────────────────────────────────────────────────
def test_phrase_contour(tracks, structure, section_config, bpm):
    """
    Verifies Chorus melody phrases have an arch contour:
    - Pitch-peak occurs at index >= len(phrase)//2
    - Final note pitch < first note pitch
    """
    print("\n--- Running Phrase Contour Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    current_time = 0.0
    choruses = []
    for section_type in structure:
        bars = section_config.get(section_type, {"bars": 4})["bars"]
        duration = bars * bar_dur
        if section_type == "Chorus":
            choruses.append((current_time, current_time + duration))
        current_time += duration
        
    melody_notes = tracks.get("melody", [])
    assert len(melody_notes) > 0, "No melody notes found to verify contour!"
    
    for c_idx, (start, end) in enumerate(choruses):
        chorus_notes = [n for n in melody_notes if start - 0.01 <= n.start < end - 0.01]
        if not chorus_notes:
            continue
            
        # Group notes into phrases based on rest gap (> 0.15s)
        chorus_notes = sorted(chorus_notes, key=lambda n: n.start)
        phrases = []
        curr = []
        for n in chorus_notes:
            if not curr:
                curr.append(n)
            else:
                if n.start - curr[-1].end > 0.15:
                    phrases.append(curr)
                    curr = [n]
                else:
                    curr.append(n)
        if curr:
            phrases.append(curr)
            
        for p_idx, phrase in enumerate(phrases):
            if len(phrase) < 4:
                continue  # Skip short phrase fragments
            pitches = [n.pitch for n in phrase]
            max_p = max(pitches)
            peak_indices = [i for i, p in enumerate(pitches) if p == max_p]
            first_p = pitches[0]
            last_p = pitches[-1]
            
            # Assert pitch-peak in second half
            assert any(idx >= len(phrase)//2 for idx in peak_indices), \
                f"Chorus {c_idx} Phrase {p_idx}: Peak pitch {max_p} at indices {peak_indices} is not in second half for len {len(phrase)}!"
                
            # Assert arch contour: final note is lower than first note
            assert last_p < first_p, \
                f"Chorus {c_idx} Phrase {p_idx}: Last note ({last_p}) must be lower than first note ({first_p})!"
                
    print("[PASS] Phrase contour arch structures verified successfully.")


# ── 8. No Duplicate Progressions Test ──────────────────────────────────────
def test_no_duplicate_progressions(tracks):
    """
    Verifies that no two adjacent sections share the exact same list of root notes.
    """
    print("\n--- Running No Duplicate Progressions Test ---")
    section_roots = tracks.get("section_roots")
    assert section_roots is not None, "No section roots recorded in generated tracks (unimplemented feature)"
    assert len(section_roots) > 0, "No section roots recorded in generated tracks"
    
    for i in range(len(section_roots) - 1):
        sec1 = section_roots[i]
        sec2 = section_roots[i+1]
        if sec1["type"] in ("Intro", "Outro") or sec2["type"] in ("Intro", "Outro"):
            continue
        assert sec1["roots"] != sec2["roots"], \
            f"Adjacent sections share identical root progressions! Section {sec1['section_idx']} ({sec1['type']}) vs Section {sec2['section_idx']} ({sec2['type']}): {sec1['roots']}"
            
    print("[PASS] Adjacent section progressions are distinct.")


# ── 9. Velocity Arc Test ────────────────────────────────────────────────────
def test_velocity_arc(tracks, structure, section_config, bpm):
    """
    Verifies that mean_velocity(Intro) < mean_velocity(Verse) < mean_velocity(Chorus)
    across all instrument tracks.
    """
    print("\n--- Running Velocity Arc Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    def get_mean_vel(section_name):
        current_time = 0.0
        windows = []
        for section_type in structure:
            bars = section_config.get(section_type, {"bars": 4})["bars"]
            duration = bars * bar_dur
            if section_type == section_name:
                windows.append((current_time, current_time + duration))
            current_time += duration
            
        vels = []
        for t_name, notes in tracks.items():
            if t_name in ("silben", "melody_data", "section_roots"):
                continue
            for n in notes:
                for start, end in windows:
                    if start - 0.01 <= n.start < end - 0.01:
                        vels.append(n.velocity)
                        break
        return np.mean(vels) if vels else 0.0

    mean_intro = get_mean_vel("Intro")
    mean_verse = get_mean_vel("Verse")
    mean_chorus = get_mean_vel("Chorus")
    
    print(f"Mean Velocities - Intro: {mean_intro:.2f}, Verse: {mean_verse:.2f}, Chorus: {mean_chorus:.2f}")
    assert mean_intro < mean_verse, f"Intro velocity ({mean_intro:.2f}) must be < Verse velocity ({mean_verse:.2f})!"
    assert mean_verse < mean_chorus, f"Verse velocity ({mean_verse:.2f}) must be < Chorus velocity ({mean_chorus:.2f})!"
    print("[PASS] Velocity arc verified (Intro < Verse < Chorus).")


# ── 10. Drop Section Silence Test ──────────────────────────────────────────
def test_drop_section_silence(tracks, structure, section_config, bpm):
    """
    Verifies that in the Drop section:
    - Only MIDI notes present are on kick and bass channels (pitch 36 for kick on drums)
    - All other tracks are completely silent
    """
    print("\n--- Running Drop Section Silence Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    current_time = 0.0
    drop_windows = []
    for section_type in structure:
        bars = section_config.get(section_type, {"bars": 4})["bars"]
        duration = bars * bar_dur
        if section_type == "Drop":
            drop_windows.append((current_time, current_time + duration))
        current_time += duration
        
    assert len(drop_windows) > 0, "No 'Drop' section found in song structure! (unimplemented feature)"
    
    for start, end in drop_windows:
        # Check non-bass and non-drum tracks are empty
        for track_name, notes in tracks.items():
            if track_name in ("drums", "bass", "silben", "melody_data", "section_roots"):
                continue
            notes_in_drop = [n for n in notes if start - 0.01 <= n.start < end - 0.01]
            assert len(notes_in_drop) == 0, \
                f"Track '{track_name}' contains {len(notes_in_drop)} notes in Drop section, must be silent!"
                
        # Check drums track is kick-only (pitch 36)
        drum_notes = [n for n in tracks.get("drums", []) if start - 0.01 <= n.start < end - 0.01]
        assert len(drum_notes) > 0, "Drums track has no notes in Drop section"
        for n in drum_notes:
            assert n.pitch == 36, f"Non-kick drum note (pitch {n.pitch}) found in Drop section!"
            
        # Check bass track has active notes
        bass_notes = [n for n in tracks.get("bass", []) if start - 0.01 <= n.start < end - 0.01]
        assert len(bass_notes) > 0, "Bass track must be active in Drop section"
        
    print("[PASS] Drop section silence and kick/bass-only constraints verified.")


# ── 11. Final Chorus Pitch Shift Test ──────────────────────────────────────
def test_final_chorus_pitch_shift(tracks, structure, section_config, bpm):
    """
    Verifies that the final Chorus is modulated at least 1 semitone higher than Chorus 2.
    """
    print("\n--- Running Final Chorus Pitch Shift Test ---")
    beat_dur = 60.0 / bpm
    bar_dur = 4 * beat_dur
    
    current_time = 0.0
    choruses = []
    for section_type in structure:
        bars = section_config.get(section_type, {"bars": 4})["bars"]
        duration = bars * bar_dur
        if section_type == "Chorus":
            choruses.append((current_time, current_time + duration))
        current_time += duration
        
    assert len(choruses) >= 2, f"Need at least 2 Chorus sections to test modulation, found {len(choruses)}"
    
    chorus_2 = choruses[1]
    chorus_final = choruses[-1]
    
    melody_notes = tracks.get("melody", [])
    notes_c2 = [n for n in melody_notes if chorus_2[0] - 0.01 <= n.start < chorus_2[1] - 0.01]
    notes_cf = [n for n in melody_notes if chorus_final[0] - 0.01 <= n.start < chorus_final[1] - 0.01]
    
    assert len(notes_c2) > 0, "No melody notes found in Chorus 2"
    assert len(notes_cf) > 0, "No melody notes found in Chorus Final"
    
    mean_c2 = np.mean([n.pitch for n in notes_c2])
    mean_cf = np.mean([n.pitch for n in notes_cf])
    
    print(f"Mean Pitch - Chorus 2: {mean_c2:.2f}, Chorus Final: {mean_cf:.2f} (diff: {mean_cf - mean_c2:.2f})")
    assert mean_cf - mean_c2 >= 0.99, \
        f"Chorus Final mean pitch ({mean_cf:.2f}) must be >= 1 semitone higher than Chorus 2 ({mean_c2:.2f})!"
        
    print("[PASS] Final Chorus pitch modulation verified successfully.")


# ── 12. Lyric Continuity Test ──────────────────────────────────────────────
def test_lyric_continuity():
    """
    Verifies that SONG_TEXT_VERSE does not contain space-separated single kana.
    """
    print("\n--- Running Lyric Continuity Test ---")
    import re
    from config import SONG_TEXT_VERSE
    
    # Matches a single hiragana followed by whitespace and another single hiragana
    pattern = r'[ぁ-ん]\s+[ぁ-ん]'
    match = re.search(pattern, SONG_TEXT_VERSE)
    assert match is None, \
        f"SONG_TEXT_VERSE contains space-separated single-kana sequences: '{match.group(0) if match else ''}' found in: {SONG_TEXT_VERSE}"
        
    print("[PASS] Lyric continuity (no space-separated single-kana) verified successfully.")


# ── standalone Runner ────────────────────────────────────────────────────────
def run_all_tests():
    print("======================================================================")
    print("STARTING PROGRAMMATIC J-POP GENERATOR VERIFICATION SUITE")
    print("======================================================================")
    
    # 1. Run VST error handling / Typecheck test
    test_vst_error_handling()
    
    # 2. Run orchestration to obtain midi tracks for subsequent tests
    print("\n--- Generating J-Pop Song for Verification ---")
    
    # We enforce STRICT_SCALE_LOCKING for this generation
    import config
    config.STRICT_SCALE_LOCKING = True  # Enable proposed strict scale locking
    
    tracks = orchestrate_song(
        genre="J-Pop",
        bpm=BPM,
        structure=SONG_STRUCTURE,
        key=KEY,
        mode=MODE,
        section_config=SECTION_CONFIG
    )
    
    # 3. Generate Vocals using local synthesizer
    vocals_wav_path = os.path.join(OUTPUT_ORDNER, "vocals_test.wav")
    melody_data = tracks.get("melody_data", [])
    silben = tracks.get("silben", [])
    
    print("\n--- Generating Local Vocals for Verification ---")
    generiere_lokale_vocals(melody_data, silben, BPM, vocals_wav_path, breathiness=0.03, shimmer=True)
    
    # Run tests on the generated outputs
    try:
        test_vocal_clipping(vocals_wav_path, melody_data, BPM)
        test_vocal_pitch_transitions(vocals_wav_path)
        test_midi_scale_locking(tracks, KEY, MODE)
        test_midi_velocity_variation(tracks)
        test_structural_sections(tracks, SONG_STRUCTURE, SECTION_CONFIG, BPM)
        
        # Call the 6 new verification tests
        test_phrase_contour(tracks, SONG_STRUCTURE, SECTION_CONFIG, BPM)
        test_no_duplicate_progressions(tracks)
        test_velocity_arc(tracks, SONG_STRUCTURE, SECTION_CONFIG, BPM)
        test_drop_section_silence(tracks, SONG_STRUCTURE, SECTION_CONFIG, BPM)
        test_final_chorus_pitch_shift(tracks, SONG_STRUCTURE, SECTION_CONFIG, BPM)
        test_lyric_continuity()
        
        print("\n======================================================================")
        print("ALL VERIFICATION TESTS COMPLETED AND PASSED SUCCESSFULLY!")
        print("======================================================================")
    finally:
        # Clean up temporary test vocals WAV file
        if os.path.exists(vocals_wav_path):
            try: os.remove(vocals_wav_path)
            except: pass

if __name__ == "__main__":
    run_all_tests()
