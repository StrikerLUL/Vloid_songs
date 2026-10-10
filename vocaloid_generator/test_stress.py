# test_stress.py - Automated Stress Testing Script for J-Pop Generator
import os
import sys
import numpy as np
import pretty_midi
import soundfile as sf
import traceback

# Ensure we can import the modules from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import both configs to bypass duplicate module import issue
import config as standalone_config
import vocaloid_generator.config as package_config

# Set STRICT_SCALE_LOCKING to True on both config instances
standalone_config.STRICT_SCALE_LOCKING = True
package_config.STRICT_SCALE_LOCKING = True

from orchestrator import orchestrate_song, PATTERN_MAP
from vocal_synthesizer import generiere_lokale_vocals, neutrino_synthese

# Scale offsets and interval maps for verification
SCALE_INTERVALS = {
    "major":       [0, 2, 4, 5, 7, 9, 11],
    "minor":       [0, 2, 3, 5, 7, 8, 10],
    "dorian":      [0, 2, 3, 5, 7, 9, 10],
    "phrygian":    [0, 1, 3, 5, 7, 8, 10],
    "penta_minor": [0, 3, 5, 7, 10],
    "penta_major": [0, 2, 4, 7, 9],
}

KEY_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
}

def verify_scale_locking(tracks, key, mode):
    """Checks if all notes in non-drum tracks belong strictly to the scale."""
    root_offset = KEY_OFFSETS[key]
    intervals = SCALE_INTERVALS[mode]
    valid_classes = {(root_offset + interval) % 12 for interval in intervals}
    
    violations = []
    excluded_tracks = {"drums", "silben", "melody_data"}
    
    for track_name, notes in tracks.items():
        if track_name in excluded_tracks or not notes:
            continue
        for idx, note in enumerate(notes):
            pitch_class = note.pitch % 12
            if pitch_class not in valid_classes:
                violations.append((track_name, idx, note.pitch))
    return violations

def verify_wav_clipping(wav_path):
    """Checks if the WAV file clips (absolute peak >= 1.0 or exceeding headroom 0.96)."""
    if not os.path.exists(wav_path):
        return "File not found", 0.0, 0.0
    
    audio, sr = sf.read(wav_path)
    if len(audio.shape) > 1:
        audio = audio[:, 0]
        
    max_amp = np.max(np.abs(audio))
    
    # Click check (sample-to-sample difference)
    diffs = np.abs(np.diff(audio))
    max_diff = np.max(diffs)
    
    is_clipping = max_amp >= 1.0 or max_amp > 0.96
    is_clicking = max_diff >= 0.8
    
    status = []
    if is_clipping: status.append("CLIPPING")
    if is_clicking: status.append("CLICKING")
    
    return ",".join(status) if status else "PASS", max_amp, max_diff

