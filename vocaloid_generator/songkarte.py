# songkarte.py – Was im Song wann passiert, für das Video (1.5.0 V1)
#
# Beim Komponieren kennt der Song-Plan alles: Sektionen mit ihrer Energie, Akkorde, Takt und Schläge, das Schlagzeug
# und die Gesangsmelodie. Bis 1.4 landete davon nichts neben dem Song, das Video kannte nur den Text. Jetzt steht es in
# songkarte.json im Song-Ordner, Zeiten in Sekunden ab Songanfang. Das Video (musikvideo.py) liest nur diese Datei.
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

FILE = "songkarte.json"
VERSION = 1
KICKS = (35, 36)
SNARES = (37, 38, 39, 40)          # mit Rimshot und Clap: was auf der Zwei und Vier knallt
CRASHES = (49, 52, 55, 57)
NAMES = {"Intro": "Intro", "Build-up": "Build-up", "Verse": "Strophe", "PreChorus": "Pre-Chorus",
         "Chorus": "Refrain", "Bridge": "Bridge", "Drop": "Drop", "Solo": "Solo", "Rap": "Rap", "Outro": "Outro",
         "Interlude": "Zwischenspiel", "Spoken": "Sprechen"}


@dataclass
class Section:
    kind: str
    occurrence: int
    start: float
    end: float
    energy: float
    vocals: bool

    @property
    def label(self) -> str:
        """„Refrain 2“; das erste Vorkommen ohne Nummer, wenn es das einzige ist, steht in Map.label."""
        return f"{NAMES.get(self.kind, self.kind)} {self.occurrence}"


@dataclass
class Map:
    style: str = ""
    bpm: float = 120.0
    meter: str = "4/4"
    key: str = "C"
    scale: str = "major"
    seed: Optional[int] = None
    length: float = 0.0
    beats: list = field(default_factory=list)        # Zeit jedes Schlags
    accents: int = 4                                 # jeder so-vielte Schlag ist eine Eins
    sections: list = field(default_factory=list)     # [Section]
    chords: list = field(default_factory=list)       # [[Anfang, Ende, Name]]
    kicks: list = field(default_factory=list)
    snares: list = field(default_factory=list)
    crashes: list = field(default_factory=list)
    melody: list = field(default_factory=list)       # [[Anfang, Ende, Tonhöhe]]
    key_change: int = 0
    key_change_at: Optional[float] = None            # ab hier liegt der letzte Refrain höher

    def section_at(self, t: float) -> Optional[Section]:
        for sec in self.sections:
            if sec.start <= t < sec.end:
                return sec
        return self.sections[-1] if self.sections and t >= self.sections[-1].start else None

    def label(self, sec: Section) -> str:
        """„Refrain 2“, oder nur „Bridge“, wenn es nur eine gibt."""
        many = sum(1 for s in self.sections if s.kind == sec.kind) > 1
        return sec.label if many else NAMES.get(sec.kind, sec.kind)

    def chord_at(self, t: float) -> tuple:
        """(jetzt, danach): Namen der Akkorde um t; leer, wo keiner klingt."""
        for i, (start, end, name) in enumerate(self.chords):
            if start <= t < end:
                return name, self.chords[i + 1][2] if i + 1 < len(self.chords) else ""
        return "", ""

    def beat_at(self, t: float) -> tuple:
        """(Nummer des Schlags ab 0, Anteil 0..1 bis zum nächsten); (-1, 0) vor dem ersten."""
        import bisect
        i = bisect.bisect_right(self.beats, t) - 1
        if i < 0:
            return -1, 0.0
        nxt = self.beats[i + 1] if i + 1 < len(self.beats) else self.beats[i] + 60.0 / self.bpm
        return i, min(1.0, (t - self.beats[i]) / max(1e-6, nxt - self.beats[i]))

    def to_dict(self) -> dict:
        data = {k: v for k, v in self.__dict__.items() if k != "sections"}
        data["sections"] = [s.__dict__ for s in self.sections]
        return {"version": VERSION, **data}

    @classmethod
    def from_dict(cls, data: dict) -> "Map":
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "sections"}
        found = cls(**fields)
        found.sections = [Section(**s) for s in data.get("sections", [])]
        return found


