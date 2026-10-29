# media.py – Daten für Player und Piano-Roll: Wellenform, Noten der Spuren, Spuren zum Solo-Hören
import logging
import os
import subprocess
import sys
from typing import Optional

import numpy as np

from gui import labels

log = logging.getLogger(__name__)

PEAKS = 3000                  # Balken der Wellenform; wavesurfer rechnet sie auf die Fensterbreite um
ROLL_TRACKS = ("vocals", "melody", "counter", "piano", "guitar", "synth", "strings", "brass", "bells", "choir",
               "bass")        # Schlagzeug und Percussion haben keine Tonhöhe und fehlen in der Piano-Roll


def peaks(path: str, count: int = PEAKS) -> tuple:
    """(Spitzenwerte 0..1, Dauer in Sekunden) einer WAV oder MP3, damit der Browser die Datei nicht selbst
    dekodieren muss."""
    try:
        import soundfile as sf
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
    except Exception as e:
        log.warning("Wellenform von %s nicht lesbar: %s", path, e)
        return [], 0.0
    mono = np.abs(audio).max(axis=1)
    duration = len(mono) / rate
    if not len(mono):
        return [], duration
    blocks = np.array_split(mono, min(count, len(mono)))
    values = np.array([b.max() for b in blocks])
    top = values.max() or 1.0
    return [round(float(v), 3) for v in values / top], round(duration, 3)


def stems(result) -> dict:
    """Was sich im Player anhören lässt: {Name: Pfad}, der Mix zuerst."""
    found = {}
    if result is None:
        return found
    mix = result.audio
    if mix and os.path.exists(mix):
        found["Mix"] = mix
    polished = getattr(result, "polished_mp3", None) or getattr(result, "polished_wav", None)
    if polished and os.path.exists(polished):
        found["Veredelt (ACE-Step)"] = polished
    for kind, name in (("offvocal", "Off-Vocal (ohne Gesang)"), ("acappella", "A-cappella (nur Gesang)")):
        path = getattr(result, "versions", {}).get(kind)
        if path and os.path.exists(path):
            found[name] = path
    if result.vocals_wav and os.path.exists(result.vocals_wav):
        found[labels.CHANNELS["vocals"]] = result.vocals_wav
    if result.harmony_wav and os.path.exists(result.harmony_wav):
        found["Zweite Stimme"] = result.harmony_wav
    if getattr(result, "choir_wav", None) and os.path.exists(result.choir_wav):
        found["Chor im letzten Refrain"] = result.choir_wav
    for inst, path in result.wav_files.items():
        if os.path.exists(path):
            found[labels.CHANNELS.get(inst, inst)] = path
    return found


def piano_roll(result) -> dict:
    """Noten aller Spuren mit Tonhöhe für die Piano-Roll: {"notes": [[start, ende, tonhöhe, spur]], "tracks":
    [{"name", "color"}], "duration"}. Die Gesangsmelodie steht als eigene Spur ganz vorn."""
    import pretty_midi

    data = {"notes": [], "tracks": [], "duration": 0.0}
    if result is None:
        return data
    files = dict(result.midi_files)
    vocal = os.path.join(result.output_dir, "vocal_melody.mid")
    if os.path.exists(vocal):
        files["vocals"] = vocal
    for inst in ROLL_TRACKS:
        path = files.get(inst)
        if not path or not os.path.exists(path):
            continue
        try:
            midi = pretty_midi.PrettyMIDI(path)
        except Exception as e:
            log.warning("MIDI %s nicht lesbar: %s", path, e)
            continue
        notes = [n for i in midi.instruments if not i.is_drum for n in i.notes]
        if not notes:
            continue
        index = len(data["tracks"])
        data["tracks"].append({"key": inst, "name": labels.CHANNELS.get(inst, inst),
                               "color": labels.COLORS.get(inst, "#90a4ae")})
        data["notes"] += [[round(n.start, 3), round(n.end, 3), n.pitch, index] for n in notes]
    if data["notes"]:
        data["duration"] = max(n[1] for n in data["notes"])
    if result.settings is not None:
        data["step"] = 60.0 / result.settings.bpm / 4       # ein Sechzehntel: so fein ändert sich die Länge
    return data


def phrase_at(result, t: float) -> Optional[tuple]:
    """(Anfang, Ende) in Sekunden der gesungenen Phrase, in der die Zeit t liegt; None ohne Gesang dort."""
    import pretty_midi

    import voice_fx
    path = os.path.join(result.output_dir, "vocal_melody.mid") if result is not None else ""
    if not os.path.exists(path):
        return None
    midi = pretty_midi.PrettyMIDI(path)
    notes = sorted((voice_fx.SungNote(n.start, n.end, n.pitch) for i in midi.instruments for n in i.notes),
                   key=lambda n: n.start)
    for group in voice_fx.phrases(notes):
        if group[0].start - 0.05 <= t <= group[-1].end + 0.05:
            return group[0].start, group[-1].end
    return None


def lyrics(result) -> list:
    """Die Zeilen zum Mitlesen (karaoke.lines) des Songs; leer ohne Gesang."""
    import karaoke
    if result is None:
        return []
    return karaoke.load(os.path.join(result.output_dir, karaoke.FILE))


def sung_by(result) -> tuple:
    """(Zeile unter dem Player, Warnung?): wer den Gesang gesungen hat (vocal_check)."""
    import vocal_check
    if result is None or not result.vocals_wav:
        return "", False
    return vocal_check.describe(vocal_check.read(result.output_dir))


def hearing(result) -> tuple:
    """(Zeile unter dem Player, Warnung?): was der Hör-Check verstanden hat (hoercheck.py, 1.5.0)."""
    import hoercheck
    if result is None or not result.vocals_wav:
        return "", False
    return hoercheck.describe(hoercheck.load(result.output_dir))


def open_folder(path: str) -> bool:
    """Öffnet einen Ordner im Explorer (oder im Dateimanager), oder eine Datei mit ihrem Programm."""
    if not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except OSError as e:
        log.warning("Ordner %s lässt sich nicht öffnen: %s", path, e)
        return False
