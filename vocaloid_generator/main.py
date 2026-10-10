# main.py – Startet den kompletten Song-Generator

from config import *
from orchestrator import orchestrate_song
from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, generiere_lokale_vocals
from mixer import midi_zu_wav, mische_spuren
from exporter import exportiere_song
import os
import pretty_midi

# Output-Ordner erstellen
os.makedirs(OUTPUT_ORDNER, exist_ok=True)

if __name__ == "__main__":
    print("=== Vocaloid Song Generator (Advanced Sound Design) ===\n")

    # 1. Parameter aus config lesen (STYLE, BPM, SONG_STRUCTURE, KEY, MODE, SECTION_CONFIG)
    print(f"Genre/Style: {STYLE}")
    print(f"BPM: {BPM}")
    print(f"Key: {KEY} {MODE}")
    print(f"Structure: {SONG_STRUCTURE}")
    
    # 2. orchestrate_song aufrufen, um alle MIDI-Spuren sowie melody_data und silben zu erhalten
    tracks = orchestrate_song(
        genre=STYLE,
        bpm=BPM,
        structure=SONG_STRUCTURE,
        key=KEY,
        mode=MODE,
        section_config=SECTION_CONFIG
    )
    
    # 3. melody_data und silben extrahieren
    melody_data = tracks.get("melody_data", [])
    silben = tracks.get("silben", [])
    
    # Phase 4: Vocals Synthese
    print("\n[4/6] Synthetisiere Vocals...")
    xml_pfad_vorgabe = os.path.join(OUTPUT_ORDNER, "vocals.xml")
    vocals_wav_path = os.path.join(OUTPUT_ORDNER, "vocals.wav")

    if len(melody_data) > 0 and len(silben) > 0:
        xml_pfad = erstelle_musicxml(melody_data, silben, BPM, xml_pfad_vorgabe)

        if VOCAL_ENGINE == "NEUTRINO":
            try:
                neutrino_synthese(xml_pfad, vocals_wav_path, NEUTRINO_PFAD, NEUTRINO_MODEL_PFAD)
            except Exception as e:
                print(f"NEUTRINO fehlgeschlagen: {e}. Nutze lokale Synthese...")
                generiere_lokale_vocals(melody_data, silben, BPM, vocals_wav_path)
        else:
            generiere_lokale_vocals(melody_data, silben, BPM, vocals_wav_path)
    else:
        print("[Warnung] Keine Melodiedaten oder Silben vorhanden. Überspringe Vocal-Synthese.")
        if os.path.exists(vocals_wav_path):
            try:
                os.remove(vocals_wav_path)
            except:
                pass

    # Phase 5: MIDI → WAV & Mix
    print("\n[5/6] Konvertiere MIDI zu WAV & Mixe...")
    instruments = ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody"]
    spur_pfade = []
    lautstaerken = []
    
    vol_map = {
        "drums": 1.0,
        "bass": 0.9,
        "piano": 0.8,
        "guitar": 0.8,
        "strings": 0.7,
        "synth": 0.7,
        "brass": 0.7,
        "melody": 0.8
    }
    
    for inst in instruments:
        mid_file = f"{inst}.mid"
        wav_file = f"{inst}.wav"
        mid_path = os.path.join(OUTPUT_ORDNER, mid_file)
        wav_path = os.path.join(OUTPUT_ORDNER, wav_file)
        
        # Nur rendern, wenn die Spur Noten hat
        if inst in tracks and len(tracks[inst]) > 0:
            print(f"Rendere {inst} ({len(tracks[inst])} Noten) zu WAV...")
            is_drum = (inst == "drums")
            midi_zu_wav(mid_path, wav_path, is_drum=is_drum, instrument_type=inst)
            if os.path.exists(wav_path):
                spur_pfade.append(wav_path)
                lautstaerken.append(vol_map.get(inst, 0.8))
        else:
            # Falls Datei von altem Run existiert, löschen, um Mischen zu verhindern
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except:
                    pass

    # Vocals-Spur hinzufügen, falls vorhanden
    if os.path.exists(vocals_wav_path):
        spur_pfade.append(vocals_wav_path)
        lautstaerken.append(1.1)

    if len(spur_pfade) > 0:
        final_mix_path = os.path.join(OUTPUT_ORDNER, "final_mix.wav")
        mische_spuren(
            spur_pfade=spur_pfade,
            lautstaerken=lautstaerken,
            output_pfad=final_mix_path
        )

        # Phase 6: Export
        print("\n[6/6] Exportiere finalen Song...")
        exportiere_song(
            wav_pfad=final_mix_path,
            mp3_pfad=os.path.join(OUTPUT_ORDNER, "final_song.mp3")
        )
        print("\n[OK] Song fertig! Gespeichert in output/final_song.mp3")
    else:
        print("[FEHLER] Keine Audiospuren zum Mischen vorhanden.")
