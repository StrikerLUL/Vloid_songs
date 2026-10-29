# anison.py – Anison-Grooves (1.3.0, I6)
#
# Schnelle Anime-Openings treiben mit eigenen Grooves: der 2-Beat (Bassdrum auf jedem Schlag, Snare auf jedem „und“),
# Disco-Hi-Hats (offen auf dem „und“), ein Tom-Groove in der ersten Strophe statt der Hi-Hats, ein Snare-Wirbel als
# Anlauf in den Refrain, wo die Strophe ohne Pre-Chorus hineinführt (der Pre-Chorus hat seinen eigenen), und
# Becken-Stopps am Ende eines Refrains: Becken und Bassdrum auf der Eins, Becken abgestoppt, und die Band holt auf der
# Vier mit zwei Schlägen Luft. Die eingebauten Grooves der Stile bleiben, wo kein Anison-Groove passt. Die Muster
# stehen bei den anderen in drums.GROOVES.
import random

from drums import CRASH, KICK, SNARE, _vel
from parts import Ev
from song_plan import BEATS_PER_BAR

STYLES = ("J-Pop Energy", "Rock", "Idol-Pop", "Dark Vocaloid", "Kawaii Chiptune", "Wafuu-Rock")
MIN_BPM = 140               # langsamer treibt kein 2-Beat
TWO_BEAT_SHARE, DISCO_SHARE, TOM_SHARE, STOP_SHARE, ROLL_SHARE = 0.5, 0.5, 0.5, 0.5, 0.6


def plays(style: str, bpm: float) -> bool:
    return style in STYLES and bpm >= MIN_BPM


def groove_for(sec, style: str, bpm: float, groove: str, label: str) -> str:
    """Der Groove der Sektion: ein Anison-Groove, wo er passt, sonst der des Stils. Gleiche Sektionen gleich."""
    if not groove or not plays(style, bpm) or groove in ("build", "halftime") or sec.feel:
        return groove
    rng = random.Random(f"{label}:anison:{sec.kind}")
    if sec.kind == "Chorus" and rng.random() < TWO_BEAT_SHARE:
        return "two_beat"
    if sec.kind == "PreChorus" and rng.random() < DISCO_SHARE:
        return "disco"
    if sec.kind == "Verse" and sec.occurrence == 1 and rng.random() < TOM_SHARE:
        return "tom_verse"
    return groove


def apply(plan, events: dict, style: str, bpm: float, label: str) -> dict:
    """Snare-Wirbel als Anlauf und Becken-Stopps. Rückgabe: Takte, zum Nachsehen."""
    done = {"rolls": [], "stops": []}
    if not plays(style, bpm):
        return done
    drums = events["drums"]
    for sec in plan.sections:
        rng = random.Random(f"{label}:anison-fx:{sec.kind}:{sec.occurrence}")
        last_bar = sec.end - BEATS_PER_BAR
        if sec.next_kind == "Chorus" and sec.kind in ("Verse", "Bridge", "Interlude") and rng.random() < ROLL_SHARE:
            start = sec.end - 2.0          # Wirbel auf den letzten zwei Schlägen, immer dichter und lauter
            _clear(drums, start, sec.end, keep=(KICK,))
            drums += [Ev(start + k / 8, 0.1, SNARE, _vel(sec.energy, 0.45 + 0.5 * k / 15)) for k in range(16)]
            done["rolls"].append(last_bar)
        elif sec.kind == "Chorus" and sec.next_kind not in (None, "Outro", "Chorus") and rng.random() < STOP_SHARE:
            _clear(drums, last_bar, sec.end)
            drums += [Ev(last_bar, 0.3, CRASH, _vel(sec.energy, 0.95)), Ev(last_bar, 0.2, KICK, _vel(sec.energy, 1.0)),
                      Ev(last_bar + 3.0, 0.3, CRASH, _vel(sec.energy, 0.85)),
                      Ev(last_bar + 3.0, 0.2, KICK, _vel(sec.energy, 0.95)),
                      Ev(last_bar + 3.5, 0.2, SNARE, _vel(sec.energy, 0.8)),
                      Ev(last_bar + 3.75, 0.2, SNARE, _vel(sec.energy, 0.9))]
            for inst, evs in events.items():
                if inst in ("drums", "melody") or not evs:
                    continue
                for e in evs:          # die Band klingt auf der Eins kurz an und schweigt bis zur Vier
                    if abs(e.start - last_bar) < 0.05:
                        e.dur = min(e.dur, 0.5)
                evs[:] = [e for e in evs if not (last_bar + 0.05 <= e.start < last_bar + 3.0)]
            done["stops"].append(last_bar)
    return done


def _clear(drums: list, start: float, end: float, keep: tuple = ()) -> None:
    drums[:] = [e for e in drums if not (start - 1e-6 <= e.start < end - 1e-6) or e.pitch in keep]
