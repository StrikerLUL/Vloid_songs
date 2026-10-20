# ai_melody.py – KI-Melodie (1.3.0, M7, Versuch)
#
# Der Anticipatory Music Transformer der KI-Begleitung (accompaniment.py) bekommt Akkorde, Bass und Schlagzeug des
# ersten Refrains als feste Vorgabe und schreibt TAKES Fassungen dazu. Aus jeder nimmt die App die Stimme, die am
# ehesten eine Melodie ist (einstimmig, in Singlage, die meisten Töne), rundet sie auf Sechzehntel, passt sie wie eine
# eigene Melodie an Silben und Stimmlage an (melody_import.fit) und bewertet sie mit den Punkten von M1
# (melody_score). Singt eine KI-Fassung besser als die komponierte, singen alle Refrains sie. Braucht die eingerichtete
# KI-Begleitung; ob es besser klingt, ist offen, deshalb ist der Schalter ab Werk aus.
import hashlib
import json
import logging
import os
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

RESULT_FILE = "ki_melodie.json"   # im Ausgabeordner: gleiche Vorgabe und gleicher Seed fragen das Modell nicht neu
VERSION = 1
TAKES = 4
KIND = "Chorus"
CHORD_PROGRAM = 48                # die Akkorde als Streicherfläche, so stehen sie in den Trainingsdaten oft
SINGABLE = (55, 84)               # in dieser Lage kann eine Stimme die Melodie des Modells singen
STEPS_PER_BEAT = 4


def window(plan) -> Optional[tuple]:
    """(Abschnitt, Anfang, Ende in Sekunden) des ersten Refrains mit Gesang; None ohne Refrain."""
    sec = next((s for s in plan.sections if s.kind == KIND and s.has_vocals), None) if plan else None
    if sec is None:
        return None
    spb = plan.seconds_per_beat
    return sec, sec.start * spb, sec.end * spb


def given_notes(tracks: dict) -> tuple:
    """Was das Modell im ersten Refrain hört: Akkorde (als Fläche), Bass, Bassdrum und Snare, in Sekunden ab dem
    Anfang des Refrains. Rückgabe (Töne, Länge in Sekunden); ([], 0) ohne Refrain."""
    import accompaniment
    plan = tracks.get("plan")
    found = window(plan)
    if found is None:
        return [], 0.0
    sec, start, end = found
    spb = plan.seconds_per_beat
    given = []
    for bar in range(sec.bars):
        beat = sec.start + bar * sec.bar_beats
        chord = plan.chord_at(beat)
        for pc in sorted(chord.pcs):
            pitch = 48 + chord.root + (pc - chord.root) % 12          # über dem Grundton, um C3 bis H4
            given.append([beat * spb - start, (beat + sec.bar_beats) * spb - start, pitch, CHORD_PROGRAM])
    given += [[n.start - start, n.end - start, n.pitch, accompaniment.BASS] for n in tracks.get("bass") or []
              if start <= n.start < end]
    given += [[n.start - start, n.end - start, n.pitch, accompaniment.DRUMS] for n in tracks.get("drums") or []
              if start <= n.start < end and n.pitch in accompaniment.GROOVE]
    return sorted([round(a, 3), round(min(b, end - start), 3), int(p), i] for a, b, p, i in given), end - start


def line(notes: list, spb: float) -> list:
    """Aus den Tönen einer Fassung des Modells die Melodie: die Stimme, die am meisten einstimmig in Singlage spielt,
    der höchste Ton je Sechzehntel. Rückgabe [(Schlag ab Refrain-Anfang, Dauer, Tonhöhe)] wie melody_import.load."""
    import accompaniment
    voices = {}
    for start, end, pitch, program in notes:
        if program in (accompaniment.BASS, accompaniment.DRUMS, CHORD_PROGRAM) or 32 <= program < 40 or end <= start:
            continue
        voices.setdefault(program, []).append((start, end, pitch))
    best, points = None, 0.0
    for program, played in voices.items():
        singable = [n for n in played if SINGABLE[0] <= n[2] <= SINGABLE[1]]
        onsets = {round(n[0] / spb * STEPS_PER_BEAT) for n in singable}
        value = len(onsets) * len(onsets) / max(1, len(singable))        # viele Einsätze, kaum Akkorde
        if value > points:
            best, points = program, value
    if best is None:
        return []
    highest = {}
    for start, end, pitch in voices[best]:
        step = round(start / spb * STEPS_PER_BEAT)
        if step >= 0 and (step not in highest or pitch > highest[step][1]):
            highest[step] = (max(1, round(end / spb * STEPS_PER_BEAT) - step), pitch)
    steps = sorted(highest)
    melody = []
    for i, step in enumerate(steps):
        length, pitch = highest[step]
        if i + 1 < len(steps):
            length = min(length, steps[i + 1] - step)
        melody.append((step / STEPS_PER_BEAT, length / STEPS_PER_BEAT, pitch))
    return melody


