# systemcheck.py – „System prüfen“: läuft jeder Baustein auf diesem Rechner wirklich?
#
# Jede Prüfung macht etwas Kleines echt (einen Takt Klavier rendern, zwei Töne mit NEUTRINO singen, einen Probeton
# bewerten, ...) und meldet grün, rot oder grau (nicht eingerichtet). Zum Schluss entsteht ein ganzer kurzer Song mit
# den aktuellen Einstellungen. Das Ergebnis liegt als systemcheck.json im Datenordner und kommt in den Fehlerbericht.
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Optional

import numpy as np
import soundfile as sf

import cancel
import config

log = logging.getLogger(__name__)

RESULT_FILE = "systemcheck.json"
FOLDER = "Systemcheck"            # im Datenordner: der kurze Probesong
MIN_FREE_GB = 5.0
# Immer nur eine Prüfung: Zwei gleichzeitige (z. B. „Prüfen“ in einem zweiten Fenster „System prüfen“) singen den
# Probesong in denselben Ordner und löschen sich gegenseitig die Gesangsdateien (Errno 2, „System error“).
_lock = threading.Lock()
_progress = [0.0, ""]             # wie weit die laufende Prüfung ist, für jedes Fenster „System prüfen“


class Busy(RuntimeError):
    """Es läuft schon eine Prüfung."""


@dataclass
class Check:
    key: str
    name: str
    ok: Optional[bool]            # None: nicht eingerichtet oder übersprungen
    message: str
    seconds: float = 0.0

    @property
    def symbol(self) -> str:
        return {True: "✓", False: "✗", None: "–"}[self.ok]


def result_path() -> str:
    return os.path.join(config.DATA_DIR, RESULT_FILE)


def _audible(path: str) -> bool:
    try:
        audio, _ = sf.read(path, dtype="float32", always_2d=True)
    except (RuntimeError, OSError):
        return False
    return bool(len(audio)) and float(np.max(np.abs(audio))) > 1e-3


def _tone(path: str, seconds: float = 3.0, rate: int = 44100) -> str:
    t = np.arange(int(seconds * rate)) / rate
    tone = 0.3 * np.sin(2 * np.pi * 440 * t) * np.minimum(1, t * 20)
    sf.write(path, np.stack([tone, tone], axis=1).astype(np.float32), rate)
    return path


