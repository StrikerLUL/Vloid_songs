# kime.py – Kime, Stopps und kleine Fills der Band (1.3.0, I2)
#
# Bis 1.2 spielt jedes Instrument sein Muster Takt für Takt, und die Band setzt nur auf dem letzten Schlag vor dem
# Refrain aus. Jetzt spielt sie an passenden Stellen gemeinsam Akzente (Kime): alle auf denselben Schlägen, mit
# Bassdrum und Becken, dazwischen Stille. Im Stopp setzt sie für zwei Schläge aus und nur die Stimme singt, und am
# Ende jeder Vier-Takt-Phrase spielt ein Instrument einen kleinen Lauf in die Lücke des Gesangs.
import random

from drums import CRASH, KICK, SNARE, _vel as drum_vel
from parts import Ev
from song_plan import BEATS_PER_BAR
from theory import scale_pcs

# Akzente im Takt (Sechzehntel); vor dem Refrain enden sie vor dem letzten Schlag, der gehört dem Fill
KIME_PATTERNS = ((0, 6, 12), (0, 3, 6, 12), (0, 6, 10), (0, 2, 6, 8), (0, 3, 6, 10, 12))
# Wie oft es an einer Stelle passiert: Takt vor dem Refrain (Kime oder Stopp), Ende des letzten Refrains, Stopp in der
# Strophe, Lauf am Ende einer Vier-Takt-Phrase
PRE_KIME, PRE_STOP, LAST_KIME, VERSE_STOP, PHRASE_FILL = 0.45, 0.25, 0.6, 0.35, 0.6
CALM = {"Ballade": 0.3, "Lo-Fi": 0.3, "City Pop": 0.7}      # ruhige Stile: Kime und Stopps seltener
NO_KIME = ("perc", "melody", "fx")                           # spielen dort nicht mit, Percussion schweigt
FILLERS = ("piano", "guitar", "synth", "strings", "bells")   # wer einen Lauf am Phrasenende spielt (der Bass: I4)
HIT_LEN = 0.25


def apply(plan, events: dict, label: str, style: str) -> dict:
    """Setzt Kime, Stopps und Läufe in die Ereignisse der Band. label: Zufall des Songs (eigener je Sektion).
    Rückgabe: {"kime": [Takte], "stops": [Anfänge], "fills": [(Instrument, Anfang)]} zum Nachsehen."""
    calm = CALM.get(style, 1.0)
    done = {"kime": [], "stops": [], "fills": []}
    for sec in plan.sections:
        if sec.feel == "breakdown":
            continue
        rng = random.Random(f"{label}:kime:{sec.index}")
        last_bar = sec.end - BEATS_PER_BAR
        busy = set()
        if sec.next_kind == "Chorus" and sec.kind in ("PreChorus", "Build-up"):
            roll = rng.random()
            if roll < PRE_KIME * calm:
                _kime(sec, events, last_bar, rng.choice([p for p in KIME_PATTERNS if max(p) <= 12]), True)
                done["kime"].append(last_bar)
                busy.add(last_bar)
            elif roll < (PRE_KIME + PRE_STOP) * calm:
                _stop(sec, events, last_bar, last_bar + 4, into_chorus=True)
                done["stops"].append(last_bar)
                busy.add(last_bar)
        elif sec.kind == "Chorus" and sec.is_last_of_kind and sec.next_kind == "Outro" and rng.random() < LAST_KIME * calm:
            _kime(sec, events, last_bar, rng.choice(KIME_PATTERNS), False)
            done["kime"].append(last_bar)
            busy.add(last_bar)
        if sec.kind == "Verse" and sec.bars >= 12 and rng.random() < VERSE_STOP * calm:
            bar = sec.start + 7 * BEATS_PER_BAR
            _stop(sec, events, bar + 2, bar + 4)
            done["stops"].append(bar + 2)
            busy.add(bar)
        if sec.kind in ("Verse", "PreChorus", "Chorus", "Bridge", "Intro", "Interlude"):
            for b in range(3, sec.bars - 1, 4):
                bar = sec.start + b * BEATS_PER_BAR
                if bar in busy or rng.random() >= PHRASE_FILL:
                    continue
                inst = _phrase_fill(sec, plan, events, bar, rng)
                if inst:
                    done["fills"].append((inst, bar))
    return done


def _in(e: Ev, start: float, end: float) -> bool:
    return start - 1e-6 <= e.start < end - 1e-6


def _clear(evs: list, start: float, end: float) -> list:
    """Ereignisse zwischen start und end weg; was hineinklingt, endet bei start. Rückgabe: die entfernten."""
    removed, kept = [], []
    for e in evs:
        if _in(e, start, end):
            removed.append(e)
            continue
        if e.start < start < e.start + e.dur:
            e.dur = max(start - e.start, 0.05)
        kept.append(e)
    evs[:] = kept
    return removed


def _voicing(removed: list, bar: float) -> dict:
    """{Unterspur: (Tonhöhen, Lautstärke)} des Griffs, den das Instrument am Taktanfang spielte."""
    out = {}
    for layer in {e.layer for e in removed}:
        mine = [e for e in removed if e.layer == layer]
        first = [e for e in mine if e.start < bar + 1.0] or mine
        pitches = sorted({e.pitch for e in first})
        out[layer] = (pitches, max(e.vel for e in mine))
    return out


