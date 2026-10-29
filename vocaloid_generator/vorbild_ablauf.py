# vorbild_ablauf.py – „Wie dieser Song“ (1.5.0 S1): Ablauf, Takte und Akkorde eines Vorbilds als Vorlage
#
# librosa misst Tempo und Schläge, sucht den ersten Schlag jedes Takts (dort setzen Bassdrum und Akkordwechsel ein),
# erkennt pro Takt den Akkord (Dur oder Moll, der Basston zählt mit) und teilt den Song dort in Abschnitte, wo sich
# Klang und Lautstärke ändern. Abschnitte mit denselben Akkorden und ähnlicher Lautstärke bekommen denselben Namen:
# der lauteste, der wiederkehrt, ist der Refrain, was davor wiederkehrt die Strophe, was direkt vor dem Refrain neu
# ist der Pre-Chorus. Heraus kommt eine Vorlage mit Tempo, Tonart, Ablauf, Takten pro Sektionsart und den Akkorden als
# Stufen (IV V iii vi), damit sie in jeder Tonart passen. Aus dem Vorbild landen nur diese Zahlen und Stufen im Song,
# kein Ton der Aufnahme. Die Erkennung kann danebenliegen: alles steht danach in den Feldern und lässt sich ändern.
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

import config
import reference

log = logging.getLogger(__name__)

CACHE = os.path.join(config.DATA_DIR, "vorbild_ablauf.json")
VERSION = 1                     # neue Messmethode = alter Cache ungültig
RATE = 22050
HOP = 512
MAX_SECONDS = 480               # ganze Songs, nicht nur der Anfang wie bei reference.py
MIN_PART_BARS = 4               # kürzer wird kein Abschnitt (außer einem Intro von 2 Takten)
MAX_PART_BARS = 16              # länger wird an der deutlichsten Stelle geteilt
SAME_PART = 0.58                # Abstand, unter dem zwei Abschnitte derselbe Teil sind (Akkorde + Lautstärke + Klang)
BASS_WEIGHT = 0.35              # so stark zählt der Basston bei der Akkorderkennung
SPLIT_MARGIN = 0.08             # so viel besser muss ein zweiter Akkord in einer Takthälfte passen
LOOP_SHARE = 0.85               # so viele Takte müssen zur kurzen Schleife passen, damit sie die Akkorde ersetzt

_MAJOR = ("I", "bII", "II", "bIII", "III", "IV", "bV", "V", "bVI", "VI", "bVII", "VII")
_TEMPLATES = [(root, quality) for quality in ("maj", "min") for root in range(12)]


@dataclass
class Part:
    """Ein Abschnitt des Vorbilds."""
    kind: str
    start: float                # Sekunden
    bars: int
    chords: list = field(default_factory=list)      # Stufen pro Takt, ein Takt kann zwei haben ("I V")


@dataclass
class Template:
    """Was „Wie dieser Song“ übernimmt."""
    path: str
    bpm: int
    key: str
    scale: str
    parts: list

    def structure(self) -> list:
        return [p.kind for p in self.parts]

    def section_bars(self, bpm: float = 0) -> dict:
        """Takte je Sektionsart (die erste ihrer Art zählt). Unter 100 BPM halbiert der Song-Plan Sektionen ab 8
        Takten (song_plan.SLOW_BPM), deshalb stehen dort doppelt so viele in der Vorlage. bpm: das Tempo des neuen
        Songs (0 = das des Vorbilds)."""
        import song_plan
        out = {}
        for p in self.parts:
            bars = p.bars * 2 if (bpm or self.bpm) < song_plan.SLOW_BPM and p.bars * 2 >= 8 else p.bars
            out.setdefault(p.kind, bars)
        return out

    def custom_chords(self) -> dict:
        """Eigene Akkorde je Sektionsart als Stufen, die kürzeste Schleife, die passt („vi | IV | I | V“)."""
        out = {}
        for p in self.parts:
            if p.kind in out or not p.chords:
                continue
            out[p.kind] = " | ".join(" ".join(bar) for bar in loop(p.chords))
        return out

    def updates(self, settings) -> dict:
        """Ablauf, Takte und Akkorde für settings; die Akkorde sind Stufen und passen in jeder Tonart."""
        return {"active_sections": self.structure(),
                "section_bars": {**settings.section_bars, **self.section_bars(settings.bpm)},
                "custom_chords": {**settings.custom_chords, **self.custom_chords()}}

    def describe(self) -> str:
        mode = "Dur" if self.scale == "major" else "Moll"
        return f"{self.bpm} BPM, {self.key} {mode}, " + " · ".join(f"{p.kind} {p.bars}" for p in self.parts)