def suggest(tracks: dict, seed: int, out: str, reuse: bool = True) -> Optional[list]:
    """TAKES Melodien des Modells für den ersten Refrain; None ohne Modell, Refrain oder bei Fehlern."""
    import accompaniment
    given, seconds = given_notes(tracks)
    if not seconds:
        return None
    key = hashlib.sha1(json.dumps([VERSION, given, round(seconds, 2), seed, TAKES]).encode()).hexdigest()
    saved = os.path.join(out, RESULT_FILE)
    if reuse:
        try:
            with open(saved, encoding="utf-8") as f:
                old = json.load(f)
            if old.get("key") == key:
                log.info("KI-Melodie unverändert, nicht neu geschrieben")
                return old["takes"]
        except (OSError, ValueError, KeyError):
            pass
    if not accompaniment.available():
        return None
    with tempfile.TemporaryDirectory() as folder:
        result = os.path.join(folder, "melodie.json")
        found = accompaniment.run({"mode": "melody", "notes": given, "seconds": seconds, "seed": seed,
                                   "takes": TAKES, "output": result}, folder)
        if found is None:
            return None
        try:
            with open(result, encoding="utf-8") as f:
                takes = json.load(f)["takes"]
        except (OSError, ValueError, KeyError):
            return None
    os.makedirs(out, exist_ok=True)
    with open(saved, "w", encoding="utf-8") as f:
        json.dump({"key": key, "takes": takes}, f)
    return takes


def composed(tracks: dict, sec) -> list:
    """Die komponierte Melodie des Refrains als MelNotes (aus melody_data und silben)."""
    from melody_writer import MelNote
    out, t, i = [], 0.0, 0
    for pitch, dur in tracks.get("melody_data") or []:
        if pitch is not None:
            syllable = tracks["silben"][i] if i < len(tracks.get("silben", [])) else "ら"
            i += 1
            if sec.start - 1e-6 <= t < sec.end - 1e-6:
                out.append(MelNote(t, dur, int(pitch), syllable, strong=abs(t % 1) < 1e-6))
        t += dur
    return out


def choose(tracks: dict, takes: list) -> Optional[list]:
    """Die beste KI-Melodie (wie melody_import.load), wenn sie mehr Punkte bekommt als die komponierte; sonst None."""
    import melody_import
    import melody_score
    plan = tracks["plan"]
    sec = window(plan)[0]
    mine = composed(tracks, sec)
    syllables = [n.syllable for n in mine if not getattr(n.syllable, "melisma", False)] or ["ら"]
    before = [n for s in plan.sections if s.kind in ("Verse", "PreChorus") and s.occurrence == 1
              for n in composed(tracks, s)]
    top = plan.vocal_range[1]
    own = melody_score.score(mine, KIND, before, top, sec.bar_beats)
    best, points = None, own
    for k, notes in enumerate(takes):
        melody = [(b, d, p) for b, d, p in line(notes, plan.seconds_per_beat) if b < sec.beats]
        if len(melody) < 8:
            log.info("KI-Melodie %d: zu wenige Töne (%d)", k + 1, len(melody))
            continue
        fitted = melody_import.fit(melody, plan, sec, syllables)
        value = melody_score.score(fitted, KIND, before, top, sec.bar_beats)
        log.info("KI-Melodie %d: %d Töne, %.1f Punkte (komponiert %.1f)", k + 1, len(melody), value, own)
        if value > points:
            best, points = melody, value
    return best


def for_song(tracks: dict, seed: int, out: str, reuse: bool = True) -> Optional[list]:
    """Die Refrain-Melodie vom Modell, wenn eine Fassung besser singt als die komponierte; sonst None."""
    takes = suggest(tracks, seed, out, reuse)
    if not takes:
        return None
    melody = choose(tracks, takes)
    if melody is None:
        log.info("KI-Melodie: keine Fassung singt besser als die komponierte, die komponierte bleibt")
    else:
        log.info("KI-Melodie singt im Refrain (%d Töne)", len(melody))
    return melody
