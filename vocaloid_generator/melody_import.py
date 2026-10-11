# melody_import.py – Eine eigene Melodie aus einer MIDI-Datei singen lassen
#
# Die Melodie kommt aus einer DAW, einem Notenprogramm oder einem Keyboard. Sie ersetzt die komponierte Melodie
# einer Sektionsart (meist den Refrain); Akkorde, Band und Text bleiben, wie sie sind.
import logging
import math

import pretty_midi

from melody_writer import KIND_OFFSET, MelNote
from song_plan import BEATS_PER_BAR, Section, SongPlan

log = logging.getLogger(__name__)

STEPS_PER_BEAT = 4      # gerundet wird auf Sechzehntel
MAX_BARS = 16           # längere Melodien werden abgeschnitten


def load(path: str) -> list:
    """
    Die Melodie einer MIDI-Datei: die Spur mit den meisten Tönen (ohne Schlagzeug), auf Sechzehntel gerundet,
    einstimmig (bei Akkorden zählt der höchste Ton) und so verschoben, dass sie im ersten Takt beginnt.
    Rückgabe [(Schlag, Dauer, Tonhöhe)]. Wirft ValueError, wenn die Datei keine Melodie enthält.
    """
    try:
        pm = pretty_midi.PrettyMIDI(path)
    except Exception as e:  # noqa: BLE001 – mido wirft je nach Schaden OSError, EOFError, KeyError, ValueError ...
        raise ValueError(f"MIDI-Datei nicht lesbar ({e})") from e
    tracks = [inst for inst in pm.instruments if not inst.is_drum and inst.notes]
    if not tracks:
        raise ValueError("Die MIDI-Datei enthält keine Melodie")
    track = max(tracks, key=lambda inst: len(inst.notes))

    def beat(seconds: float) -> float:
        return round(pm.time_to_tick(seconds) / pm.resolution * STEPS_PER_BEAT) / STEPS_PER_BEAT

    highest = {}
    for n in track.notes:
        start = beat(n.start)
        if start not in highest or n.pitch > highest[start][1]:
            highest[start] = (max(beat(n.end), start + 1 / STEPS_PER_BEAT), n.pitch)
    starts = sorted(highest)
    offset = math.floor(starts[0] / BEATS_PER_BAR) * BEATS_PER_BAR
    limit = MAX_BARS * BEATS_PER_BAR
    melody = []
    for i, start in enumerate(starts):
        end, pitch = highest[start]
        if i + 1 < len(starts):
            end = min(end, starts[i + 1])
        if start - offset >= limit:
            log.warning("Eigene Melodie länger als %d Takte, der Rest fällt weg", MAX_BARS)
            break
        melody.append((start - offset, min(end, offset + limit) - start, pitch))
    return melody


def imported_bars(melody: list) -> int:
    """Takte, die die Melodie braucht (1, 2, 4, 8 oder 16); 0 ohne Melodie."""
    if not melody:
        return 0
    end = max(start + dur for start, dur, _ in melody)
    bars = 1
    while bars * BEATS_PER_BAR < end - 1e-6:
        bars *= 2
    return bars


def fit(melody: list, plan: SongPlan, sec: Section, syllables: list) -> list:
    """
    Die eigene Melodie in einer Sektion: so oft wiederholt, wie die Sektion lang ist, in ganzen Oktaven in die
    Stimmlage gerückt (im höheren Schlussrefrain mit der Tonart) und Ton für Ton mit dem Text belegt. Hat die
    Melodie mehr Töne als der Text Silben, beginnt der Text von vorn.
    """
    length = imported_bars(melody) * BEATS_PER_BAR
    shift = (sec.tonic - plan.tonic + 6) % 12 - 6
    pitches = sorted(p + shift for _, _, p in melody)
    lo, hi = plan.vocal_range
    center = plan.style.vocal_center + KIND_OFFSET.get(sec.kind, 0)
    octave = round((center - pitches[len(pitches) // 2]) / 12) * 12
    if pitches[-1] + octave > hi + 2:
        octave -= 12
    elif pitches[0] + octave < lo - 2:
        octave += 12
    syllables = list(syllables) or ["ら"]
    notes = []
    for rep in range(math.ceil(sec.beats / length)):
        for start, dur, pitch in melody:
            beat = sec.start + rep * length + start
            if beat >= sec.end:
                break
            notes.append(MelNote(beat, min(dur, sec.end - beat), pitch + shift + octave,
                                 syllables[len(notes) % len(syllables)], strong=start % 1 == 0))
    if len(notes) < len(syllables):
        log.info("Eigene Melodie in %s: %d Töne für %d Silben, der Rest des Texts entfällt",
                 sec.kind, len(notes), len(syllables))
    return notes
