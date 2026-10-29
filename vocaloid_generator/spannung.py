# spannung.py – Die Spannungskurve (1.6.0)
#
# Wie viel Energie jeder Teil des Songs hat, gezeichnet pro Vorkommen (die zweite Strophe anders als die erste): ein
# Regler je Sektion im Tab Ablauf, dazu die Stimmung (ruhig … wild) der einfachen Ansicht, die alle Sektionen
# verschiebt, die nicht gezeichnet sind. Die Energie steuert, was ohnehin an ihr hängt: Anschlag, Fills und Becken des
# Schlagzeugs, Anschlag, Oktaven und Anschlagmuster der Band, die Bilder im Video. Dazu kommt:
#  - sehr leise gezeichnet (unter BREAKDOWN_BELOW): die erste Hälfte spielt als Breakdown, ohne Schlagzeug;
#  - laut gezeichnet (ab LIFT_ABOVE): kein gewürfelter Breakdown in dieser Sektion;
#  - leise (unter THIN_BELOW, gezeichnet oder durch die Stimmung): die Schmuck-Instrumente (THIN) setzen aus;
#  - im Mix: gezeichnete Sektionen werden leiser oder lauter als sonst (RIDE_DB je Energie, höchstens QUIETER_DB
#    leiser und LOUDER_DB lauter, mixer._ride_tension). Mit Vorbild-Songs bestimmen die den Lautstärke-Verlauf,
#    gemessen an derselben gezeichneten Energie.
# Ohne Zeichnung und mit der Stimmung in der Mitte bleibt der Song genau wie bisher.
from dataclasses import dataclass
from typing import Optional

from song_plan import BEATS_PER_BAR, default_energy

MOOD_SHIFT = 0.25           # so weit verschiebt die Stimmung ganz ruhig oder ganz wild die Energie
LOWEST = 0.1
BREAKDOWN_BELOW = 0.3
LIFT_ABOVE = 0.75
THIN_BELOW = 0.45
THIN = ("brass", "bells", "counter", "perc")
RIDE_DB = 6.0               # dB je ganzer Energie-Einheit Unterschied zur gewohnten
QUIETER_DB, LOUDER_DB = 4.0, 2.0


def key(kind: str, occurrence: int) -> str:
    """Der Schlüssel in settings.tension: „Chorus#2“ ist der zweite Refrain."""
    return f"{kind}#{occurrence}"


@dataclass
class Punkt:
    """Ein Punkt der Kurve: eine Sektion des Ablaufs."""
    key: str
    kind: str
    occurrence: int
    normal: float           # so viel Energie hat sie ohne Zeichnung (mit der Stimmung)
    value: float            # gezeichnet oder normal

    @property
    def drawn(self) -> bool:
        return abs(self.value - self.normal) > 1e-6


def _clamp(energy: float) -> float:
    return round(min(1.0, max(LOWEST, energy)), 3)


def shift(mood: float) -> float:
    return (mood - 0.5) * 2 * MOOD_SHIFT


def normals(structure: list, mood: float = 0.5) -> list:
    """[(Schlüssel, Energie ohne Zeichnung)] für einen Ablauf, wie build_plan sie vergibt, mit der Stimmung."""
    chorus = [i for i, kind in enumerate(structure) if kind == "Chorus"]
    last = chorus[-1] if len(chorus) > 1 else -1
    seen, out = {}, []
    for i, kind in enumerate(structure):
        seen[kind] = seen.get(kind, 0) + 1
        out.append((key(kind, seen[kind]), _clamp(default_energy(kind, seen[kind], i == last) + shift(mood))))
    return out


def points(settings) -> list:
    """[Punkt] für den Ablauf in settings: die Regler im Tab Ablauf."""
    out = []
    for k, normal in normals(settings.active_sections, settings.mood):
        kind, _, number = k.partition("#")
        out.append(Punkt(k, kind, int(number), normal, settings.tension.get(k, normal)))
    return out


