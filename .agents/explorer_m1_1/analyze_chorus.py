import os
import sys
sys.path.append(r"c:\Users\cilli\OneDrive\Desktop\vocaloid_musik")
sys.path.append(r"c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\vocaloid_generator")

import numpy as np
from vocaloid_generator.config import BPM, SONG_STRUCTURE, SECTION_CONFIG, KEY, MODE
from vocaloid_generator.orchestrator import orchestrate_song

tracks = orchestrate_song(
    genre="J-Pop",
    bpm=BPM,
    structure=SONG_STRUCTURE,
    key=KEY,
    mode=MODE,
    section_config=SECTION_CONFIG
)

melody_notes = tracks["melody"]
bpm = BPM
beat_dur = 60.0 / bpm
bar_dur = 4 * beat_dur

# Find Chorus sections
current_time = 0.0
sections = []
for section_type in SONG_STRUCTURE:
    bars = SECTION_CONFIG[section_type]["bars"]
    duration = bars * bar_dur
    sections.append({
        "type": section_type,
        "start": current_time,
        "end": current_time + duration
    })
    current_time += duration

# Extract Chorus melody notes and group them into phrases
for idx, sec in enumerate(sections):
    if sec["type"] == "Chorus":
        print(f"\n--- Chorus Section {idx} ({sec['start']:.2f}s - {sec['end']:.2f}s) ---")
        chorus_notes = [n for n in melody_notes if sec["start"] - 0.01 <= n.start < sec["end"] - 0.01]
        
        phrases = []
        curr = []
        for n in chorus_notes:
            if not curr:
                curr.append(n)
            else:
                if n.start - curr[-1].end > 0.1:
                    phrases.append(curr)
                    curr = [n]
                else:
                    curr.append(n)
        if curr:
            phrases.append(curr)
            
        print(f"Total phrases found: {len(phrases)}")
        for p_idx, phrase in enumerate(phrases):
            pitches = [n.pitch for n in phrase]
            max_p = max(pitches)
            peak_indices = [i for i, n in enumerate(phrase) if n.pitch == max_p]
            first_p = pitches[0]
            last_p = pitches[-1]
            peak_cond = any(i >= len(phrase)//2 for i in peak_indices)
            contour_cond = last_p < first_p
            print(f"  Phrase {p_idx}: length={len(phrase)}, pitches={pitches}")
            print(f"    Peak pitch: {max_p} at indices {peak_indices} (>=len//2 ({len(phrase)//2}): {peak_cond})")
            print(f"    First pitch: {first_p}, Last pitch: {last_p} (last < first: {contour_cond})")