def _revoice(pitches: list, chord, bass: bool = False) -> list:
    """Derselbe Griff auf einem anderen Akkord: jeder Ton rückt auf den nächsten Akkordton (der Bass auf den Basston)."""
    if bass:
        return sorted({min((q for q in range(p - 6, p + 7) if q % 12 == chord.bass_pc), key=lambda q: (abs(q - p), q))
                       for p in pitches})
    moved = set()
    for p in pitches:
        moved.add(min((q for q in range(p - 6, p + 7) if q % 12 in chord.pcs), key=lambda q: (abs(q - p), q)))
    return sorted(moved)


def _kime(sec, events: dict, bar: float, pattern: tuple, into_chorus: bool) -> None:
    """Die ganze Band spielt die Akzente pattern im Takt ab bar; dazwischen ist es still."""
    end = bar + (3.0 if into_chorus else BEATS_PER_BAR)     # vor dem Refrain bleibt der letzte Schlag dem Fill
    hits = [bar + s / 4 for s in pattern]
    for inst, evs in events.items():
        if inst in ("drums",) + NO_KIME:
            if inst == "perc":
                _clear(evs, bar, bar + BEATS_PER_BAR)
            continue
        removed = _clear(evs, bar, end)
        for layer, (pitches, vel) in _voicing(removed, bar).items():
            for i, t in enumerate(hits):
                length = HIT_LEN if i + 1 < len(hits) else min(0.75, end - t)
                for p in _revoice(pitches, sec.chord_at(t), inst == "bass"):
                    evs.append(Ev(t, length, p, min(120, vel + 8), layer))
    drums = events["drums"]
    _clear(drums, bar, end)
    for i, t in enumerate(hits):
        accent = 1.0 if i in (0, len(hits) - 1) else 0.9
        drums += [Ev(t, 0.2, KICK, drum_vel(sec.energy, accent)), Ev(t, 0.5, CRASH, drum_vel(sec.energy, 0.85 * accent))]
        if i:
            drums.append(Ev(t, 0.2, SNARE, drum_vel(sec.energy, 0.9 * accent)))
    if into_chorus:
        _clear(drums, end, bar + BEATS_PER_BAR)
        drums += [Ev(end + s / 4, 0.2, SNARE, drum_vel(sec.energy, 0.7 + 0.1 * s)) for s in range(4)]


def _stop(sec, events: dict, start: float, end: float, into_chorus: bool = False) -> None:
    """Stopp: ein kurzer Schlag aller auf start, dann schweigt die Band bis end; nur die Stimme singt. Das Schlagzeug
    holt die Band mit zwei Sechzehnteln (vor dem Refrain mit einem Wirbel auf dem letzten Schlag) zurück."""
    for inst, evs in events.items():
        if inst == "drums" or inst in NO_KIME:
            if inst == "perc":
                _clear(evs, start, end)
            continue
        removed = _clear(evs, start, end)
        for layer, (pitches, vel) in _voicing(removed, start).items():
            evs += [Ev(start, HIT_LEN * 2, p, min(120, vel + 6), layer)
                    for p in _revoice(pitches, sec.chord_at(start), inst == "bass")]
    drums = events["drums"]
    _clear(drums, start, end)
    drums += [Ev(start, 0.2, KICK, drum_vel(sec.energy, 1.0)), Ev(start, 1.0, CRASH, drum_vel(sec.energy, 0.8))]
    if into_chorus:
        drums += [Ev(end - 1 + s / 4, 0.2, SNARE, drum_vel(sec.energy, 0.7 + 0.1 * s)) for s in range(4)]
    else:
        drums += [Ev(end - 0.5, 0.2, SNARE, drum_vel(sec.energy, 0.7)), Ev(end - 0.25, 0.2, SNARE, drum_vel(sec.energy, 0.85))]


def _phrase_fill(sec, plan, events: dict, bar: float, rng: random.Random):
    """Ein Instrument spielt auf dem letzten Schlag des Takts einen Lauf zum Akkord des nächsten Takts. Rückgabe: wer."""
    window = (bar + 3.0, bar + BEATS_PER_BAR)
    playing = [inst for inst in FILLERS if any(_in(e, bar, bar + BEATS_PER_BAR) for e in events.get(inst, ()))]
    if not playing:
        return None
    inst = rng.choice(playing)
    evs = events[inst]
    mine = [e for e in evs if _in(e, bar, bar + BEATS_PER_BAR) and not e.layer]
    if not mine:
        return None
    center = sorted(e.pitch for e in mine)[len(mine) // 2]
    vel = max(e.vel for e in mine)
    target_chord = plan.chord_at(bar + BEATS_PER_BAR) if bar + BEATS_PER_BAR < plan.total_beats else sec.chord_at(bar)
    scale = sorted(p for p in range(center - 14, center + 15) if p % 12 in scale_pcs(sec.tonic, sec.mode))
    goal = min((p for p in scale if p % 12 == target_chord.root), key=lambda p: abs(p - center), default=center)
    up = rng.random() < 0.6
    count = rng.choice((3, 4))
    i = scale.index(goal) if goal in scale else len(scale) // 2
    run = [scale[max(0, min(len(scale) - 1, i + (-k if up else k)))] for k in range(count, 0, -1)]
    _clear(evs, *window)
    step = 0.25
    first = window[1] - count * step
    evs += [Ev(first + k * step, step * 0.9, p, max(40, int(vel * (0.75 + 0.07 * k)))) for k, p in enumerate(run)]
    return inst