# ── die einzelnen Prüfungen: jede gibt (ok, Meldung) zurück ────────────────────────
def check_space(settings, folder: str) -> tuple:
    from fehlerbericht import free_space
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        probe = os.path.join(config.DATA_DIR, ".schreibprobe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        return False, f"In den Datenordner {config.DATA_DIR} lässt sich nicht schreiben: {e}"
    free = shutil.disk_usage(config.DATA_DIR).free / 1e9
    text = f"{config.DATA_DIR}, {free_space(config.DATA_DIR)}"
    return (free >= MIN_FREE_GB), text if free >= MIN_FREE_GB else f"Wenig Platz: {text}"


def check_instruments(settings, folder: str) -> tuple:
    import pretty_midi

    from mixer import midi_zu_wav
    from renderer import engine_name
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    piano = pretty_midi.Instrument(program=0, name="piano")
    piano.notes += [pretty_midi.Note(90, p, i * 0.5, i * 0.5 + 0.45) for i, p in enumerate((60, 64, 67, 72))]
    midi.instruments.append(piano)
    mid, wav = os.path.join(folder, "klavier.mid"), os.path.join(folder, "klavier.wav")
    midi.write(mid)
    midi_zu_wav(mid, wav, instrument_type="piano", soundfont_pfad=settings.soundfont_file(),
                library=settings.sound_library and not settings.own_soundfont())
    if not _audible(wav):
        return False, "Ein Takt Klavier blieb still"
    return True, f"Ein Takt Klavier mit {engine_name()}"


def check_mp3(settings, folder: str) -> tuple:
    from exporter import exportiere_song
    mp3 = exportiere_song(_tone(os.path.join(folder, "ton.wav")), os.path.join(folder, "ton.mp3"))
    if not mp3 or not os.path.exists(mp3):
        return False, "MP3 geht nicht (ffmpeg fehlt?); die Songs liegen dann als WAV vor"
    return True, "MP3-Export klappt"


def check_video(settings, folder: str) -> tuple:
    import karaoke
    exe = karaoke.find_ffmpeg()
    return (True, f"ffmpeg gefunden: {exe}") if exe else (None, "ffmpeg fehlt: kein Lyric-Video (winget install "
                                                                  "Gyan.FFmpeg)")


def check_neutrino(settings, folder: str) -> tuple:
    from vocal_synthesizer import erstelle_musicxml, neutrino_info, neutrino_synthese, stimmlage
    neutrino_dir = settings.neutrino_dir()
    if not os.path.exists(os.path.join(neutrino_dir, "bin", "NEUTRINO.exe")):
        return None, f"NEUTRINO nicht gefunden ({neutrino_dir})"
    xml = erstelle_musicxml([(69, 1.0), (72, 1.0), (None, 1.0)], ["ら", "ら"], 120,
                            os.path.join(folder, "neutrino.xml"), stimmlage(settings.singer)[2])
    wav = os.path.join(folder, "neutrino.wav")
    started = time.monotonic()
    neutrino_synthese(xml, wav, neutrino_dir, os.path.join(neutrino_dir, "model", settings.singer))
    if not _audible(wav):
        return False, "NEUTRINO hat nur Stille gesungen"
    return True, f"{neutrino_info(neutrino_dir)}; zwei Töne mit {settings.singer} in " \
                 f"{time.monotonic() - started:.0f} s"


def check_voicevox(settings, folder: str) -> tuple:
    import voicevox
    url = settings.voicevox_url or voicevox.URL
    if not voicevox.running(url):
        return None, "VOICEVOX läuft nicht (nur nötig, wenn du damit singst)"
    singer, name = voicevox.pick_singer(url, settings.voicevox_singer)
    wav = voicevox.sing([(69, 1.0), (72, 1.0)], ["ら", "ら"], 120, os.path.join(folder, "voicevox.wav"), url, singer)
    return (True, f"VOICEVOX singt mit {name}") if _audible(wav) else (False, "VOICEVOX hat nur Stille gesungen")


def check_samples(settings, folder: str) -> tuple:
    import pretty_midi

    import sample_library
    have, total = len(sample_library.installed()), len(sample_library.files())
    if not have:
        return None, "Orchester-Aufnahmen nicht geladen"
    violin = pretty_midi.Instrument(program=40, name="strings")
    violin.notes.append(pretty_midi.Note(90, 67, 0.0, 1.0))
    if not sample_library.covers(violin):
        return False, f"{have} von {total} Instrumenten da, die Geige fehlt"
    audio = sample_library.render(violin)
    if audio is None or float(np.max(np.abs(audio))) < 1e-3:
        return False, "Die Geige aus den Aufnahmen blieb still"
    return (have == total), f"{have} von {total} Instrumenten da, die Geige spielt"


def check_band(settings, folder: str) -> tuple:
    import pretty_midi

    import band_library
    have = band_library.installed()
    if not have:
        return None, "Flügel, Bass und Gitarre aus Aufnahmen nicht geladen"
    for name in have:
        program = next(p for p, f in band_library.PROGRAMS.items() if f == name)
        inst = pretty_midi.Instrument(program=program, name=name)
        inst.notes.append(pretty_midi.Note(90, 45 if name == band_library.BASS else 60, 0.0, 1.0))
        audio = band_library.render(inst)
        if audio is None or float(np.max(np.abs(audio))) < 1e-3:
            return False, f"{band_library.NAMES[name]} aus den Aufnahmen blieb still"
    return len(have) == len(band_library.files()), band_library.status()


def check_drums(settings, folder: str) -> tuple:
    import pretty_midi

    import drum_kit
    if not drum_kit.installed():
        return None, "Echtes Schlagzeug nicht geladen"
    midi = pretty_midi.PrettyMIDI()
    kit = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    kit.notes = [pretty_midi.Note(100, pitch, k * 0.25, k * 0.25 + 0.1) for k, pitch in enumerate((36, 42, 38, 42))]
    midi.instruments.append(kit)
    audio, _ = drum_kit.render(midi)
    if audio is None or float(np.max(np.abs(audio))) < 1e-3:
        return False, "Das Schlagzeug aus den Aufnahmen blieb still"
    return drum_kit.complete(), drum_kit.status()


def check_grooves(settings, folder: str) -> tuple:
    import grooves
    if not grooves.installed():
        return None, "Echte Grooves nicht geladen"
    drummer = grooves.for_song(120, "systemcheck")
    if drummer is None or not drummer.plays("pop_verse"):
        return False, "Die Grooves lassen sich nicht lesen: unter Einrichten neu laden"
    return True, grooves.status()


def check_soundfonts(settings, folder: str) -> tuple:
    import sound_library
    have = sound_library.installed()
    return (True, sound_library.status()) if have else (None, "Zusätzliche SoundFonts nicht geladen")


def check_rating(settings, folder: str) -> tuple:
    import rating
    if not rating.available():
        return None, "Automatische Bewertung nicht eingerichtet"
    found = rating.rate([_tone(os.path.join(folder, "bewertung.wav"))])[0]
    return (True, f"Probeton bewertet: {found.describe()}") if found else (False, rating.problem())


def check_demucs(settings, folder: str) -> tuple:
    import separation
    if not separation.available():
        return None, "Mix wie die Vorbilder (Demucs) nicht eingerichtet"
    done = separation.separate([_tone(os.path.join(folder, "zerlegen.wav"))], [os.path.join(folder, "zerlegt")])
    return (True, "Probeton in Gesang, Schlagzeug, Bass und Rest zerlegt") if done else \
        (False, "Demucs lief nicht (Protokoll ansehen)")


def check_accompaniment(settings, folder: str) -> tuple:
    import accompaniment
    if not accompaniment.available():
        return None, "KI-Begleitung nicht eingerichtet"
    melody = [[0.5 * i, 0.5 * i + 0.4, 60 + 2 * (i % 4), accompaniment.MELODY] for i in range(16)]
    notes = accompaniment.write(melody, 8.0, 7, folder, reuse=False)
    if notes is None:
        return False, f"Das Modell lief nicht (Ausgabe in {os.path.join(accompaniment.FOLDER, accompaniment.LOG_FILE)})"
    return True, f"Acht Sekunden Begleitung mit {len(notes)} Tönen geschrieben"


def check_polish(settings, folder: str) -> tuple:
    import polish
    if not polish.available():
        return None, "Klang-Veredler nicht eingerichtet"
    found = polish.run({"probe": True}, folder)
    if not found or "cuda" not in found:
        return False, f"ACE-Step startet nicht (Ausgabe in {os.path.join(polish.FOLDER, polish.LOG_FILE)})"
    if not found["cuda"]:
        return False, "ACE-Step läuft, aber ohne Grafikkarte (sehr langsam)"
    return True, f"ACE-Step läuft auf {found.get('name', 'der Grafikkarte')}"


def check_pictures(settings, folder: str) -> tuple:
    import bilder
    if not bilder.available():
        return None, "KI-Bilder fürs Video nicht eingerichtet"
    found = bilder.probe(os.path.join(folder, "bilder"))
    return (True, f"Probebild gemalt: {found}") if found else (False, bilder.problem())


def check_hearing(settings, folder: str) -> tuple:
    import hoercheck
    if not hoercheck.available():
        return None, "Hör-Check nicht eingerichtet"
    return (True, "Spracherkennung läuft") if hoercheck.probe(os.path.join(folder, "hoercheck")) else \
        (False, hoercheck.problem())


def check_gpu(settings, folder: str) -> tuple:
    from fehlerbericht import gpu
    found = gpu()
    return (True, found) if not found.startswith(("keine", "nvidia-smi")) else (None, found)


def check_song(settings, folder: str) -> tuple:
    """Ein ganzer kurzer Song: zwei Takte Refrain mit den aktuellen Einstellungen, ohne Verlauf."""
    import pipeline
    target = os.path.join(config.DATA_DIR, FOLDER)
    os.makedirs(target, exist_ok=True)          # einen fehlenden Ausgabeordner ersetzen die Einstellungen durch den Standard
    short = settings.with_updates(output_ordner=target, active_sections=["Chorus"],
                                  section_bars={"Chorus": 2}, vocal_takes=1, polish=False, seed=7)
    started = time.monotonic()
    result = pipeline.generate_song(short, keep_history=False)
    seconds = time.monotonic() - started
    if not result.audio or not _audible(result.audio):
        return False, "Der kurze Song blieb still"
    sung = "mit Gesang" if result.vocals_wav else "ohne Gesang"
    return True, f"Zwei Takte Refrain {sung} in {seconds:.0f} s: {result.audio}"


CHECKS = (
    ("space", "Datenordner", check_space, False),
    ("gpu", "Grafikkarte", check_gpu, False),
    ("instruments", "Instrumente", check_instruments, False),
    ("soundfonts", "Bessere Klänge", check_soundfonts, False),
    ("samples", "Orchester-Aufnahmen", check_samples, False),
    ("band", "Flügel, Bass und Gitarre", check_band, False),
    ("drums", "Echtes Schlagzeug", check_drums, False),
    ("grooves", "Echte Grooves", check_grooves, False),
    ("mp3", "MP3-Export", check_mp3, False),
    ("video", "Lyric-Video", check_video, False),
    ("neutrino", "NEUTRINO", check_neutrino, False),
    ("voicevox", "VOICEVOX", check_voicevox, False),
    ("rating", "Automatische Bewertung", check_rating, False),
    ("demucs", "Mix wie die Vorbilder", check_demucs, False),
    ("accompaniment", "KI-Begleitung", check_accompaniment, True),    # lädt das Modell: nur bei „gründlich“
    ("polish", "Klang-Veredler", check_polish, True),         # lädt ACE-Step: nur bei „gründlich“
    ("pictures", "KI-Bilder fürs Video", check_pictures, True),     # lädt das Bildmodell: nur bei „gründlich“
    ("hearing", "Hör-Check", check_hearing, True),                  # lädt die Spracherkennung: nur bei „gründlich“
    ("song", "Ganzer Song", check_song, False),
)


def register(key: str, name: str, check: Callable, slow: bool = False, before: str = "song") -> None:
    """Weitere Prüfungen melden sich hier an (Tests, Erweiterungen), vor dem ganzen Song."""
    global CHECKS
    rest = [c for c in CHECKS if c[0] != key]
    at = next((i for i, c in enumerate(rest) if c[0] == before), len(rest))
    CHECKS = tuple(rest[:at] + [(key, name, check, slow)] + rest[at:])


def running() -> bool:
    return _lock.locked()


def current_step() -> tuple:
    """(Anteil, Schritt) der laufenden Prüfung."""
    return tuple(_progress)


def run_all(settings, progress: Optional[Callable[[float, str], None]] = None, thorough: bool = False,
            only: tuple = ()) -> list:
    """
    Alle Prüfungen nacheinander; eine fehlgeschlagene hält die anderen nicht auf. thorough: auch ACE-Step und
    KI-Begleitung. Läuft schon eine Prüfung, wirft sie Busy, statt eine zweite daneben zu starten.
    """
    if not _lock.acquire(blocking=False):
        raise Busy("Die Prüfung läuft schon")
    try:
        return _run_all(settings, progress, thorough, only)
    finally:
        _progress[:] = [0.0, ""]
        _lock.release()


def _run_all(settings, progress, thorough: bool, only: tuple) -> list:
    def report(fraction: float, message: str) -> None:
        _progress[:] = [fraction, message]
        if progress:
            progress(fraction, message)
    chosen = [c for c in CHECKS if (thorough or not c[3]) and (not only or c[0] in only)]
    results = []
    with tempfile.TemporaryDirectory() as folder:
        for i, (key, name, check, _) in enumerate(chosen):
            cancel.check()
            report(i / len(chosen), f"Prüfe {name}...")
            started = time.monotonic()
            try:
                ok, message = check(settings, folder)
            except cancel.Cancelled:
                raise
            except Exception as e:  # noqa: BLE001 – genau das soll die Prüfung zeigen
                log.warning("Systemcheck %s: %s", name, e, exc_info=True)
                ok, message = False, f"{type(e).__name__}: {e}"
            results.append(Check(key, name, ok, message, round(time.monotonic() - started, 1)))
            log.info("Systemcheck %s %s: %s", results[-1].symbol, name, message)
    report(1.0, "Fertig")
    save(results)
    return results


def save(results: list) -> None:
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(result_path(), "w", encoding="utf-8") as f:
            json.dump({"am": datetime.now().isoformat(timespec="seconds"),
                       "ergebnisse": [asdict(r) for r in results]}, f, indent=2, ensure_ascii=False)
    except OSError as e:
        log.warning("Ergebnis des Systemchecks nicht gespeichert: %s", e)


def load() -> Optional[tuple]:
    """(Zeitpunkt, [Check]) der letzten Prüfung, sonst None."""
    try:
        with open(result_path(), encoding="utf-8") as f:
            data = json.load(f)
        return datetime.fromisoformat(data["am"]), [Check(**r) for r in data["ergebnisse"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def summary(results: list) -> str:
    bad = [r.name for r in results if r.ok is False]
    missing = [r.name for r in results if r.ok is None]
    if bad:
        return f"{len(bad)} Problem{'e' if len(bad) > 1 else ''}: {', '.join(bad)}"
    text = "Alles läuft"
    return text + (f" (nicht eingerichtet: {', '.join(missing)})" if missing else "")
