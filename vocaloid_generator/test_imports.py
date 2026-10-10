# test_imports.py - Verification Script for Import and Basic Generation
import sys
import os

# Ensure the module can import local files
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator import orchestrate_song
from config import SONG_STRUCTURE, SECTION_CONFIG

def run_tests():
    print("=== STARTING IMPORT AND COMPILATION CHECKS ===")
    
    genres = ["J-Pop", "Rock", "EDM", "Lo-Fi"]
    bpms = [160, 120, 128, 75]
    
    for genre, bpm in zip(genres, bpms):
        print(f"\n--- Testing Orchestration for Genre: {genre} at BPM: {bpm} ---")
        try:
            tracks = orchestrate_song(
                genre=genre,
                bpm=bpm,
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
            print(f"[SUCCESS] Generated tracks: {list(tracks.keys())}")
            for name, notes in tracks.items():
                print(f"  - {name}: {len(notes)} notes")
        except Exception as e:
            print(f"[FAIL] Error orchestrating {genre}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
            
    print("\n=== ALL SYNTAX, IMPORT, AND GENERATION TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_tests()
