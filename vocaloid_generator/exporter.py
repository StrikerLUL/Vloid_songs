# exporter.py
import io
import logging

log = logging.getLogger(__name__)

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

    with open(mp3_pfad, "wb") as f:
        f.write(buffer.getvalue())
    log.info(f"MP3 exportiert: {mp3_pfad}")
    return mp3_pfad


# Ordner in der ZIP-Datei; WAV und MP3 sind schon komprimiert und werden nur abgelegt
_ZIP_STORED = (".wav", ".mp3")


def exportiere_projekt(result, zip_pfad: str) -> str:
    """Packt den Song für eine DAW: Mix, jede Spur als WAV und MIDI, die Gesangsnoten (MusicXML) und die
    Einstellungen, mit denen derselbe Song wieder entsteht. result ist ein pipeline.SongResult."""
    import json
    import os
    import zipfile

    out = result.output_dir
    dateien = []
    for pfad in (result.mp3, result.mix_wav):
        if pfad:
            dateien.append((pfad, os.path.basename(pfad)))
    for name, pfad in sorted(result.wav_files.items()):
        dateien.append((pfad, f"Spuren/{name}.wav"))
    for pfad in (result.vocals_wav, result.harmony_wav):
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
