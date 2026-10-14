# accompaniment.py – KI-Begleitung (Versuch): der Anticipatory Music Transformer schreibt die Begleitstimmen
#
# Das Modell (Stanford CRFM, Apache 2.0, trainiert auf dem Lakh MIDI Dataset) bekommt Gesangsmelodie, Bass sowie
# Bassdrum und Snare des Songs als feste Vorgabe und schreibt dazu, was es für passend hält: Klavier, Gitarre,
# Streicher, Synths, Bläser. Diese Töne ersetzen die komponierten Begleitstimmen; Melodie, Bass, Schlagzeug und Gesang
# bleiben. Es läuft in einer eigenen Umgebung (setup_begleitung.py, tools/begleitung) wie die Bewertung. Ob es besser
# klingt als die eingebaute Begleitung, ist offen; deshalb ist der Schalter ab Werk aus.
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from typing import Optional

import cancel
import config

log = logging.getLogger(__name__)

FOLDER = os.path.join(config.REPO_ROOT, "tools", "begleitung")
WORKER = os.path.join(config.BASE_DIR, "accompaniment_worker.py")
MARKER = "BEGLEITET "
LOG_FILE = "letzter_lauf.log"   # was das Modell beim letzten Mal ausgegeben hat, zum Nachlesen bei Fehlern
RESULT_FILE = "begleitung.json"  # im Ausgabeordner: gleiche Vorgabe und gleicher Seed schreiben nicht neu
TIMEOUT = 7200                  # Sekunden; ohne Grafikkarte schreibt das kleine Modell lange
VERSION = 1
MELODY, BASS, DRUMS = 53, 33, 128           # so stehen Gesang (Voice Oohs), Bass und Schlagzeug in den Trainingsdaten
GROOVE = (35, 36, 37, 38, 40)               # vom Schlagzeug nur Bassdrum und Snare: der Rest füllt bloß das Gedächtnis
# Diese Kanäle schreibt das Modell neu; was es dort nicht spielt, bleibt still
REPLACED = ("piano", "guitar", "strings", "synth", "brass", "bells", "choir", "counter")
NAMES = {"piano": "Klavier", "guitar": "Gitarre", "strings": "Streicher", "synth": "Synth", "brass": "Bläser",
         "bells": "Glocken", "choir": "Chor", "counter": "Gegenstimme"}


def python() -> str:
    """Python der eigenen Umgebung."""
    if sys.platform == "win32":
        return os.path.join(FOLDER, "venv", "Scripts", "python.exe")
    return os.path.join(FOLDER, "venv", "bin", "python")


def available() -> bool:
    return os.path.isfile(python())


def status() -> str:
    if not available():
        return "KI-Begleitung fehlt: unter Hilfe › Einrichten „KI-Begleitung“ laden"
    return "KI-Begleitung ist eingerichtet"


def environment() -> dict:
    """Das Modell liegt mit in tools/begleitung, nicht irgendwo im Profil."""
    return {**os.environ, "HF_HOME": os.path.join(FOLDER, "hf"), "PYTHONIOENCODING": "utf-8"}


def channel_for(program: int) -> Optional[str]:
    """Der Kanal der App für ein GM-Programm des Modells; None für Bass, Schlagzeug, Gesang und Geräusche."""
    if program < 8:
        return "piano"
    if program < 16:
        return "bells"
    if program < 24:
        return "synth"                          # Orgeln
    if program < 32 or 104 <= program < 112:
        return "guitar"                         # auch Sitar, Banjo, Koto
    if program < 40 or program == MELODY or program >= 112:
        return None
    if program in (52, 54):
        return "choir"
    if program < 56:
        return "strings"
    if program < 64:
        return "brass"
    if program < 80:
        return "counter"                        # Holzbläser und Flöten
    return "synth"


def given_notes(tracks: dict) -> list:
    """Was das Modell nicht ändern darf: [[Start, Ende, Tonhöhe, Instrument], ...] in Sekunden."""
    given = [[n.start, n.end, n.pitch, MELODY] for n in tracks.get("vocal_melody") or []]
    given += [[n.start, n.end, n.pitch, BASS] for n in tracks.get("bass") or []]
    given += [[n.start, n.end, n.pitch, DRUMS] for n in tracks.get("drums") or [] if n.pitch in GROOVE]
    return sorted([round(a, 3), round(b, 3), int(p), i] for a, b, p, i in given)


