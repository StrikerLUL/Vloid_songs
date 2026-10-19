# band_runs.py – Läufe und Glissandi (1.3.0, I5)
#
# Übergänge glänzen wie im Vocaloid-Rock: das Klavier spielt am Ende jeder Acht-Takt-Phrase einen Lauf in Sechzehnteln
# und vor dem Refrain ein Glissando über zwei Oktaven, die Streicher laufen in den letzten zwei Schlägen nach oben in
# den Refrain, und in der ersten Hälfte jedes Refrains spielt das Klavier die Hook des Gesangs in Oktaven mit.
import random

from parts import Ev
from song_plan import BEATS_PER_BAR
from theory import scale_pcs

PHRASE_RUN = 0.6            # so oft am Ende einer Acht-Takt-Phrase
GLISS_NOTES = 14            # Töne des Glissandos (zwei Oktaven weiße Tasten)
STRING_RUN = 8              # Sechzehntel der Streicher in den Refrain
HOOK_VEL = 0.62             # die Klavier-Hook im Refrain, so laut wie der Gesang sie nicht verdeckt
HOOK_LO, HOOK_HI = 72, 96   # Lage der Klavier-Hook (die tiefere Oktave)
PIANO_RANGE = (55, 96)
STRING_RANGE = (55, 91)


def _in(e, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def _scale(sec, lo: int, hi: int) -> list:
    pcs = set(scale_pcs(sec.tonic, sec.mode))
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def _playing(evs: list, start: float, end: float) -> list:
    return [e for e in evs if _in(e, start, end) or e.start < start < e.start + e.dur]


def apply(plan, events: dict, vocal: list, label: str) -> dict:
    """Läufe, Glissando, Streicherlauf und Klavier-Hook. vocal: die Gesangsmelodie, wie die Band sie hört."""
    done = {"runs": 0, "glissandi": 0, "strings": 0, "hooks": 0}
    piano, strings = events.get("piano"), events.get("strings")
    for sec in plan.sections:
        rng = random.Random(f"{label}:runs:{sec.kind}:{sec.occurrence}")
        into_chorus = sec.next_kind == "Chorus" and sec.kind != "Chorus"
        if piano is not None and _playing(piano, sec.start, sec.end):
            for b in range(7, sec.bars - 1, 8):
                bar = sec.start + b * BEATS_PER_BAR
                if rng.random() < PHRASE_RUN:
                    done["runs"] += _phrase_run(piano, plan, sec, bar, rng)
            if into_chorus:
                done["glissandi"] += _glissando(piano, sec)
        if into_chorus and strings is not None and _playing(strings, sec.end - BEATS_PER_BAR, sec.end):
            done["strings"] += _string_run(strings, plan, sec)
        if sec.kind == "Chorus" and piano is not None and sec.feel != "breakdown":
            done["hooks"] += _hook(piano, sec, vocal)
    return done


def _phrase_run(piano: list, plan, sec, bar: float, rng: random.Random) -> int:
    """Auf Schlag 4 vier Sechzehntel der Tonleiter zum Grundton des nächsten Akkords."""
    start, end = bar + 3.0, bar + BEATS_PER_BAR
    mine = [e for e in piano if _in(e, bar, end) and not e.layer]
    if not mine:
        return 0
    top = max(e.pitch for e in mine)
    vel = max(e.vel for e in mine)
    target = plan.chord_at(end) if end < plan.total_beats else sec.chord_at(bar)
    scale = _scale(sec, *PIANO_RANGE)
    goal = min((p for p in scale if p % 12 == target.root), key=lambda p: abs(p - top), default=top)
    i = scale.index(goal)
    up = rng.random() < 0.5
    run = [scale[max(0, min(len(scale) - 1, i + (-k if up else k)))] for k in range(4, 0, -1)]
    for e in piano:
        if _in(e, start, end) and e.pitch >= top - 5 and not e.layer:
            e.dur = 0.0
    piano[:] = [e for e in piano if e.dur > 0]
    piano += [Ev(start + k * 0.25, 0.22, p, max(1, round(vel * (0.7 + 0.08 * k)))) for k, p in enumerate(run)]
    return 1


def _glissando(piano: list, sec) -> int:
    """Vor dem Refrain: weiße Tasten (Tonleiter) über zwei Oktaven hinauf, auf dem vorletzten Schlag."""
    start = sec.end - 2.0
    scale = _scale(sec, 60, 96)
    if len(scale) < GLISS_NOTES:
        return 0
    vel = max((e.vel for e in piano if _in(e, sec.end - BEATS_PER_BAR, sec.end)), default=80)
    step = 1.0 / GLISS_NOTES
    piano += [Ev(start + k * step, step * 1.5, p, max(1, round(vel * (0.55 + 0.4 * k / GLISS_NOTES))), "gliss")
              for k, p in enumerate(scale[:GLISS_NOTES])]
    return 1


def _string_run(strings: list, plan, sec) -> int:
    """Die Streicher laufen in Sechzehnteln hinauf und landen auf der Eins des Refrains auf seinem Grundton."""
    start = sec.end - STRING_RUN / 4
    chord = plan.chord_at(sec.end) if sec.end < plan.total_beats else sec.chord_at(sec.end - 1)
    before = [e for e in strings if _in(e, sec.end - BEATS_PER_BAR, sec.end) and not e.layer]
    top = max((e.pitch for e in before), default=72)
    scale = _scale(sec, *STRING_RANGE)
    goal = min((p for p in scale if p % 12 == chord.root and p > top - 3), default=None)
    if goal is None or goal not in scale or scale.index(goal) < STRING_RUN:
        return 0
    i = scale.index(goal)
    run = scale[i - STRING_RUN:i]
    vel = max((e.vel for e in before), default=80)
    for e in strings:
        if e.start < start < e.start + e.dur and not e.layer:
            e.dur = max(start - e.start, 0.05)
    strings[:] = [e for e in strings if not (_in(e, start, sec.end) and not e.layer)]
    strings += [Ev(start + k * 0.25, 0.24, p, max(1, round(vel * (0.6 + 0.05 * k)))) for k, p in enumerate(run)]
    strings.append(Ev(sec.end, 1.0, goal, max(1, min(127, vel + 8))))
    return 1


def _hook(piano: list, sec, vocal: list) -> int:
    """In der ersten Hälfte des Refrains spielt das Klavier die Melodie des Gesangs in Oktaven, eine Lage höher."""
    half = sec.start + (sec.bars // 2) * BEATS_PER_BAR
    sung = [n for n in vocal if sec.start - 1e-6 <= n.start < half and not getattr(n.syllable, "melisma", False)]
    if not sung:
        return 0
    vel = max((e.vel for e in piano if _in(e, sec.start, half)), default=80)
    shift = 12
    while min(n.pitch for n in sung) + shift < HOOK_LO:
        shift += 12
    while max(n.pitch for n in sung) + shift + 12 > HOOK_HI and shift > 0:
        shift -= 12
    for n in sung:
        length = min(n.dur, 1.0) * 0.9
        for octave in (0, 12):
            piano.append(Ev(n.start, length, n.pitch + shift + octave, max(1, round(vel * HOOK_VEL)), "hook"))
    return 1