def run_stress_test():
    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".agents", "teamwork_preview_challenger_m2_1", "stress_test_log.txt"
    )
    
    test_cases = [
        # 1. Base verification configurations
        {"key": "A", "mode": "minor", "bpm": 160, "engine": "LOCAL"},
        # 2. Key variations
        {"key": "C", "mode": "major", "bpm": 160, "engine": "LOCAL"},
        {"key": "E", "mode": "minor", "bpm": 160, "engine": "LOCAL"},
        {"key": "D", "mode": "phrygian", "bpm": 160, "engine": "LOCAL"},
        {"key": "G", "mode": "dorian", "bpm": 160, "engine": "LOCAL"},
        # 3. BPM variations
        {"key": "A", "mode": "minor", "bpm": 90, "engine": "LOCAL"},
        {"key": "A", "mode": "minor", "bpm": 200, "engine": "LOCAL"},
        # 4. Engine variations
        {"key": "A", "mode": "minor", "bpm": 160, "engine": "NEUTRINO"},
    ]
    
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("======================================================================\n")
        log.write("J-POP GENERATOR STRESS TESTING REPORT\n")
        log.write("======================================================================\n\n")
        
        log.write("[BUG ANALYSIS - MODULE DUPLICATE IMPORT DETECTED]\n")
        log.write("Note: There is a module import duplicate bug in the system. \n")
        log.write("orchestrator.py imports 'config' directly from path, while test_jpop_verification.py\n")
        log.write("imports 'vocaloid_generator.config'. This causes them to load config.py as separate\n")
        log.write("module objects, meaning config.STRICT_SCALE_LOCKING = True set by the test script is\n")
        log.write("NOT seen by orchestrator.py, causing it to run with STRICT_SCALE_LOCKING = False by default.\n")
        log.write("This stress-test script fixes this issue by setting the flag on BOTH module instances.\n\n")
        
        # Test with STRICT_SCALE_LOCKING = True on both configs
        log.write("--- PHASE 1: TESTING WITH FIXED STRICT_SCALE_LOCKING = True ---\n\n")
        
        for idx, case in enumerate(test_cases):
            key = case["key"]
            mode = case["mode"]
            bpm = case["bpm"]
            engine = case["engine"]
            
            log.write(f"Test Case {idx+1}: Key={key} {mode}, BPM={bpm}, Engine={engine}\n")
            
            # Temporary override in packages
            standalone_config.KEY = key
            standalone_config.MODE = mode
            standalone_config.BPM = bpm
            standalone_config.VOCAL_ENGINE = engine
            
            package_config.KEY = key
            package_config.MODE = mode
            package_config.BPM = bpm
            package_config.VOCAL_ENGINE = engine
            
            try:
                # 1. Orchestrate song
                tracks = orchestrate_song(
                    genre="J-Pop",
                    bpm=bpm,
                    structure=standalone_config.SONG_STRUCTURE,
                    key=key,
                    mode=mode,
                    section_config=standalone_config.SECTION_CONFIG
                )
                
                # 2. Check Scale Locking
                violations = verify_scale_locking(tracks, key, mode)
                if violations:
                    log.write(f"  [FAIL] Scale locking violations found: {len(violations)} notes out of scale!\n")
                    for t_name, n_idx, pitch in violations[:5]:
                        log.write(f"    - Track '{t_name}' note {n_idx}: pitch {pitch} (PC {pitch % 12})\n")
                else:
                    log.write("  [PASS] Scale locking verified. All non-drum notes are scale locked.\n")
                    
                # 3. Generate Vocals
                vocals_wav_path = f"vocals_temp_{idx}.wav"
                melody_data = tracks.get("melody_data", [])
                silben = tracks.get("silben", [])
                
                vocals_generated = False
                if engine == "NEUTRINO":
                    xml_path = "vocals_temp.xml"
                    from vocal_synthesizer import erstelle_musicxml
                    xml_file = erstelle_musicxml(melody_data, silben, bpm, xml_path)
                    if os.path.exists(xml_file):
                        # Try NEUTRINO, fall back to local if binary fails
                        try:
                            vocals_generated = neutrino_synthese(
                                xml_file, vocals_wav_path, 
                                standalone_config.NEUTRINO_PFAD, 
                                standalone_config.NEUTRINO_MODEL_PFAD
                            )
                        except Exception as e:
                            log.write(f"  [WARN] NEUTRINO failed: {e}. Falling back to LOCAL...\n")
                            vocals_generated = False
                        finally:
                            if os.path.exists(xml_file): os.remove(xml_file)
                            
                if not vocals_generated:
                    # Fallback to local vocoder
                    generiere_lokale_vocals(melody_data, silben, bpm, vocals_wav_path, breathiness=0.03, shimmer=True)
                    vocals_generated = True
                    
                # 4. Check WAV clipping and clicking
                if os.path.exists(vocals_wav_path):
                    status, max_amp, max_diff = verify_wav_clipping(vocals_wav_path)
                    log.write(f"  [WAV Check] Status={status}, Max Peak={max_amp:.4f}, Max Diff={max_diff:.4f}\n")
                    os.remove(vocals_wav_path)
                else:
                    log.write("  [FAIL] Vocals WAV was not generated.\n")
                    
            except Exception as e:
                log.write(f"  [CRASH] Test case crashed with exception: {e}\n")
                log.write(traceback.format_exc())
                
            log.write("-" * 50 + "\n\n")
            
        # Test with STRICT_SCALE_LOCKING = False to show what happens without fixing the bug
        log.write("--- PHASE 2: TESTING WITH STRICT_SCALE_LOCKING = False (BUG REPRODUCTION) ---\n\n")
        standalone_config.STRICT_SCALE_LOCKING = False
        package_config.STRICT_SCALE_LOCKING = False
        
        # Test with C Major to show chromatic bass and melody out-of-scale pitches
        log.write("Reproduction Case: Key=C major, BPM=160, STRICT_SCALE_LOCKING=False\n")
        try:
            tracks = orchestrate_song(
                genre="J-Pop",
                bpm=160,
                structure=standalone_config.SONG_STRUCTURE,
                key="C",
                mode="major",
                section_config=standalone_config.SECTION_CONFIG
            )
            violations = verify_scale_locking(tracks, "C", "major")
            if violations:
                log.write(f"  [EXPECTED FAIL] Scale locking violations found: {len(violations)} notes out of scale!\n")
                for t_name, n_idx, pitch in violations[:10]:
                    log.write(f"    - Track '{t_name}' note {n_idx}: pitch {pitch} (PC {pitch % 12} - expected F#/pitch class 6 for C major)\n")
            else:
                log.write("  [WARN] No violations found? Check generator settings.\n")
        except Exception as e:
            log.write(f"  [CRASH] Reproduction case crashed: {e}\n")
            
        log.write("\n======================================================================\n")
        log.write("END OF REPORT\n")
        log.write("======================================================================\n")
        
    print(f"Stress test log written to: {log_path}")

if __name__ == "__main__":
    run_stress_test()
