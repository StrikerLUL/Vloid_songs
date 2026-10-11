# exporter.py
import logging
import os

log = logging.getLogger(__name__)

def exportiere_song(wav_pfad, mp3_pfad=None):
    """Exportiert den fertigen Mix als MP3. Gibt den MP3-Pfad zurück, oder None, wenn das nicht ging."""
    # Der finale Mix wurde bereits von Pedalboard professionell gemastert und limitiert.
    # Keine weitere Normalisierung nötig.
    log.info(f"WAV finalisiert: {wav_pfad}")
    if not mp3_pfad:
        return None

    try:
        from pydub import AudioSegment
        song = AudioSegment.from_wav(wav_pfad)
        song.export(mp3_pfad, format="mp3", bitrate="320k")
    except Exception as e:
        log.warning(f"MP3-Export übersprungen (ffmpeg fehlt?), der Song liegt als WAV vor: {e}")
        # pydub legt die Datei schon an, bevor ffmpeg scheitert
        if os.path.exists(mp3_pfad):
            os.remove(mp3_pfad)
        return None

    log.info(f"MP3 exportiert: {mp3_pfad}")
    return mp3_pfad
