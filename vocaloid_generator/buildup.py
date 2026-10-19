# buildup.py – Aufbau innerhalb der Sektion (1.3.0, I7)
#
# Bis 1.2 spielt die Band eine Sektion vom ersten bis zum letzten Takt gleich voll. Jetzt beginnt die erste Strophe
# nur mit Klavier oder Gitarre und dem Gesang; nach vier Takten kommen Bass und Schlagzeug dazu (mit kurzem Fill und
# Becken), dann der Rest. In der zweiten Hälfte jedes Refrains spielt eine Schicht mehr: die Streicher (oder der Synth,
# oder das Klavier) eine Oktave höher dazu, leiser, und das Schlagzeug setzt dort mit einem Becken ein.
from drums import CRASH, KICK, SNARE, _vel
from parts import Ev
from song_plan import BEATS_PER_BAR

ALONE = ("piano", "guitar")              # wer die Strophe allein beginnt (der erste, der dort spielt)
WAIT_BARS = 4                            # so lange spielt er allein
MIN_BARS = 8                             # kürzere Strophen bauen nicht auf
SILENT_FIRST = ("bass", "drums", "perc", "synth", "strings", "brass", "bells", "counter", "choir", "melody")
LAYERS = ("strings", "synth", "piano")   # wer im Refrain die Oktave dazu spielt
LAYER_VEL = 0.55
TOP = 100


def _in(e, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def apply(plan, events: dict) -> dict:
    """Rückgabe: {"verse": Anfang der allein begonnenen Strophe oder None, "choruses": [Anfänge der Schicht]}."""
    done = {"verse": None, "choruses": []}
    verse = next((s for s in plan.sections if s.kind == "Verse" and s.occurrence == 1), None)
    if verse is not None and verse.bars >= MIN_BARS and verse.feel != "breakdown":
        alone = next((inst for inst in ALONE if any(_in(e, verse.start, verse.start + BEATS_PER_BAR)
                                                     for e in events.get(inst, ()))), None)
        if alone is not None:
            enter = verse.start + WAIT_BARS * BEATS_PER_BAR
            for inst in SILENT_FIRST:
                evs = events.get(inst)
                if evs:
                    evs[:] = [e for e in evs if not _in(e, verse.start, enter)]
            drums = events.setdefault("drums", [])
            drums += [Ev(enter - 1.0 + k / 4, 0.2, SNARE, _vel(verse.energy, 0.6 + 0.1 * k)) for k in range(4)]
            drums += [Ev(enter, 1.0, CRASH, _vel(verse.energy, 0.85)), Ev(enter, 0.2, KICK, _vel(verse.energy, 1.0))]
            done["verse"] = verse.start
    for sec in plan.sections:
        if sec.kind != "Chorus" or sec.feel == "breakdown" or sec.bars < 4:
            continue
        half = sec.start + (sec.bars // 2) * BEATS_PER_BAR
        for inst in LAYERS:
            mine = [e for e in events.get(inst, ()) if _in(e, half, sec.end) and not e.layer]
            if not mine:
                continue
            events[inst] += [Ev(e.start, e.dur, e.pitch + 12, max(1, round(e.vel * LAYER_VEL)), "octave")
                             for e in mine if e.pitch + 12 <= TOP]
            drums = events.setdefault("drums", [])
            if not any(abs(e.start - half) < 0.05 and e.pitch == CRASH for e in drums):
                drums.append(Ev(half, 1.0, CRASH, _vel(sec.energy, 0.8)))
            done["choruses"].append(half)
            break
    return done