def loop(chords: list) -> list:
    """Die kürzeste Wiederholung (1, 2, 4 oder 8 Takte), zu der fast alle Takte passen; sonst die ersten 8."""
    for period in (1, 2, 4, 8):
        if period > len(chords):
            break
        fits = sum(chords[i] == chords[i % period] for i in range(len(chords)))
        if fits >= LOOP_SHARE * len(chords):
            return chords[:period]
    return chords[:8]


def for_references(refs) -> Optional[Template]:
    """Die Vorlage aus dem Vorbild mit dem größten Gewicht; None ohne messbares Vorbild."""
    chosen = sorted(reference.active(refs), key=lambda pw: -pw[1])
    for path, _ in chosen[:1]:
        try:
            return measure(path)
        except Exception as e:
            log.warning("Ablauf von %s nicht messbar: %s", os.path.basename(path), e)
    return None


# ── Messen ───────────────────────────────────────────────────────────────────────
def measure(path: str, use_cache: bool = True) -> Template:
    key = reference._cache_key(path)
    cache = _read_cache() if use_cache else {}
    if key in cache:
        data = cache[key]
        return Template(**{**data, "parts": [Part(**p) for p in data["parts"]]})
    import librosa
    y, sr = librosa.load(path, sr=RATE, mono=True, duration=MAX_SECONDS)
    if len(y) < RATE * 20:
        raise ValueError(f"{os.path.basename(path)} ist zu kurz für einen Ablauf")
    template = analyse(y, sr, path)
    if use_cache:
        cache[key] = asdict(template)
        _write_cache(cache)
    log.info("Ablauf des Vorbilds %s: %s", os.path.basename(path), template.describe())
    return template


def analyse(y: np.ndarray, sr: int, path: str = "") -> Template:
    import librosa
    drums = reference._drum_share(y)
    bpm = reference._tempo(y, drums)
    scores = reference._key_scores(y)
    best = int(np.argmax(scores))
    tonic, scale = best % 12, "major" if best < 12 else "minor"

    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    # trim=False: leise Intros und Strophen gehören zum Ablauf, librosa würde sie sonst abschneiden
    _, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=HOP, start_bpm=bpm, trim=False)
    beats = np.asarray(beats, dtype=int)
    if len(beats) < 16:
        raise ValueError("zu wenige Schläge erkannt")
    # der mittlere Schlag-Abstand ist genauer als das Raster des Tempos (ein Rahmen sind 23 ms)
    times = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)
    mean = 60.0 * (len(times) - 1) / (times[-1] - times[0])
    if abs(mean - bpm) < 0.1 * bpm:
        bpm = mean
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    bass = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_octaves=3)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP, n_mfcc=13)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    spec = np.abs(librosa.stft(y, hop_length=HOP)) ** 2
    low = librosa.onset.onset_strength(S=librosa.power_to_db(spec[librosa.fft_frequencies(sr=sr) < 150]), sr=sr,
                                       hop_length=HOP)

    n = min(chroma.shape[1], bass.shape[1], mfcc.shape[1], len(rms), len(low))
    per_beat = lambda m: _sync(m[..., :n], beats, n)     # noqa: E731
    beat_chroma, beat_bass = per_beat(chroma), per_beat(bass)
    phase = _downbeat_phase(low[:n], beats, beat_chroma)
    bar_beats = beats[phase::4]
    n_bars = len(bar_beats) - 1
    if n_bars < 8:
        raise ValueError("zu wenige Takte erkannt")

    bar_chords, bar_chroma, bar_mfcc, bar_db = [], [], [], []
    for b in range(n_bars):
        first = phase + 4 * b
        halves = [(first, first + 2), (first + 2, first + 4)]
        whole = (first, first + 4)
        bar_chords.append(_bar_chords(beat_chroma, beat_bass, whole, halves, tonic))
        a, z = beats[first], beats[min(first + 4, len(beats) - 1)]
        bar_chroma.append(_unit(chroma[:, a:z].mean(axis=1)))
        bar_mfcc.append(mfcc[:, a:z].mean(axis=1))
        bar_db.append(20 * np.log10(rms[a:z].mean() + 1e-9))
    times = librosa.frames_to_time(bar_beats, sr=sr, hop_length=HOP)
    features = (np.array(bar_chroma), _standardize(np.array(bar_mfcc)), np.array(bar_db))
    bounds = _boundaries(features)
    parts = _label(bounds, bar_chords, features)
    out = []
    for kind, a, z in parts:
        out.append(Part(kind=kind, start=round(float(times[a]), 2), bars=z - a, chords=bar_chords[a:z]))
    return Template(path=os.path.abspath(path) if path else "", bpm=int(round(bpm)), key=reference.KEYS[tonic],
                    scale=scale, parts=out)


