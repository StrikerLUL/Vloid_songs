# buildup.py – Aufbau innerhalb der Sektion (1.3.0, I7)
#
# Bis 1.2 spielt die Band eine Sektion vom ersten bis zum letzten Takt gleich voll. Jetzt beginnt die erste Strophe
# nur mit Klavier oder Gitarre und dem Gesang; nach vier Takten kommen Bass und Schlagzeug dazu (mit kurzem Fill und
# Becken), dann der Rest. In der zweiten Hälfte jedes Refrains spielt eine Schicht mehr: die Streicher (oder der Synth,
# oder das Klavier) eine Oktave höher dazu, leiser, und das Schlagzeug setzt dort mit einem Becken ein.
# 1.11.0: nach einem Refrain (oder Drop, Solo, Zwischenspiel) atmet die nächste Strophe durch: in ihren ersten zwei
# Takten schweigen Flächen und Verzierungen (Streicher, Synth, Bläser, Glocken, Gegenstimme, Chor), Schlagzeug, Bass und
# das Akkordinstrument tragen weiter. Bis 1.10 lief die zweite Strophe direkt nach dem Refrain so voll weiter, dass der
# Gesang darin unterging (FIR-54, FIR-49).
from drums import CRASH, KICK, SNARE, _vel
from parts import Ev
from song_plan import BEATS_PER_BAR

ALONE = ("piano", "guitar")              # wer die Strophe allein beginnt (der erste, der dort spielt)
WAIT_BARS = 4                            # so lange spielt er allein
MIN_BARS = 8                             # kürzere Strophen bauen nicht auf
SILENT_FIRST = ("bass", "drums", "perc", "synth", "strings", "brass", "bells", "counter", "choir", "melody")
LAYERS = ("strings", "synth", "piano")   # wer im Refrain die Oktave dazu spielt
LAYER_VEL = 0.55
BREATH_BARS = 2                          # 1.11.0: so lange atmet eine Strophe nach dem Höhepunkt durch
BREATH_QUIET = ("strings", "synth", "brass", "bells", "counter", "choir")
BREATH_AFTER = ("Chorus", "Drop", "Solo", "Interlude")
TOP = 100


def _in(e, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def apply(plan, events: dict) -> dict:
    """Rückgabe: {"verse": Anfang der allein begonnenen Strophe oder None, "choruses": [Anfänge der Schicht],
    "breaths": [Anfänge der Strophen, die nach einem Höhepunkt durchatmen]}."""
    done = {"verse": None, "choruses": [], "breaths": breathe(plan, events)}
    verse = next((s for s in plan.sections if s.kind == "Verse" and s.occurrence == 1), None)
    if verse is not None and verse.bars >= MIN_BARS and verse.feel != "breakdown":
        alone = next((inst for inst in ALONE if any(_in(e, verse.start, verse.start + BEATS_PER_BAR)
                                                     for e in events.get(inst, ()))), None)
        if alone is not None:
            enter = verse.start + WAIT_BARS * BEATS_PER_BAR
            for inst in SILENT_FIRST + tuple(inst for inst in ALONE if inst != alone):
                evs = events.get(inst)
                if evs:
                    # Aus dem Intro gehaltene Töne dürfen die leise Strophe nicht überdecken.
                    for e in evs:
                        if e.start < verse.start and e.start + e.dur > verse.start:
                            e.dur = verse.start - e.start
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


def breathe(plan, events: dict) -> list:
    """1.11.0: Strophen nach einem Höhepunkt beginnen ohne Flächen und Verzierungen (BREATH_BARS Takte); was aus dem
    Refrain hineinklingt, endet an der Grenze. Rückgabe: die Anfänge dieser Strophen."""
    out = []
    sections = list(plan.sections)
    for k, sec in enumerate(sections):
        before = sections[k - 1] if k > 0 else None
        if sec.kind != "Verse" or before is None or before.kind not in BREATH_AFTER or sec.feel == "breakdown"                 or sec.bars < MIN_BARS:
            continue
        stop = sec.start + BREATH_BARS * BEATS_PER_BAR
        for inst in BREATH_QUIET:
            evs = events.get(inst)
            if not evs:
                continue
            for e in evs:
                if e.start < sec.start < e.start + e.dur:
                    e.dur = sec.start - e.start
            evs[:] = [e for e in evs if not _in(e, sec.start, stop)]
        out.append(sec.start)
    return out
