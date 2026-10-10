# exporter.py
import logging
import shutil

log = logging.getLogger(__name__)

def exportiere_song(wav_pfad, mp3_pfad=None):
    try:
        # Der finale Mix wurde bereits von Pedalboard professionell gemastert und limitiert.
        # Keine weitere Normalisierung nötig.
        log.info(f"WAV finalisiert: {wav_pfad}")
        
        # Optional: MP3 exportieren (sofern ffmpeg/pydub verfügbar)
        if mp3_pfad:
            try:
                from pydub import AudioSegment
                song = AudioSegment.from_wav(wav_pfad)
                song.export(mp3_pfad, format="mp3", bitrate="320k")
                log.info(f"MP3 exportiert: {mp3_pfad}")
            except Exception as e:
                log.info(f"MP3 Export übersprungen (Pydub/ffmpeg fehlt): {e}")
    except Exception as e:
        log.info(f"Fehler beim Exportieren: {e}")
