# bass_runs.py – Melodischer Anime-Bass (1.3.0, I4)
#
# Bis 1.2 spielt der Bass Grundtöne nach seinem Muster, dazu Ghost-Notes, Slides und einzelne Durchgangstöne. Jetzt
# läuft er wie im J-Rock und Anisong: am Ende jedes zweiten Takts vor einem großen Schritt auf dem letzten Schlag
# die Tonleiter hinauf oder hinunter zum neuen Grundton, am Ende jeder Vier-Takt-Phrase spielt er einen kleinen Fill
# (Oktave und Weg zurück), im Refrain springen Töne auf dem „und“ in die Oktave, und im City Pop spielt er funkige
# Oktaven mit abgedämpften Tönen dazwischen.
import random

from parts import Ev
from song_plan import BEATS_PER_BAR
from theory import scale_pcs

RUN_SHARE, FILL_SHARE, OCTAVE_SHARE = 0.4, 0.5, 0.35
RUN_MIN_LEAP = 3            # Halbtöne zum nächsten Grundton, ab denen ein Lauf hinführt
FUNK_STYLES = ("City Pop",)
FUNK_SHARE = 0.6            # so viele Takte im City Pop
LO, HI = 28, 55             # Lage des Basses (MIDI)
DEAD_VEL, DEAD_LEN = 0.35, 0.06     # abgedämpfte Töne: so leise und so kurz
CALM = 0.45                 # Sektionen mit weniger Energie: keine Läufe