def _sync(m: np.ndarray, beats: np.ndarray, n: int) -> np.ndarray:
    """Mittelwert pro Schlag (Spalte k = Schlag k bis k+1)."""
    edges = list(beats[beats < n]) + [n]
    return np.stack([m[..., a:max(z, a + 1)].mean(axis=-1) for a, z in zip(edges, edges[1:])], axis=-1)


def _unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-9 else v


def _standardize(m: np.ndarray) -> np.ndarray:
    return (m - m.mean(axis=0)) / (m.std(axis=0) + 1e-9)


def _downbeat_phase(low: np.ndarray, beats: np.ndarray, beat_chroma: np.ndarray) -> int:
    """Welcher von vier Schlägen der erste im Takt ist: dort ist die Bassdrum am stärksten und der Akkord wechselt."""
    change = np.r_[0.0, np.linalg.norm(np.diff(beat_chroma / (beat_chroma.max(axis=0) + 1e-9), axis=1), axis=0)]
    kick = low[np.clip(beats, 0, len(low) - 1)]
    k, c = kick / (kick.mean() + 1e-9), change / (change.mean() + 1e-9)
    m = min(len(k), len(c))
    return int(np.argmax([k[p:m:4].mean() + c[p:m:4].mean() for p in range(4)]))


def _chord_scores(chroma: np.ndarray, bass: np.ndarray) -> np.ndarray:
    """Passung der 24 Dreiklänge (Dur auf C..B, dann Moll) zu einem Chroma-Vektor."""
    c, b = _unit(chroma), bass / (bass.max() + 1e-9)
    out = np.empty(24)
    for i, (root, quality) in enumerate(_TEMPLATES):
        t = np.zeros(12)
        t[[root, (root + (4 if quality == "maj" else 3)) % 12, (root + 7) % 12]] = 1.0
        out[i] = float(c @ _unit(t)) + BASS_WEIGHT * b[root]
    return out


def _bar_chords(beat_chroma, beat_bass, whole, halves, tonic) -> list:
    """Die Stufen eines Takts: ein Akkord, oder zwei, wenn jede Hälfte deutlich ihren eigenen hat."""
    def scores(span):
        a, z = span
        z = min(z, beat_chroma.shape[1])
        if z <= a:
            return None
        return _chord_scores(beat_chroma[:, a:z].sum(axis=1), beat_bass[:, a:z].sum(axis=1))

    w = scores(whole)
    if w is None:
        return []
    main = int(np.argmax(w))
    picks = []
    for span in halves:
        s = scores(span)
        if s is None:
            break
        best = int(np.argmax(s))
        picks.append(best if s[best] - s[main] > SPLIT_MARGIN else main)
    if len(picks) == 2 and picks[0] != picks[1]:
        return [_roman(picks[0], tonic), _roman(picks[1], tonic)]
    return [_roman(main, tonic)]


def _roman(index: int, tonic: int) -> str:
    root, quality = _TEMPLATES[index]
    name = _MAJOR[(root - tonic) % 12]
    return name if quality == "maj" else "b" * name.startswith("b") + name.lstrip("b").lower()


# ── Abschnitte ───────────────────────────────────────────────────────────────────
def _similarity(features) -> np.ndarray:
    chroma, timbre, db = features
    s_chroma = chroma @ chroma.T
    d = np.linalg.norm(timbre[:, None, :] - timbre[None, :, :], axis=2)
    s_timbre = np.exp(-d / (np.median(d) + 1e-9))
    s_level = np.exp(-np.abs(db[:, None] - db[None, :]) / 3.0)
    return (s_chroma + s_timbre + s_level) / 3


def _boundaries(features) -> list:
    """Takte, an denen ein neuer Abschnitt beginnt (mit 0 und dem Ende), alle 2 Takte geprüft, lieber alle 4."""
    s = _similarity(features)
    n = len(s)
    novelty = {}
    for b in range(2, n - 1, 2):
        w = min(4, b, n - b)
        past, future = s[b - w:b, b - w:b], s[b:b + w, b:b + w]
        cross = s[b - w:b, b:b + w]
        value = past.mean() + future.mean() - 2 * cross.mean()
        novelty[b] = value * (1.0 if b % 4 == 0 else 0.8)
    if not novelty:
        return [0, n]
    values = np.array(list(novelty.values()))
    threshold = values.mean() + 0.5 * values.std()
    chosen = []
    for b in sorted(novelty, key=lambda k: -novelty[k]):
        if novelty[b] < threshold:
            break
        if all(abs(b - c) >= MIN_PART_BARS for c in chosen) and (b >= MIN_PART_BARS or b == 2) and \
                n - b >= MIN_PART_BARS:
            chosen.append(b)
    bounds = sorted([0, n, *chosen])
    # zu lange Abschnitte an der deutlichsten Stelle teilen
    i = 0
    while i < len(bounds) - 1:
        a, z = bounds[i], bounds[i + 1]
        if z - a > MAX_PART_BARS:
            inside = [b for b in novelty if a + MIN_PART_BARS <= b <= z - MIN_PART_BARS and b % 4 == a % 4]
            cut = max(inside, key=lambda k: novelty[k]) if inside else a + MAX_PART_BARS // 2
            bounds.insert(i + 1, cut)
            continue
        i += 1
    return bounds


