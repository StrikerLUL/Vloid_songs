# chorus_lift.py – Refrains steigern sich (1.5.0, S5)
#
# Bis 1.4 klingen alle Refrains gleich voll: „Aufbau in der Sektion“ (buildup.py) gibt jeder zweiten Refrain-Hälfte
# eine Oktave dazu, die Bewegung im Mix (mix_movement.py) macht jeden Refrain gleich breit. Was fehlte, ist der Weg
# vom ersten zum letzten Refrain: Jetzt ist der erste schlanker (ohne Antwort-Melodie und Glocken in der ersten Hälfte,
# ohne Oktav-Schicht), die mittleren bleiben, wie sie sind, und der letzte spielt mit allem: die Oktave über den ganzen
# Refrain in bis zu zwei Instrumenten und ein Becken zu jedem vierten Takt.
from drums import CRASH, _vel
from parts import Ev
from song_plan import BEATS_PER_BAR

LEAN = ("counter", "bells")              # spielen im ersten Refrain erst ab der Hälfte
LAYERS = ("strings", "synth", "piano")   # wer im letzten Refrain die Oktave dazu spielt
MAX_LAYERS = 2
LAYER_VEL = 0.5
TOP = 100
CRASH_BARS = 4


def _in(e, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def apply(plan, events: dict) -> dict:
    """Rückgabe: {"lean": Anfang des schlankeren ersten Refrains oder None, "full": Anfang des vollen letzten}."""
    done = {"lean": None, "full": None, "layers": []}
    choruses = [s for s in plan.sections if s.kind == "Chorus" and s.bars >= 4]
    if len(choruses) < 2:
        return done
    first, last = choruses[0], choruses[-1]
    half = first.start + (first.bars // 2) * BEATS_PER_BAR
    removed = 0
    for inst in LEAN:
        evs = events.get(inst)
        if evs:
            before = len(evs)
            evs[:] = [e for e in evs if not _in(e, first.start, half)]
            removed += before - len(evs)
    for inst in LAYERS:
        evs = events.get(inst)
        if evs:
            before = len(evs)
            evs[:] = [e for e in evs if not (_in(e, first.start, first.end) and e.layer == "octave")]
            removed += before - len(evs)
    if removed:
        done["lean"] = first.start
    if last.feel == "breakdown":
        return done
    # der letzte Refrain: Oktave von Anfang an (was buildup.py ab der Hälfte schon dazugibt, bleibt)
    for inst in LAYERS:
        mine = [e for e in events.get(inst, ()) if _in(e, last.start, last.end) and not e.layer]
        if not mine:
            continue
        have = {(round(e.start, 4), e.pitch) for e in events[inst] if e.layer == "octave"}
        events[inst] += [Ev(e.start, e.dur, e.pitch + 12, max(1, round(e.vel * LAYER_VEL)), "octave")
                         for e in mine if e.pitch + 12 <= TOP and (round(e.start, 4), e.pitch + 12) not in have]
        done["layers"].append(inst)
        if len(done["layers"]) >= MAX_LAYERS:
            break
    drums = events.setdefault("drums", [])
    for bar in range(0, last.bars, CRASH_BARS):
        at = last.start + bar * BEATS_PER_BAR
        if not any(abs(e.start - at) < 0.05 and e.pitch == CRASH for e in drums):
            drums.append(Ev(at, 1.0, CRASH, _vel(last.energy, 0.8)))
    done["full"] = last.start
    return done
