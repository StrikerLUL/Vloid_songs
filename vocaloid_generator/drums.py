# drums.py – Schlagzeug-Grooves pro Sektion, mit Fills, Crashes und Steigerung vor dem Refrain
import random

from parts import Ev
from song_plan import BEATS_PER_BAR, Section

KICK, RIM, SNARE, CLAP, HAT, PEDAL_HAT, OPEN_HAT = 36, 37, 38, 39, 42, 44, 46
CRASH, RIDE, TAMBOURINE = 49, 51, 54
TOMS = (50, 48, 47, 45, 43, 41)       # hoch nach tief
EXTRAS = (CLAP, TAMBOURINE)            # spielen auch zu den Grooves echter Schlagzeuger
GHOST_VELOCITY = 34                    # leiser als das hier: Ghost-Note


def _eighths(accent_on=0.8, off=0.55):
    return [(s, accent_on if s % 4 == 0 else off) for s in range(0, 16, 2)]


def _sixteenths(on=0.7, eighth=0.5, off=0.32):
    return [(s, on if s % 4 == 0 else eighth if s % 2 == 0 else off) for s in range(16)]


# Takt-Muster: Instrument → [(Sechzehntel, Akzent)]
GROOVES = {
    "pop_verse":   {KICK: [(0, 1.0), (8, 0.9), (11, 0.7)], SNARE: [(4, 1.0), (12, 1.0)],
                    HAT: _eighths(), "ghost": [(7, 1.0), (15, 1.0)]},
    "pop_pre":     {KICK: [(0, 1.0), (6, 0.7), (8, 0.9), (10, 0.7)], SNARE: [(4, 1.0), (12, 1.0)],
                    HAT: _sixteenths(), TAMBOURINE: [(4, 0.6), (12, 0.6)]},
    "pop_chorus":  {KICK: [(0, 1.0), (3, 0.7), (8, 0.95), (10, 0.75)], SNARE: [(4, 1.0), (12, 1.0)],
                    OPEN_HAT: [(s, 0.7 if s % 4 == 0 else 0.55) for s in range(2, 16, 4)],
                    HAT: [(s, 0.75) for s in range(0, 16, 4)], TAMBOURINE: _eighths(0.55, 0.45)},
    "four_floor":  {KICK: [(0, 1.0), (4, 1.0), (8, 1.0), (12, 1.0)], CLAP: [(4, 0.9), (12, 0.9)],
                    SNARE: [(4, 0.65), (12, 0.65)], OPEN_HAT: [(2, 0.7), (6, 0.7), (10, 0.7), (14, 0.7)],
                    HAT: [(s, 0.35) for s in range(1, 16, 2)]},
    "edm_verse":   {KICK: [(0, 1.0), (8, 0.9)], CLAP: [(4, 0.8), (12, 0.8)],
                    HAT: [(2, 0.6), (6, 0.6), (10, 0.6), (14, 0.6)]},
    "rock_verse":  {KICK: [(0, 1.0), (8, 0.9), (10, 0.8)], SNARE: [(4, 1.0), (12, 1.0)], HAT: _eighths(0.85, 0.65)},
    "rock_chorus": {KICK: [(0, 1.0), (3, 0.75), (8, 1.0), (10, 0.8)], SNARE: [(4, 1.0), (12, 1.0)],
                    RIDE: _eighths(0.8, 0.6)},
    "double_kick": {KICK: [(s, 0.85 if s % 4 == 0 else 0.68) for s in range(16)], SNARE: [(4, 1.0), (12, 1.0)],
                    RIDE: [(s, 0.75) for s in range(0, 16, 4)], CRASH: [(0, 0.6)]},
    "halftime":    {KICK: [(0, 1.0), (10, 0.7)], SNARE: [(8, 1.0)], HAT: _eighths(0.6, 0.42)},
    "ballad":      {KICK: [(0, 0.9), (10, 0.6)], SNARE: [(4, 0.85), (12, 0.85)], HAT: _eighths(0.5, 0.38)},
    "ballad_light": {KICK: [(0, 0.7), (10, 0.5)], RIM: [(4, 0.6), (12, 0.6)], HAT: _eighths(0.38, 0.28)},
    "citypop":     {KICK: [(0, 1.0), (7, 0.6), (10, 0.85)], SNARE: [(4, 1.0), (12, 1.0)],
                    HAT: _sixteenths(0.7, 0.55, 0.35), "ghost": [(3, 1.0), (15, 1.0)]},
    # Future Bass: Snare und Clap nur auf der Drei (halbes Tempo), darüber schnelle Hi-Hats
    "fb_verse":    {KICK: [(0, 1.0), (10, 0.75)], SNARE: [(8, 0.95)], CLAP: [(8, 0.9)], HAT: _eighths(0.6, 0.45)},
    "fb_chorus":   {KICK: [(0, 1.0), (3, 0.6), (10, 0.9)], SNARE: [(8, 1.0)], CLAP: [(8, 1.0)],
                    HAT: [h for h in _sixteenths(0.7, 0.5, 0.35) if h[0] != 14], OPEN_HAT: [(14, 0.6)]},
    # Drum and Bass: der Two-Step, Bassdrum auf 1 und 3+, Snare auf 2 und 4, leise Ghost-Notes dazwischen
    "dnb":         {KICK: [(0, 1.0), (10, 0.9)], SNARE: [(4, 1.0), (12, 1.0)],
                    HAT: [(s, 0.7 if s % 4 == 2 else 0.5) for s in range(0, 16, 2)],
                    "ghost": [(7, 1.0), (9, 1.0), (15, 1.0)]},
    "dnb_verse":   {KICK: [(0, 1.0), (10, 0.85)], SNARE: [(4, 0.9), (12, 0.9)], HAT: [(s, 0.55) for s in range(2, 16, 4)],
                    "ghost": [(7, 1.0), (15, 1.0)]},
    # Lo-Fi: Boom-Bap, gemütlich und mit Swing
    "lofi":        {KICK: [(0, 1.0), (7, 0.55), (10, 0.85)], SNARE: [(4, 0.9), (12, 0.9)], HAT: _eighths(0.5, 0.35),
                    "ghost": [(15, 1.0)]},
    "lofi_light":  {KICK: [(0, 0.8), (10, 0.6)], RIM: [(4, 0.6), (12, 0.6)], HAT: _eighths(0.4, 0.28)},
    "idol_verse":  {KICK: [(0, 1.0), (8, 0.9), (10, 0.7)], SNARE: [(4, 1.0), (12, 1.0)], HAT: _sixteenths(0.7, 0.5, 0.3),
                    TAMBOURINE: [(4, 0.55), (12, 0.55)]},
    # Anison-Grooves (1.3.0, anison.py): 2-Beat, Disco-Hi-Hat und Tom-Groove statt Hi-Hats
    "two_beat":    {KICK: [(s, 1.0 if s % 8 == 0 else 0.9) for s in range(0, 16, 4)],
                    SNARE: [(s, 0.95) for s in range(2, 16, 4)], RIDE: [(s, 0.7) for s in range(0, 16, 2)]},
    "disco":       {KICK: [(s, 1.0) for s in range(0, 16, 4)], SNARE: [(4, 1.0), (12, 1.0)],
                    HAT: [(s, 0.6) for s in range(0, 16, 4)], OPEN_HAT: [(s, 0.75) for s in range(2, 16, 4)]},
    "tom_verse":   {KICK: [(0, 1.0), (8, 0.9), (10, 0.7)], SNARE: [(4, 0.95), (12, 0.95)],
                    TOMS[-1]: [(s, 0.7 if s % 4 == 0 else 0.55) for s in range(0, 16, 2)]},
}