def _distance(a: tuple, b: tuple, bar_chords: list, features) -> float:
    """Wie verschieden zwei Abschnitte sind: Akkorde Takt für Takt, Lautstärke und Klang."""
    _, timbre, db = features
    length = min(a[1] - a[0], b[1] - b[0])
    first = [bar_chords[a[0] + k][:1] for k in range(length)]
    second = [bar_chords[b[0] + k][:1] for k in range(length)]
    chords = sum(x != y for x, y in zip(first, second)) / max(length, 1)
    level = abs(db[a[0]:a[1]].mean() - db[b[0]:b[1]].mean()) / 6.0
    sound = np.linalg.norm(timbre[a[0]:a[1]].mean(axis=0) - timbre[b[0]:b[1]].mean(axis=0)) / \
        (np.sqrt(timbre.shape[1]) * 2)
    return chords + level + sound


def _label(bounds: list, bar_chords: list, features) -> list:
    """[(Sektionsart, erster Takt, Takt danach)] in Song-Reihenfolge."""
    spans = list(zip(bounds, bounds[1:]))
    db = features[2]
    groups = []
    for i, span in enumerate(spans):
        near = [(min(_distance(spans[j], span, bar_chords, features) for j in g), gi) for gi, g in enumerate(groups)]
        best = min(near, default=None)
        if best is not None and best[0] < SAME_PART:
            groups[best[1]].append(i)
        else:
            groups.append([i])
    group_of = {i: gi for gi, g in enumerate(groups) for i in g}
    level = [float(db[a:z].mean()) for a, z in spans]
    kinds = [""] * len(spans)

    repeated = [g for g in groups if len(g) >= 2]
    if repeated:
        chorus = max(repeated, key=lambda g: (np.mean([level[i] for i in g]), g[0]))
    else:
        chorus = [int(np.argmax(level))]
    for i in chorus:
        kinds[i] = "Chorus"
    last = len(spans) - 1
    if kinds[0] != "Chorus" and (len(groups[group_of[0]]) == 1 or set(groups[group_of[0]]) <= {0, last}
                                 or spans[0][1] - spans[0][0] <= 2):
        kinds[0] = "Intro"
    if last > 0 and not kinds[last] and (len(groups[group_of[last]]) == 1 or kinds[0] == "Intro" and
                                         group_of[last] == group_of[0]):
        kinds[last] = "Outro"
    first_chorus = kinds.index("Chorus")
    # Pre-Chorus: kurz, direkt vor dem Refrain und nie woanders (sonst ist es eine Strophe, die gleich in ihn geht)
    before = {i - 1 for i in range(1, len(spans)) if kinds[i] == "Chorus"}
    for i in sorted(before):
        if not kinds[i] and spans[i][1] - spans[i][0] <= 8 and set(groups[group_of[i]]) <= before:
            for j in groups[group_of[i]]:
                kinds[j] = "PreChorus"
    # Strophe: was vor dem ersten Refrain steht, und alles, was genauso klingt
    for i in range(first_chorus):
        if not kinds[i]:
            for j in groups[group_of[i]]:
                kinds[j] = kinds[j] or "Verse"
    for i in range(1, len(spans) - 1):
        if not kinds[i] and kinds[i - 1] == "Chorus" and kinds[i + 1] in ("Verse", "PreChorus") and \
                spans[i][1] - spans[i][0] <= 8:
            kinds[i] = "Interlude"
    for i, kind in enumerate(kinds):
        if not kind:
            kinds[i] = "Verse" if i < first_chorus else "Bridge"
    # gleiche Teile hintereinander sind einer (eine Strophe aus zwei Hälften)
    merged = []
    for kind, (a, z) in zip(kinds, spans):
        if merged and merged[-1][0] == kind and z - merged[-1][1] <= 2 * MAX_PART_BARS:
            merged[-1] = (kind, merged[-1][1], z)
        else:
            merged.append((kind, a, z))
    kind, a, z = merged[-1]
    if (z - a) % 4 == 1 and z - a > 4:          # der letzte Takt klingt nur aus
        merged[-1] = (kind, a, z - 1)
    return merged


# ── Cache ────────────────────────────────────────────────────────────────────────
def _read_cache() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("entries", {}) if data.get("version") == VERSION else {}
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "entries": cache}, f, ensure_ascii=False)
    except OSError as e:
        log.warning("Ablauf-Cache nicht gespeichert: %s", e)
