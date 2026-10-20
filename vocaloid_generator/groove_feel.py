# groove_feel.py – Die Band spielt im Groove des Schlagzeugers (1.3.0, I3)
#
# Die echten Grooves (grooves.py) haben das Timing echter Schlagzeuger: Bassdrum und Snare liegen knapp vor oder
# hinter dem Raster, betonte Schläge sind lauter. Bass, Gitarre und Klavier lagen bis 1.2 genau auf dem Raster, mit
# eigenem Zufall. Jetzt rückt jeder Ton der Band, der auf einer Sechzehntel mit einem Schlag des Schlagzeugs liegt,
# um dessen Verschiebung (der Bass ganz, die anderen etwas weniger) und wird lauter, wo der Schlagzeuger betont,
# und etwas leiser, wo er schweigt. Mit den eingebauten Grooves (genau im Raster) bleiben nur die Betonungen.
from drums import CLAP, HAT, KICK, OPEN_HAT, PEDAL_HAT, RIDE, SNARE

FOLLOWERS = {"bass": 1.0, "guitar": 0.8, "piano": 0.7, "brass": 0.8, "synth": 0.5, "counter": 0.5}
ACCENT = {"bass": 0.18, "guitar": 0.12, "piano": 0.1, "brass": 0.12, "synth": 0.06, "counter": 0.06}
QUIET = 0.04                 # so viel leiser, wo das Schlagzeug auf dieser Sechzehntel nichts spielt
TIMEKEEPERS = (KICK, SNARE, CLAP, HAT, PEDAL_HAT, OPEN_HAT, RIDE)
NEAR = 0.12                  # Schläge: so weit darf ein Ton vom Raster liegen, damit er zu einer Sechzehntel gehört
HEAVY = (KICK, SNARE, CLAP)  # zählen für die Betonung doppelt (der Bass hört auf die Bassdrum)


def _grid(start: float) -> float:
    return round(start * 4) / 4


def pocket(drums: list) -> dict:
    """{Sechzehntel ab Songanfang: (mittlere Verschiebung in Schlägen, Lautstärke)} der Schläge des Schlagzeugs."""
    found = {}
    for e in drums:
        if e.pitch not in TIMEKEEPERS:
            continue
        q = _grid(e.start)
        if abs(e.start - q) > NEAR:
            continue
        offsets, vel = found.setdefault(round(q * 4), ([], [0]))
        offsets.append(e.start - q)
        vel[0] = max(vel[0], e.vel * (1.25 if e.pitch in HEAVY else 1.0))
    return {k: (sum(offs) / len(offs), vel[0]) for k, (offs, vel) in found.items()}


def apply(events: dict, until: float = float("inf")) -> dict:
    """Rückt und betont die Töne der Band nach dem Schlagzeug, bis zum Schlag until (der Schlussakkord bleibt).
    Rückgabe: {Instrument: verschobene Töne}."""
    grid = pocket(events.get("drums", []))
    if not grid:
        return {}
    bars = {}
    for step, (_, vel) in grid.items():
        bars.setdefault(step // 16, []).append(vel)
    mean = {bar: sum(v) / len(v) for bar, v in bars.items()}
    moved = {}
    for inst, amount in FOLLOWERS.items():
        count = 0
        for e in events.get(inst, ()):
            q = _grid(e.start)
            if abs(e.start - q) > NEAR or q >= until - 1e-6:
                continue
            step = round(q * 4)
            hit = grid.get(step)
            if hit is None:
                if step // 16 in mean:
                    e.vel = max(1, round(e.vel * (1 - QUIET)))
                continue
            offset, vel = hit
            if offset:
                e.start = max(0.0, e.start + offset * amount)
                count += 1
            rel = vel / mean[step // 16] - 1
            e.vel = max(1, min(127, round(e.vel * (1 + ACCENT[inst] * rel))))
        moved[inst] = count
    return moved