def _vel(energy: float, accent: float) -> int:
    return max(1, min(127, int((52 + 68 * energy) * accent)))


def _fill(kind: str, bar_start: float, energy: float, rng: random.Random) -> tuple:
    """(Ereignisse, ab welchem Sechzehntel der Groove schweigt)"""
    out = []
    if kind == "roll":                                   # ganzer Takt Snare, immer dichter und lauter
        for s in range(16):
            if s < 8 and s % 2:
                continue
            out.append(Ev(bar_start + s / 4, 0.2, SNARE, _vel(energy, 0.55 + 0.45 * s / 15)))
        out.append(Ev(bar_start, 0.2, KICK, _vel(energy, 0.9)))
        return out, 0
    if kind == "toms":                                   # Schläge 3 und 4 die Toms hinunter
        toms = [TOMS[min(i // 2, len(TOMS) - 1)] for i in range(8)]
        for i, s in enumerate(range(8, 16)):
            out.append(Ev(bar_start + s / 4, 0.2, toms[i], _vel(energy, 0.75 + 0.03 * i)))
        out += [Ev(bar_start + 2, 0.2, KICK, _vel(energy, 0.9)), Ev(bar_start + 3, 0.2, KICK, _vel(energy, 0.85))]
        return out, 8
    # kurzer Fill auf Schlag 4
    pattern = rng.choice([[12, 13, 14, 15], [12, 14, 15], [12, 13, 14]])
    for s in pattern:
        out.append(Ev(bar_start + s / 4, 0.2, SNARE, _vel(energy, 0.7 + 0.08 * (s - 12))))
    return out, 12


def _real_fill(drummer, groove: str, bar_start: float, energy: float, rng: random.Random) -> tuple:
    """Ein Fill eines echten Schlagzeugers über den ganzen Takt; ohne passenden der eingebaute kurze."""
    hits = drummer.fill(groove, energy, rng)
    if not hits:
        return _fill("short", bar_start, energy, rng)
    return [Ev(bar_start + pos, 0.2, pitch, vel) for pos, pitch, vel in hits], 0


def drum_section(sec: Section, groove: str, rng: random.Random, drummer=None) -> list:
    """
    Das Schlagzeug einer Sektion. drummer (grooves.Drummer): spielt die Grooves, die er kennt, mit Phrasen und Fills
    echter Schlagzeuger; None = nur die eingebauten Muster.
    """
    out = []
    if not groove:
        return out
    real = drummer is not None and drummer.plays(groove)
    leads_into_chorus = sec.next_kind == "Chorus"
    for b in range(sec.bars):
        bar_start = sec.start + b * BEATS_PER_BAR
        last = b == sec.bars - 1
        fill, silent_from = [], 16
        if last and sec.next_kind is not None:
            kind = "roll" if (leads_into_chorus and sec.kind in ("PreChorus", "Build-up")) or groove == "build" else \
                   "toms" if sec.energy >= 0.55 or leads_into_chorus else "short"
            if real and kind != "roll":
                fill, silent_from = _real_fill(drummer, groove, bar_start, sec.energy, rng)
            else:
                fill, silent_from = _fill(kind, bar_start, sec.energy, rng)
        elif (b + 1) % 8 == 0 and sec.bars > 8:
            fill, silent_from = (_real_fill(drummer, groove, bar_start, sec.energy, rng) if real else
                                 _fill("short", bar_start, sec.energy, rng))
        elif not real and (b + 1) % 4 == 0 and sec.energy >= 0.85 and rng.random() < 0.5:
            fill, silent_from = _fill("short", bar_start, sec.energy, rng)
        out += fill

        if real:
            if silent_from:
                out += [Ev(bar_start + pos, 0.2, pitch, vel) for pos, pitch, vel in drummer.bar(groove, sec.energy, b)
                        if pos * 4 < silent_from]
            for inst, hits in GROOVES[groove].items():          # Clap und Tamburin spielen weiter wie eingebaut
                if inst in EXTRAS:
                    out += [Ev(bar_start + step / 4, 0.2, inst, _vel(sec.energy, accent * rng.uniform(0.94, 1.04)))
                            for step, accent in hits if step < silent_from]
        elif groove == "build":
            division = 4 if b < sec.bars / 2 else 2 if b < sec.bars - 1 else 1
            for s in range(0, min(silent_from, 16), division):
                progress = (b * 16 + s) / (sec.bars * 16)
                out.append(Ev(bar_start + s / 4, 0.2, SNARE, _vel(sec.energy, 0.45 + 0.5 * progress)))
            for s in range(0, min(silent_from, 16), 4):
                out.append(Ev(bar_start + s / 4, 0.2, KICK, _vel(sec.energy, 0.9)))
        else:
            for inst, hits in GROOVES[groove].items():
                for step, accent in hits:
                    if step >= silent_from:
                        continue
                    accent *= rng.uniform(0.94, 1.04)
                    if inst == "ghost":
                        out.append(Ev(bar_start + step / 4, 0.1, SNARE, min(GHOST_VELOCITY, _vel(sec.energy, 0.32))))
                    else:
                        out.append(Ev(bar_start + step / 4, 0.2, inst, _vel(sec.energy, accent)))
            # jede zweite Takthälfte ein offenes Hi-Hat als Auftakt
            if groove in ("pop_verse", "rock_verse", "citypop") and b % 2 == 1 and silent_from == 16:
                out = [e for e in out if not (e.pitch == HAT and abs(e.start - (bar_start + 3.5)) < 1e-6)]
                out.append(Ev(bar_start + 3.5, 0.2, OPEN_HAT, _vel(sec.energy, 0.6)))

        crash_here = b == 0 and sec.index > 0 and sec.energy >= 0.55
        if crash_here or (b % 8 == 0 and b > 0 and sec.energy >= 0.85):
            near = {e.pitch for e in out if abs(e.start - bar_start) < 0.1}   # echte Schläge liegen knapp daneben
            if not near & {CRASH, 57}:
                out.append(Ev(bar_start, 1.0, CRASH, _vel(sec.energy, 0.85)))
            if KICK not in near:
                out.append(Ev(bar_start, 0.2, KICK, _vel(sec.energy, 1.0)))
    return out


def lead_in(sec: Section, rng: random.Random) -> list:
    """Breakdown ohne Schlagzeug: erst im letzten Takt holt ein Snare-Wirbel die Band zurück."""
    if sec.bars < 1:
        return []
    return _fill("roll", sec.end - BEATS_PER_BAR, max(sec.energy, 0.6), rng)[0]