def run(job: dict, folder: str) -> Optional[dict]:
    """Ein Auftrag an das Modell; die Antwort (Gerät, Modell, Zahl der Töne) oder None (Meldung im Log)."""
    path = os.path.join(folder, "auftrag.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    os.makedirs(FOLDER, exist_ok=True)
    log_path = os.path.join(FOLDER, LOG_FILE)
    try:
        # Ausgabe in eine Datei statt in Pipes (wie beim Klang-Veredler); -P: die App gehört nicht auf den Suchpfad
        with open(log_path, "w", encoding="utf-8") as output:
            done = cancel.run([python(), "-P", WORKER, path], stdin=subprocess.DEVNULL, stdout=output,
                              stderr=subprocess.STDOUT, timeout=TIMEOUT, env=environment(), creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("KI-Begleitung fehlgeschlagen: %s", e)
        return None
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    line = next((ln for ln in reversed(text.splitlines()) if ln.startswith(MARKER)), None)
    if done.returncode != 0 or line is None:
        log.warning("KI-Begleitung fehlgeschlagen (ganze Ausgabe in %s): %s", log_path, text.strip()[-800:])
        return None
    try:
        found = json.loads(line[len(MARKER):])
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def write(given: list, seconds: float, seed: int, out: str, reuse: bool = True) -> Optional[list]:
    """Die Töne der Begleitung, [[Start, Ende, Tonhöhe, Programm], ...]; None ohne Modell oder bei Fehlern."""
    key = hashlib.sha1(json.dumps([VERSION, given, round(seconds, 2), seed]).encode()).hexdigest()
    saved = os.path.join(out, RESULT_FILE)
    if reuse:
        try:
            with open(saved, encoding="utf-8") as f:
                old = json.load(f)
            if old.get("key") == key:
                log.info("KI-Begleitung unverändert, nicht neu geschrieben")
                return old["notes"]
        except (OSError, ValueError, KeyError):
            pass
    if not available():
        return None
    with tempfile.TemporaryDirectory() as folder:
        result = os.path.join(folder, "begleitung.json")
        found = run({"notes": given, "seconds": seconds, "seed": seed, "output": result}, folder)
        if found is None:
            return None
        try:
            with open(result, encoding="utf-8") as f:
                notes = json.load(f)["notes"]
        except (OSError, ValueError, KeyError):
            return None
    log.info("KI-Begleitung: %d Töne vom Modell %s auf %s", len(notes), found.get("model", "?"),
             "der Grafikkarte" if found.get("device") == "cuda" else "dem Prozessor")
    with open(saved, "w", encoding="utf-8") as f:
        json.dump({"key": key, "notes": notes}, f)
    return notes


def velocity(start: float, sections: list) -> int:
    """Lauter, wo der Song Energie hat: das Modell kennt keine Anschlagstärke."""
    energy = next((e for a, b, e in sections if a <= start < b), 0.7)
    return int(round(56 + 40 * min(max(energy, 0.0), 1.0)))


def apply(notes: list, tracks: dict, out: str, bpm: float, sections: list = ()) -> dict:
    """Ersetzt die Begleitstimmen durch die Töne des Modells: neue MIDI-Dateien und tracks; {Kanal: Zahl der Töne}."""
    import pretty_midi
    parts = defaultdict(lambda: defaultdict(list))         # Kanal → Programm → Töne
    for start, end, pitch, program in notes:
        channel = channel_for(program)
        if channel and 0 <= pitch < 128 and end > start:
            parts[channel][program].append(pretty_midi.Note(velocity=velocity(start, sections), pitch=pitch,
                                                             start=start, end=end))
    counts = {}
    for channel in REPLACED:
        path = os.path.join(out, f"{channel}.mid")
        if channel not in parts:
            tracks[channel] = []
            if os.path.exists(path):
                os.remove(path)
            continue
        midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        for program, played in sorted(parts[channel].items()):
            track = pretty_midi.Instrument(program=program, name=f"KI {NAMES[channel]}")
            track.notes = sorted(played, key=lambda n: (n.start, n.pitch))
            midi.instruments.append(track)
        midi.write(path)
        tracks[channel] = sorted((n for t in midi.instruments for n in t.notes), key=lambda n: (n.start, n.pitch))
        counts[channel] = len(tracks[channel])
    return counts


def accompany(tracks: dict, out: str, bpm: float, seed: int, sections: list = (), reuse: bool = True) -> bool:
    """Die KI-Begleitung für den Song in tracks; False (alles bleibt, wie es ist) ohne Modell, Melodie oder bei Fehlern."""
    plan = tracks.get("plan")
    given = given_notes(tracks)
    if plan is None or not any(i == MELODY for *_, i in given):
        return False
    notes = write(given, plan.total_beats * 60.0 / bpm, seed, out, reuse)
    if not notes:
        return False
    if not any(channel_for(program) for *_, program in notes):
        log.warning("Die KI-Begleitung spielt nichts, was die App spielen kann; die komponierte bleibt.")
        return False
    counts = apply(notes, tracks, out, bpm, sections)
    log.info("KI-Begleitung: %s", ", ".join(f"{NAMES[c]} {n} Töne" for c, n in counts.items()))
    return True