def build(settings, tracks: dict) -> Map:
    """Die Songkarte aus den Einstellungen und den komponierten Spuren (pipeline.compose)."""
    plan = tracks.get("plan")
    found = Map(style=settings.style, bpm=float(settings.bpm), meter=settings.meter, key=settings.key,
                scale=settings.scale, seed=settings.seed)
    if plan is None or not plan.sections:
        return found
    spb = plan.seconds_per_beat
    found.bpm = round(60.0 / spb, 3)
    found.length = round(plan.total_beats * spb, 3)
    found.accents = 2 if settings.meter == "6/8" else int(round(plan.bar_beats)) or 4
    found.beats = [round(b * spb, 4) for b in range(int(plan.total_beats))]
    for sec in plan.sections:
        found.sections.append(Section(sec.kind, sec.occurrence, round(sec.start * spb, 3), round(sec.end * spb, 3),
                                      round(float(sec.energy), 3), bool(sec.has_vocals)))
        for slot in sec.chords:
            name = slot.chord.name
            start, end = round(slot.start * spb, 3), round((slot.start + slot.dur) * spb, 3)
            if found.chords and found.chords[-1][2] == name and abs(found.chords[-1][1] - start) < 1e-3:
                found.chords[-1][1] = end
            else:
                found.chords.append([start, end, name])
    drums = tracks.get("drums") or []
    found.kicks = sorted(round(n.start, 3) for n in drums if n.pitch in KICKS)
    found.snares = sorted(round(n.start, 3) for n in drums if n.pitch in SNARES)
    found.crashes = sorted(round(n.start, 3) for n in drums if n.pitch in CRASHES)
    found.melody = [[round(n.start, 3), round(n.end, 3), int(n.pitch)]
                    for n in sorted(tracks.get("vocal_melody") or [], key=lambda n: n.start)]
    found.key_change = int(getattr(plan, "key_change", 0) or 0)
    if found.key_change:
        last = [s for s in found.sections if s.kind == "Chorus"]
        found.key_change_at = last[-1].start if last else None
    return found


def save(path: str, found: Map) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(found.to_dict(), f, ensure_ascii=False)


def load(path: str) -> Optional[Map]:
    """Die Songkarte eines Songs; None bei Songs von 1.4 und älter (das Video kommt dann ohne sie aus)."""
    try:
        with open(path, encoding="utf-8") as f:
            return Map.from_dict(json.load(f))
    except (OSError, ValueError, TypeError, AttributeError) as e:
        log.debug("Keine Songkarte in %s: %s", path, e)
        return None


def write(settings, tracks: dict, out: str) -> Optional[str]:
    path = os.path.join(out, FILE)
    try:
        save(path, build(settings, tracks))
        return path
    except OSError as e:
        log.warning("Songkarte nicht gespeichert: %s", e)
        return None


def chapters(found: Map) -> list:
    """YouTube-Kapitel [(Sekunde, Name)]: jede Sektion; YouTube will das erste bei 0:00 und jedes mindestens 10 s. Eine
    kürzere Sektion geht in der folgenden auf (ein kurzes Intro heißt dann wie die erste Strophe), eine kurze am
    Schluss in der davor."""
    marks = []
    for sec in found.sections:
        name = found.label(sec)
        if not marks or marks[-1][1] != name:
            marks.append([sec.start, name])
    if not marks:
        return []
    marks[0][0] = 0.0
    out = []
    for i, (start, name) in enumerate(marks):
        following = marks[i + 1][0] if i + 1 < len(marks) else max(found.length, start)
        if out and out[-1][2]:                              # die davor war zu kurz: dieses Kapitel übernimmt sie
            start = out.pop()[0]
        out.append([start, name, following - start < 10.0])
    if len(out) > 1 and out[-1][2]:
        out.pop()
    return [(start, name) for start, name, _ in out] if len(out) >= 3 else []


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}" if total < 3600 else f"{total // 3600}:{total // 60 % 60:02d}:{total % 60:02d}"
