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