def _in(e, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def _clear(evs: list, start: float, end: float) -> None:
    keep = []
    for e in evs:
        if _in(e, start, end):
            continue
        if e.start < start < e.start + e.dur:
            e.dur = max(start - e.start, 0.05)
        keep.append(e)
    evs[:] = keep


def _scale(sec) -> list:
    pcs = set(scale_pcs(sec.tonic, sec.mode))
    return [p for p in range(LO - 5, HI + 6) if p % 12 in pcs]


def _run(scale: list, start: int, target: int, count: int) -> list:
    """count Töne der Tonleiter von start in Richtung target, der letzte einen Schritt vor dem Ziel."""
    up = target > start
    steps = [p for p in scale if (start < p < target if up else target < p < start)]
    if not up:
        steps = steps[::-1]
    path = steps[-count:] if len(steps) >= count else steps
    if len(path) < count:
        near = target - 1 if up else target + 1
        path = (path + [near])[-count:]
    return path


def apply(plan, events: dict, label: str, style: str) -> dict:
    """Läufe, Fills, Oktaven und Funk-Oktaven im Bass. Rückgabe: wie oft was, zum Nachsehen."""
    bass = events.get("bass")
    done = {"runs": 0, "fills": 0, "octaves": 0, "funk": 0}
    if not bass:
        return done
    for sec in plan.sections:
        if sec.feel == "breakdown" or sec.energy < CALM:
            continue
        rng = random.Random(f"{label}:bassrun:{sec.kind}:{sec.occurrence}")
        scale = _scale(sec)
        for b in range(sec.bars):
            bar = sec.start + b * BEATS_PER_BAR
            mine = sorted((e for e in bass if _in(e, bar, bar + BEATS_PER_BAR) and not e.layer),
                          key=lambda e: e.start)
            if not mine:
                continue
            nxt_start = bar + BEATS_PER_BAR
            following = [e for e in bass if _in(e, nxt_start, nxt_start + 0.5) and not e.layer]
            last_beat = bar + BEATS_PER_BAR - 1
            before = [e for e in mine if e.start < last_beat - 1e-6]
            phrase_end = (b + 1) % 4 == 0 and b + 1 < sec.bars
            if phrase_end and before and rng.random() < FILL_SHARE:
                _fill(bass, bar, before[-1], scale, sec)
                done["fills"] += 1
            elif b % 2 == 1 and following and before and abs(following[0].pitch - before[-1].pitch) >= RUN_MIN_LEAP \
                    and rng.random() < RUN_SHARE:
                path = _run(scale, before[-1].pitch, following[0].pitch, 2 if sec.energy < 0.7 else 3)
                step = 0.25 if len(path) > 2 else 0.5           # Sechzehntel oder Achtel auf dem letzten Schlag
                start = nxt_start - step * len(path)
                _clear(bass, start, nxt_start)
                vel = max(e.vel for e in mine)
                bass += [Ev(start + k * step, step * 0.9, p, max(1, round(vel * (0.8 + 0.06 * k))))
                         for k, p in enumerate(path)]
                done["runs"] += 1
            if sec.kind == "Chorus":
                done["octaves"] += _octaves(mine, rng)
            if style in FUNK_STYLES and rng.random() < FUNK_SHARE:
                done["funk"] += _funk(bass, bar, mine, sec)
    return done


def _fill(bass: list, bar: float, anchor, scale: list, sec) -> None:
    """Am Ende der Phrase: Schlag 4 mit Oktave, Septime oder Quinte und einem Ton zurück (Sechzehntel)."""
    root = anchor.pitch if anchor.pitch + 12 <= HI or anchor.pitch - 12 < LO else anchor.pitch - 12
    up = root + 12 if root + 12 <= HI else root      # liegt der Bass hoch, spielt er den Fill von seiner Oktave abwärts
    fifth = next((p for p in scale if p > root and (p - root) in (7, 6, 8)), root + 7)
    seventh = next((p for p in scale if p > root and (p - root) in (10, 11)), up - 2)
    start = bar + BEATS_PER_BAR - 1
    _clear(bass, start, bar + BEATS_PER_BAR)
    vel = anchor.vel
    figure = [(0.0, up), (0.25, seventh), (0.5, fifth), (0.75, root + 2 if root + 2 in scale else root)]
    bass += [Ev(start + t, 0.22, p, max(1, round(vel * (0.85 if k else 0.95)))) for k, (t, p) in enumerate(figure)]


def _octaves(mine: list, rng: random.Random) -> int:
    """Im Refrain: Achtel auf dem „und“, die den Ton davor wiederholen, springen in die Oktave."""
    count = 0
    for a, b in zip(mine, mine[1:]):
        offbeat = abs((b.start % 1) - 0.5) < 1e-6
        if offbeat and b.pitch == a.pitch and b.dur <= 0.5 and b.pitch + 12 <= HI and rng.random() < OCTAVE_SHARE:
            b.pitch += 12
            count += 1
    return count


def _funk(bass: list, bar: float, mine: list, sec) -> int:
    """City Pop: Oktaven auf der Zwei-und und Vier-und, abgedämpfte Töne eine Sechzehntel davor."""
    count = 0
    starts = {round((e.start - bar) * 4): e for e in mine}
    for step in (6, 14):
        on = starts.get(step)
        if on is not None:                    # dort spielt der Bass schon: der Ton springt in die Oktave
            before = [e for e in mine if e.start < on.start - 1e-6]
            if not before or on.pitch % 12 != before[-1].pitch % 12 or on.pitch + 12 > HI:
                continue
            on.pitch += 12
            root = before[-1]
        else:                                 # dort klingt ein langer Ton: er wird kürzer, die Oktave kommt dazu
            held = [e for e in mine if e.start <= bar + step / 4 < e.start + e.dur]
            if not held:
                continue
            root = held[-1]
            root.dur = min(root.dur, bar + (step - 1) / 4 - root.start - 0.02)
            if root.dur <= 0.05:
                continue
            pitch = root.pitch + 12 if root.pitch + 12 <= HI else root.pitch
            bass.append(Ev(bar + step / 4, 0.2, pitch, max(1, round(root.vel * 0.9))))
        if step - 1 not in starts:
            if root.start < bar + (step - 1) / 4 < root.start + root.dur:
                root.dur = max(0.05, bar + (step - 1) / 4 - root.start - 0.02)
            bass.append(Ev(bar + (step - 1) / 4, DEAD_LEN, root.pitch, max(1, round(root.vel * DEAD_VEL))))
        count += 1
    return count
