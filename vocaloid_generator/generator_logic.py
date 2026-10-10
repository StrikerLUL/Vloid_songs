# generator_logic.py – Kern-Logik für den Aufruf durch die GUI

from config import *
from beat_generator import generiere_beat_sektion
from melody_generator import generiere_melodie_sektion
from chord_generator import generiere_akkorde_sektion
from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, generiere_lokale_vocals, openutau_synthese, diffsinger_synthese
from mixer import midi_zu_wav, mische_spuren
from exporter import exportiere_song
import os
import pretty_midi


def starte_generierung(
    update_status_func,
    verse_text=None,
    chorus_text=None,
    prechorus_text=None,
    bridge_text=None,
    bpm=None,
    style="J-Pop Energy",
    energy="Hoch",
    singer="MERROW",
    key=None,
    mode=None,
    breathiness=None,
    shimmer=None,
    swing=None,
    song_structure=None,
    vocal_engine=None,
    vst_pfad=None,
):
    """
    Führt den gesamten Generierungsprozess aus.
    Alle Parameter können aus der GUI überschrieben werden.
    """
    try:
        # ── Parameter finalisieren ─────────────────────────────────────────────
        final_bpm        = int(bpm) if bpm else BPM
        final_key        = key   if key   else KEY
        final_mode       = mode  if mode  else MODE
        final_breathiness= float(breathiness) if breathiness is not None else VOCAL_BREATHINESS
        final_shimmer    = shimmer if shimmer is not None else VOCAL_SHIMMER
        final_swing      = float(swing) if swing is not None else SWING
        final_structure  = song_structure if song_structure else SONG_STRUCTURE
        final_vocal_engine = vocal_engine if vocal_engine else VOCAL_ENGINE
        final_vst_pfad   = vst_pfad if vst_pfad else VST3_SYNTH_PFAD

        # Style → Modus-Anpassung (BPM und Energie werden nicht mehr überschrieben, um GUI-Werte zu respektieren!)
        if style == "Ballade":
            final_mode = "minor"
        elif style == "Rock":
            pass # Keine Zwangs-BPM mehr
        elif style == "City Pop":
            final_mode = "dorian"
        elif style == "Dark Vocaloid":
            final_mode = "phrygian"
        elif style == "Kawaii Chiptune":
            final_mode = "minor"
            final_shimmer = True
            final_swing = 0.05

        # Texte
        final_verse     = verse_text     if verse_text     else SONG_TEXT_VERSE
        final_chorus    = chorus_text    if chorus_text    else SONG_TEXT_CHORUS
        final_prechorus = prechorus_text if prechorus_text else SONG_TEXT_PRECHORUS
        final_bridge    = bridge_text    if bridge_text    else SONG_TEXT_BRIDGE

        text_map = {
            "Intro":     final_chorus,
            "Verse":     final_verse,
            "PreChorus": final_prechorus,
            "Chorus":    final_chorus,
            "Bridge":    final_bridge,
        }

        # NEUTRINO-Modell-Pfad
        aktueller_model_pfad = os.path.join(NEUTRINO_PFAD, "model", singer)

        os.makedirs(OUTPUT_ORDNER, exist_ok=True)
        update_status_func("Starte Generierung...")
        update_status_func(f"  BPM={final_bpm}  Tonart={final_key}-{final_mode}  Energie={energy}")

        # ── MIDI-Container ─────────────────────────────────────────────────────
        midi_beat   = pretty_midi.PrettyMIDI(initial_tempo=final_bpm)
        drums       = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

        midi_melody = pretty_midi.PrettyMIDI(initial_tempo=final_bpm)
        melody_synth= pretty_midi.Instrument(program=81, name="Lead Synth")

        midi_chords = pretty_midi.PrettyMIDI(initial_tempo=final_bpm)
        chord_instruments = {}
        melody_doubler = pretty_midi.Instrument(program=80, name="Vocal Doubler Synth")

        gesamte_melodie_daten = []
        gesamte_silben        = []
        aktuell_sekunden      = 0.0
        viertel_dauer         = 60.0 / final_bpm

        # ── Sektionen generieren ───────────────────────────────────────────────
        for section_type in final_structure:
            if section_type not in SECTION_CONFIG:
                continue  # Unbekannte Sektion überspringen

            update_status_func(f"  Generiere: {section_type}...")
            config = SECTION_CONFIG[section_type]
            bars   = config["bars"]

            # Beat
            drums.notes.extend(
                generiere_beat_sektion(final_bpm, bars, section_type, aktuell_sekunden, final_swing, style=style)
            )

            # Akkorde
            chord_data = generiere_akkorde_sektion(
                final_bpm, bars, section_type, aktuell_sekunden, final_key, final_mode, style=style
            )
            for item in chord_data:
                name  = item[0]
                cnotes = item[1]
                prog  = item[2]
                is_drum = len(item) > 3 and item[3]

                if name not in chord_instruments:
                    chord_instruments[name] = pretty_midi.Instrument(
                        program=prog, is_drum=is_drum, name=name
                    )
                chord_instruments[name].notes.extend(cnotes)

            # Melodie & Vocals
            has_vocals = config["has_vocals"]
            if style == "Kawaii Chiptune" and section_type == "Intro":
                has_vocals = True

            if has_vocals:
                text   = text_map.get(section_type, final_verse)
                silben = text.split()
                sec_notes, sec_mel, next_start = generiere_melodie_sektion(
                    final_bpm, silben, section_type, aktuell_sekunden,
                    energy, final_key, final_mode, final_swing, style=style
                )
                melody_synth.notes.extend(sec_notes)
                if style == "Kawaii Chiptune":
                    for n in sec_notes:
                        melody_doubler.notes.append(pretty_midi.Note(
                            velocity=int(n.velocity * 0.58),
                            pitch=n.pitch,
                            start=n.start,
                            end=n.end
                        ))
                gesamte_melodie_daten.extend(sec_mel)
                gesamte_silben.extend(silben)

            aktuell_sekunden += bars * 4 * viertel_dauer

        # ── MIDI speichern ─────────────────────────────────────────────────────
        update_status_func("Speichere MIDI-Dateien...")
        midi_beat.instruments.append(drums)
        midi_beat.write(os.path.join(OUTPUT_ORDNER, "beat.mid"))

        midi_melody.instruments.append(melody_synth)
        midi_melody.write(os.path.join(OUTPUT_ORDNER, "melody.mid"))

        for inst in chord_instruments.values():
            midi_chords.instruments.append(inst)
        if len(melody_doubler.notes) > 0:
            midi_chords.instruments.append(melody_doubler)
        midi_chords.write(os.path.join(OUTPUT_ORDNER, "chords.mid"))

        # ── Vocals ─────────────────────────────────────────────────────────────
        update_status_func(f"Synthetisiere Vocals ({final_vocal_engine}/{singer})...")
        xml_pfad_vorgabe = os.path.join(OUTPUT_ORDNER, "vocals.xml")
        wav_pfad         = os.path.join(OUTPUT_ORDNER, "vocals.wav")
        xml_pfad = erstelle_musicxml(gesamte_melodie_daten, gesamte_silben, final_bpm, xml_pfad_vorgabe)

        if final_vocal_engine == "NEUTRINO":
            try:
                update_status_func("NEUTRINO rechnet (das kann dauern)...")
                neutrino_synthese(xml_pfad, wav_pfad, NEUTRINO_PFAD, aktueller_model_pfad)
            except Exception as e:
                update_status_func(f"NEUTRINO Fehler: {e}. Nutze Fallback.")
                generiere_lokale_vocals(gesamte_melodie_daten, gesamte_silben, final_bpm, wav_pfad, breathiness=final_breathiness, shimmer=final_shimmer)
        elif final_vocal_engine == "OPENUTAU":
            update_status_func("Rufe OpenUTAU CLI auf...")
            erfolg = openutau_synthese(xml_pfad, wav_pfad)
            if not erfolg:
                generiere_lokale_vocals(gesamte_melodie_daten, gesamte_silben, final_bpm, wav_pfad, breathiness=final_breathiness, shimmer=final_shimmer)
        elif final_vocal_engine == "DIFFSINGER":
            update_status_func("Erstelle DiffSinger Projekt...")
            diffsinger_synthese(gesamte_melodie_daten, gesamte_silben, final_bpm, wav_pfad)
            generiere_lokale_vocals(gesamte_melodie_daten, gesamte_silben, final_bpm, wav_pfad, breathiness=final_breathiness, shimmer=final_shimmer)
        else:
            update_status_func("Nutze lokalen Synth...")
            generiere_lokale_vocals(gesamte_melodie_daten, gesamte_silben, final_bpm, wav_pfad, breathiness=final_breathiness, shimmer=final_shimmer)

        # ── MIDI -> WAV ─────────────────────────────────────────────────────────
        update_status_func("Konvertiere MIDI -> WAV...")
        for name in ["beat", "melody", "chords"]:
            midi_zu_wav(
                os.path.join(OUTPUT_ORDNER, f"{name}.mid"),
                os.path.join(OUTPUT_ORDNER, f"{name}.wav"),
                is_drum=(name == "beat"),
                instrument_type=name,
                vst_pfad=final_vst_pfad
            )

        # ── Mix ────────────────────────────────────────────────────────────────
        update_status_func("Mixe Tracks...")
        mische_spuren(
            spur_pfade=[os.path.join(OUTPUT_ORDNER, f"{n}.wav") for n in ["beat", "melody", "chords", "vocals"]],
            # Perfektes Gain-Staging: Viel Headroom für das Mastering, Instrumente leiser für Sprachverständlichkeit
            lautstaerken=[0.60, 0.25, 0.35, 1.0],
            output_pfad=os.path.join(OUTPUT_ORDNER, "final_mix.wav")
        )

        exportiere_song(
            wav_pfad=os.path.join(OUTPUT_ORDNER, "final_mix.wav"),
            mp3_pfad=os.path.join(OUTPUT_ORDNER, "final_song.mp3")
        )

        update_status_func("\n[OK] Song fertig! -> output/final_song.mp3")
        return True

    except Exception as e:
        import traceback
        update_status_func(f"\n[FEHLER] {e}")
        update_status_func(traceback.format_exc())
        return False
