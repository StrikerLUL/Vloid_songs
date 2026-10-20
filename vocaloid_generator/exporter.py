# exporter.py
import io
import logging
import warnings

log = logging.getLogger(__name__)
# pydub 0.25.1 schreibt reguläre Ausdrücke ohne r"…"; Python 3.12 meldet das beim ersten Import nach jeder
# Installation als SyntaxWarning im Fenster. Am MP3-Export ändert das nichts.
warnings.filterwarnings("ignore", "invalid escape sequence", SyntaxWarning, r".*[\\/]pydub[\\/]")

def exportiere_song(wav_pfad, mp3_pfad=None):
    """Exportiert den fertigen Mix als MP3. Gibt den MP3-Pfad zurück, oder None, wenn das nicht ging."""
    # Der finale Mix wurde bereits von Pedalboard professionell gemastert und limitiert.
    # Keine weitere Normalisierung nötig.
    log.info(f"WAV finalisiert: {wav_pfad}")
    if not mp3_pfad:
        return None

    # Erst in den Speicher exportieren: pydub öffnet eine Zieldatei, bevor ffmpeg startet,
    # und lässt sie offen, wenn ffmpeg fehlt (unter Windows lässt sie sich dann nicht mehr löschen)
    buffer = io.BytesIO()
    try:
        from pydub import AudioSegment
        song = AudioSegment.from_wav(wav_pfad)
        song.export(buffer, format="mp3", bitrate="320k")
    except Exception as e:
        log.warning(f"MP3-Export übersprungen (ffmpeg fehlt?), der Song liegt als WAV vor: {e}")
        return None

    try:
        with open(mp3_pfad, "wb") as f:
            f.write(buffer.getvalue())
    except OSError as e:        # z. B. unter Windows: die alte MP3 ist gerade in einem Player offen
        log.warning(f"MP3 nicht geschrieben ({e}), der Song liegt als WAV vor")
        return None
    log.info(f"MP3 exportiert: {mp3_pfad}")
    return mp3_pfad


# Ordner in der ZIP-Datei; WAV und MP3 sind schon komprimiert und werden nur abgelegt
_ZIP_STORED = (".wav", ".mp3")


def exportiere_projekt(result, zip_pfad: str) -> str:
    """Packt den Song für eine DAW: Mix, jede Spur als WAV und MIDI, die Gesangsnoten (MusicXML für NEUTRINO,
    UST für OpenUtau) und die Einstellungen, mit denen derselbe Song wieder entsteht. result ist ein
    pipeline.SongResult."""
    import json
    import os
    import zipfile

    out = result.output_dir
    dateien = []
    for pfad in (result.mp3, result.mix_wav, getattr(result, "polished_mp3", None),
                 getattr(result, "polished_wav", None), *getattr(result, "versions", {}).values()):
        if pfad:
            dateien.append((pfad, os.path.basename(pfad)))
    dateien.append((os.path.join(out, "cover.png"), "cover.png"))
    for name, pfad in sorted(result.wav_files.items()):
        dateien.append((pfad, f"Spuren/{name}.wav"))
    for pfad in (result.vocals_wav, result.harmony_wav, getattr(result, "choir_wav", None)):
        if pfad:
            dateien.append((pfad, f"Spuren/{os.path.basename(pfad)}"))
    for name, pfad in sorted(result.midi_files.items()):
        dateien.append((pfad, f"MIDI/{name}.mid"))
    for name in ("vocal_melody.mid",):
        dateien.append((os.path.join(out, name), f"MIDI/{name}"))
    if result.vocals_wav:
        dateien.append((os.path.join(out, "vocals.xml"), "Gesang/vocals.xml"))
    if result.harmony_wav:
        dateien.append((os.path.join(out, "vocals_harmony.xml"), "Gesang/vocals_harmony.xml"))
    for name in ("vocals.ust", "vocals_harmony.ust", "vocals_duett_1.ust", "vocals_duett_2.ust"):
        dateien.append((os.path.join(out, name), f"Gesang/{name}"))

    os.makedirs(os.path.dirname(os.path.abspath(zip_pfad)), exist_ok=True)
    with zipfile.ZipFile(zip_pfad, "w") as z:
        for pfad, ziel in dateien:
            if pfad and os.path.exists(pfad):
                art = zipfile.ZIP_STORED if ziel.lower().endswith(_ZIP_STORED) else zipfile.ZIP_DEFLATED
                z.write(pfad, ziel, compress_type=art)
        s = result.settings
        if s is not None:
            z.writestr("einstellungen.json", json.dumps(s.model_dump(), indent=2, ensure_ascii=False),
                       compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("song.txt", _song_info(s), compress_type=zipfile.ZIP_DEFLATED)
    log.info("Projekt exportiert: %s", zip_pfad)
    return zip_pfad


def _song_info(s) -> str:
    rerolled = ", ".join(f"{teil} {n}x" for teil, n in sorted(s.variations.items())) or "nichts"
    return (
        f"Stil: {s.style}\n"
        f"Tempo: {s.bpm} BPM, 4/4\n"
        f"Tonart: {s.key} {s.scale}\n"
        f"Seed: {s.seed}\n"
        f"Neu gewürfelt: {rerolled}\n\n"
        "Alle MIDI- und WAV-Spuren starten bei 0:00 und lassen sich so in jede DAW ziehen.\n"
        "Mit einstellungen.json entsteht derselbe Song wieder: python main.py --settings einstellungen.json\n"
    )


NOTEN_LIESMICH = """Noten des Gesangs für Tuning-Tools

vocals.xml          MusicXML, genau so, wie NEUTRINO sie bekommt (ein Takt Vorlauf). Liest das NEUTRINO-Tuning-Tool,
                    VoiSona und MuseScore.
vocals_harmony.xml  die zweite Stimme im Refrain, wenn es eine gibt
*.ust               für OpenUtau (UTAU-Format)
vocal_melody.mid    die Melodie als MIDI, z. B. für Synthesizer V

Zurück in den Song: die gerenderte WAV in Vloid Songs unter Gesang, „Eigene Gesangsspur“ wählen und den Song neu
singen. Die App richtet die Spur an den Noten aus (der Vorlauftakt fällt weg) und mischt sie wie ihren eigenen Gesang;
die Begleitstimmen singt weiter NEUTRINO.
"""


def exportiere_noten(result, zip_pfad: str) -> str:
    """Die Noten des Gesangs für Tuning-Tools (Gesang 1.1, E2): MusicXML für NEUTRINO, UST, MIDI und eine kurze
    Anleitung, wie die bearbeitete Aufnahme zurück in den Song kommt."""
    import os
    import zipfile

    out = result.output_dir
    names = ("vocals.xml", "vocals_harmony.xml", "vocals.ust", "vocals_harmony.ust", "vocals_duett_1.ust",
             "vocals_duett_2.ust", "vocal_melody.mid")
    found = [n for n in names if os.path.exists(os.path.join(out, n))]
    if not found:
        raise FileNotFoundError("Der Song hat keine Gesangsnoten (Gesang ausgeschaltet?)")
    os.makedirs(os.path.dirname(os.path.abspath(zip_pfad)), exist_ok=True)
    with zipfile.ZipFile(zip_pfad, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in found:
            z.write(os.path.join(out, name), name)
        z.writestr("LIESMICH.txt", NOTEN_LIESMICH)
    log.info("Noten exportiert: %s (%s)", zip_pfad, ", ".join(found))
    return zip_pfad