def draw(settings, k: str, value: float) -> dict:
    """settings.tension mit diesem Punkt; ein Wert wie ohne Zeichnung nimmt ihn wieder heraus."""
    normal = dict(normals(settings.active_sections, settings.mood)).get(k)
    out = {name: level for name, level in settings.tension.items() if name != k}
    if normal is None or abs(value - normal) > 0.01:
        out[k] = round(float(value), 2)
    return out


def extras(settings) -> Optional[dict]:
    """Was orchestrator.compose_song braucht ({"drawn": {Schlüssel: Energie}, "mood": 0 bis 1}); None = wie bisher."""
    if not settings.tension_curve or (not settings.tension and abs(settings.mood - 0.5) < 1e-6):
        return None
    return {"drawn": dict(settings.tension), "mood": settings.mood}


def apply(plan, wanted: Optional[dict]) -> dict:
    """Setzt die Energie der Sektionen im Plan (vor meter.plan, in Kompositionsschlägen). Rückgabe fürs Protokoll und
    für thin(): {"drawn", "breakdowns", "lifted": [Schlüssel], "thin": [(Anfang, Ende in Schlägen)]}."""
    done = {"drawn": [], "breakdowns": [], "lifted": [], "thin": []}
    if not wanted:
        return done
    moved, drawn = shift(wanted.get("mood", 0.5)), wanted.get("drawn", {})
    for sec in plan.sections:
        k = key(sec.kind, sec.occurrence)
        if k in drawn:
            sec.energy = _clamp(drawn[k])
            done["drawn"].append(k)
            if sec.energy < BREAKDOWN_BELOW and sec.bars >= 4 and sec.feel != "breakdown":
                sec.feel, sec.resume = "breakdown", sec.start + (sec.bars // 2) * BEATS_PER_BAR
                done["breakdowns"].append(k)
            elif sec.energy >= LIFT_ABOVE and sec.feel == "breakdown":
                sec.feel, sec.resume = "", None
                done["lifted"].append(k)
        elif moved:
            sec.energy = _clamp(sec.energy + moved)
        else:
            continue
        if sec.energy < THIN_BELOW:
            done["thin"].append((sec.start, sec.end))
    return done


def thin(events: dict, windows: list) -> int:
    """Die Schmuck-Instrumente (THIN) setzen in den leisen Sektionen aus; Rückgabe: so viele Töne fallen weg."""
    dropped = 0
    for inst in THIN:
        evs = events.get(inst)
        if not evs:
            continue
        kept = [e for e in evs if not any(a - 1e-6 <= e.start < b - 1e-6 for a, b in windows)]
        dropped += len(evs) - len(kept)
        evs[:] = kept
    return dropped


def describe(done: dict) -> str:
    parts = [f"gezeichnet: {', '.join(done['drawn'])}"] if done["drawn"] else []
    if done["breakdowns"]:
        parts.append(f"Breakdown in {', '.join(done['breakdowns'])}")
    if done["lifted"]:
        parts.append(f"kein Breakdown in {', '.join(done['lifted'])}")
    if done["thin"]:
        parts.append(f"{len(done['thin'])} Sektionen schlanker besetzt")
    return "; ".join(parts) or "nur die Stimmung"


def rides(settings, plan) -> list:
    """[(Start, Ende in Sekunden, dB)] für den Mix: gezeichnete Sektionen leiser oder lauter als gewohnt."""
    wanted = extras(settings)
    if not wanted or not wanted["drawn"] or plan is None:
        return []
    normal = dict(normals([sec.kind for sec in plan.sections]))
    spb = plan.seconds_per_beat
    out = []
    for sec in plan.sections:
        k = key(sec.kind, sec.occurrence)
        if k not in wanted["drawn"]:
            continue
        db = min(LOUDER_DB, max(-QUIETER_DB, (wanted["drawn"][k] - normal[k]) * RIDE_DB))
        if abs(db) >= 0.1:
            out.append((sec.start * spb, sec.end * spb, round(db, 2)))
    return out
