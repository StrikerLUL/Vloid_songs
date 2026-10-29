# melody_score.py – Punkte für eine Gesangsmelodie (1.3.0, M1)
#
# Der Melodie-Schreiber würfelt, und nicht jeder Wurf ist gleich eingängig. Mit „Beste Melodie suchen“ schreibt er
# CANDIDATES Fassungen jeder Sektionsart, und diese Punkte wählen die beste: ein Umfang, der weder eintönig noch zu
# weit ist, ein klarer Höhepunkt auf einem langen oder betonten Ton, Schritte und Sprünge gemischt, wenige
# Tonwiederholungen am Stück, Takte, deren Motiv wiederkommt, Sprünge, nach denen die Melodie zurückgeht, lange Töne
# nur auf Silben, die man halten kann, und ein Refrain, der höher hinausgeht als die Strophe.
# 1.5.0 (jeweils mit eigenem Schalter): S2 das Kernwort des Refrains liegt hoch oder lang auf der betonten Zeit, und
# Gefühlswörter (涙, 好き, さよなら) bekommen lange Töne; S3 der Refrain ist ein Ohrwurm: seine erste Phrase kommt mit
# kleiner Veränderung wieder, und sein Anfangsmotiv kehrt zurück.
import logging
from typing import Optional

log = logging.getLogger(__name__)

CANDIDATES = 30
PHRASE_GAP = 1.0             # Schläge Pause, ab denen eine neue Phrase beginnt
# Umfang (Halbtöne vom tiefsten zum höchsten Ton), der sich gut anhört
IDEAL_RANGE = {"Chorus": (9, 13), "Verse": (6, 10), "PreChorus": (7, 11), "Bridge": (7, 12)}
# Anteile der Bewegungen von Ton zu Ton: Schritte (1–2 Halbtöne), Sprünge (ab 3) und Tonwiederholungen
STEP_SHARE = (0.45, 0.75)
LEAP_SHARE = (0.1, 0.3)
REPEAT_SHARE = (0.05, 0.3)
LONG_RUN = 4                 # so viele gleiche Töne nacheinander sind schon eintönig
BIG_LEAP = 5                 # nach einem Sprung ab einer Quarte soll die Melodie zurückgehen
HOLD_BEATS = 1.0             # ab dieser Länge muss die Silbe ein Vokal sein, den man halten kann
UNHELD = ("ん", "っ")
HIGH_SHARE = 0.25            # so viel der Zeit darf die Stimme ganz oben (die oberen zwei Halbtöne) singen
WEIGHTS = {"range": 1.0, "peak": 1.0, "moves": 1.5, "runs": 0.8, "motif": 1.0, "text": 1.0, "recovery": 0.6,
           "contrast": 1.0, "high": 0.6, "words": 1.2, "catchy": 1.2}
# S2: Gefühlswörter, wie sie gesungen werden (Kana); das Wort darf Partikel dahinter haben (なみだが)
FEELING_WORDS = ("すき", "だいすき", "なみだ", "さよなら", "あいして", "あいたい", "ごめん", "ありがとう", "こころ", "ゆめ",
                 "なきたい", "わすれない", "いかないで", "さみしい", "かなしい", "うれしい", "えがお", "やくそく",
                 "えいえん", "きせき", "ひかり", "いのち", "おもいで", "まって", "ずっと", "ひとり")
KEY_WORD_MORAE = 2           # kürzere Wörter sind kein Kernwort
KEY_HIGH = 2                 # Halbtöne unter dem höchsten Ton der Sektion zählen noch als „oben“
KEY_LONG = 1.0               # Schläge: so lang ist ein langer Ton für das Kernwort
FEELING_LONG = 1.5           # so viel länger als der typische Ton klingt das Ende eines Gefühlsworts


def score(notes: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
          bar_beats: float = 4, targets: Optional[dict] = None, extras=()) -> float:
    """
    Punkte einer Sektion (MelNotes), mehr ist besser. below: die schon geschriebenen Töne der Sektionen vor dem
    Refrain (der Refrain soll höher hinaus), top: höchster Ton der Stimme, bar_beats: Schläge pro Takt.
    targets: was im Stil anders gut ist (1.4.0, style_dna.MelodyCharacter.score): "steps", "leaps", "repeats" als
    (von, bis), "range" als {Sektionsart: (von, bis)}, "motif_weight" als Gewicht der Motive.
    extras: eingeschaltete Neuerungen; "key_words" (S2) und "catchy_chorus" (S3) zählen nur mit ihnen.
    """
    weights = dict(WEIGHTS)
    if targets and "motif_weight" in targets:
        weights["motif"] = targets["motif_weight"]
    return sum(weights[name] * value
               for name, value in parts(notes, kind, below, top, bar_beats, targets, extras).items())


def parts(notes: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
          bar_beats: float = 4, targets: Optional[dict] = None, extras=()) -> dict:
    """Die einzelnen Punkte (jeweils etwa -1 bis 1), zum Nachsehen und für die Tests."""
    sung = sorted((n for n in notes if not getattr(n.syllable, "melisma", False)), key=lambda n: n.start)
    if len(sung) < 2:
        return {name: 0.0 for name in WEIGHTS}
    pitches = [n.pitch for n in sung]
    moves = [b.pitch - a.pitch for a, b in zip(sung, sung[1:]) if b.start - a.start - a.dur < PHRASE_GAP]
    return {
        "range": _range(pitches, kind, (targets or {}).get("range")),
        "peak": _peak(sung),
        "moves": _moves(moves, targets),
        "runs": _runs(sung),
        "motif": _motif(sung, bar_beats),
        "text": _text(notes),
        "recovery": _recovery(moves),
        "contrast": _contrast(sung, kind, below),
        "high": _high(sung, top),
        "words": _key_words(notes, kind) if "key_words" in extras else 0.0,
        "catchy": _catchy(sung) if "catchy_chorus" in extras and kind == "Chorus" else 0.0,
    }


def _range(pitches: list, kind: str, own: Optional[dict] = None) -> float:
    lo, hi = (own or {}).get(kind) or IDEAL_RANGE.get(kind, (7, 11))
    span = max(pitches) - min(pitches)
    return 1.0 - 0.25 * max(lo - span, span - hi, 0)


def _peak(sung: list) -> float:
    """Ein klarer Höhepunkt: der höchste Ton kommt selten und mindestens einmal lang oder betont."""
    top = max(n.pitch for n in sung)
    tops = [n for n in sung if n.pitch == top]
    held = any(n.strong or n.dur >= 0.75 for n in tops)
    return (0.6 if held else -0.4) + 0.4 * (len(tops) <= 3) - 0.15 * max(len(tops) - 4, 0)


def _share_penalty(share: float, bounds: tuple) -> float:
    lo, hi = bounds
    return max(lo - share, share - hi, 0.0) * 4


def _moves(moves: list, targets: Optional[dict] = None) -> float:
    if not moves:
        return 0.0
    targets = targets or {}
    n = len(moves)
    steps = sum(1 for m in moves if 1 <= abs(m) <= 2) / n
    leaps = sum(1 for m in moves if abs(m) >= 3) / n
    repeats = sum(1 for m in moves if m == 0) / n
    return 1.0 - _share_penalty(steps, targets.get("steps", STEP_SHARE)) - \
        _share_penalty(leaps, targets.get("leaps", LEAP_SHARE)) - \
        _share_penalty(repeats, targets.get("repeats", REPEAT_SHARE))


def _runs(sung: list) -> float:
    """Minus für jede Strecke aus LONG_RUN oder mehr gleichen Tönen."""
    penalty, run = 0.0, 1
    for a, b in zip(sung, sung[1:]):
        run = run + 1 if b.pitch == a.pitch else 1
        if run >= LONG_RUN:
            penalty += 0.3
    return 1.0 - penalty


def _motif(sung: list, bar_beats: float) -> float:
    """Wie viele Takte ein Motiv singen, das in einem anderen Takt wiederkommt (Intervalle und Rhythmus)."""
    bars = {}
    for n in sung:
        bars.setdefault(int(n.start // bar_beats), []).append(n)
    shapes = []
    for notes in bars.values():
        if len(notes) < 3:
            continue
        shapes.append((tuple(round(n.start % bar_beats, 2) for n in notes),
                       tuple(b.pitch - a.pitch for a, b in zip(notes, notes[1:]))))
    if len(shapes) < 2:
        return 0.0
    repeated = sum(1 for s in shapes if shapes.count(s) > 1) / len(shapes)
    return min(repeated, 0.6) / 0.6


def _text(notes: list) -> float:
    """Lange Töne auf ん oder っ lassen sich nicht schön halten."""
    bad = sum(1 for n in notes if str(n.syllable or "") in UNHELD and n.dur >= HOLD_BEATS)
    return 1.0 - 0.5 * bad


def _recovery(moves: list) -> float:
    """Nach einem großen Sprung geht eine gute Melodie in die Gegenrichtung zurück."""
    jumps = [(a, b) for a, b in zip(moves, moves[1:]) if abs(a) >= BIG_LEAP]
    if not jumps:
        return 0.5
    return 1.0 - 0.3 * sum(1 for a, b in jumps if a * b > 0)


def _contrast(sung: list, kind: str, below: Optional[list]) -> float:
    """Der Refrain liegt höher als die Teile davor: sein höchster Ton und seine Mitte."""
    if kind != "Chorus" or not below:
        return 0.0
    mine = [n.pitch for n in sung]
    theirs = [n.pitch for n in below]
    peak = 1.0 if max(mine) > max(theirs) else -0.5 if max(mine) < max(theirs) else 0.0
    mean = sum(mine) / len(mine) - sum(theirs) / len(theirs)
    return peak + (0.5 if mean >= 1.0 else -0.3 if mean < 0 else 0.0)


def _high(sung: list, top: Optional[int]) -> float:
    """Ganz oben singt die Stimme nur kurz: zu lange dort strengt an und klingt gepresst."""
    if top is None:
        return 0.0
    total = sum(n.dur for n in sung) or 1.0
    high = sum(n.dur for n in sung if n.pitch >= top - 1) / total
    return -max(high - HIGH_SHARE, 0.0) * 4


# ── 1.5.0: wichtige Wörter (S2) und Ohrwurm (S3) ─────────────────────────────────
def _hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def words(notes: list) -> list:
    """[(Wort in Hiragana, [Töne])] in der gesungenen Reihenfolge; Partikel und Melisma gehören zum Wort davor."""
    out = []
    for n in sorted(notes, key=lambda n: n.start):
        syllable = n.syllable
        if syllable is None:
            continue
        if getattr(syllable, "melisma", False):
            if out:
                out[-1][1].append(n)
            continue
        if getattr(syllable, "word_start", False) or not out:
            out.append(["", []])
        out[-1][0] += _hiragana(str(syllable))
        out[-1][1].append(n)
    return [(text, ns) for text, ns in out]


def key_word(found: list) -> Optional[str]:
    """Das Kernwort: das häufigste Wort ab zwei Moren, das wiederkommt; sonst das erste (der Anfang der Hook)."""
    texts = [text for text, ns in found if sum(not getattr(n.syllable, "melisma", False) for n in ns) >= KEY_WORD_MORAE]
    if not texts:
        return None
    counts = {t: texts.count(t) for t in texts}
    best = max(texts, key=lambda t: (counts[t], len(t), -texts.index(t)))
    return best if counts[best] >= 2 else texts[0]


def _key_words(notes: list, kind: str) -> float:
    """S2: das Kernwort des Refrains hoch oder lang und auf der betonten Zeit, Gefühlswörter enden auf langen Tönen."""
    found = words(notes)
    sung = [n for n in notes if n.syllable is not None]
    if not found or not sung:
        return 0.0
    values = []
    if kind == "Chorus":
        key = key_word(found)
        top = max(n.pitch for n in sung)
        for text, ns in found:
            if text == key:
                lifted = any(n.pitch >= top - KEY_HIGH for n in ns) or max(n.dur for n in ns) >= KEY_LONG
                values.append(0.5 * lifted + 0.5 * bool(ns[0].strong))
    typical = sorted(n.dur for n in sung)[len(sung) // 2]
    for text, ns in found:
        if any(text.startswith(w) for w in FEELING_WORDS):
            values.append(float(ns[-1].dur >= FEELING_LONG * typical))
    return 2 * sum(values) / len(values) - 1 if values else 0.0


def phrases(sung: list) -> list:
    """Die Phrasen einer Sektion: Töne bis zur nächsten Pause ab PHRASE_GAP Schlägen."""
    out = []
    for n in sung:
        if out and n.start - (out[-1][-1].start + out[-1][-1].dur) < PHRASE_GAP:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def _likeness(a: list, b: list) -> float:
    """Wie sehr Phrase b wie Phrase a klingt: Rhythmus (Einsätze ab Phrasenanfang) und Richtung jeder Bewegung."""
    onsets_a = {round(n.start - a[0].start, 2) for n in a}
    onsets_b = {round(n.start - b[0].start, 2) for n in b}
    rhythm = len(onsets_a & onsets_b) / max(len(onsets_a | onsets_b), 1)
    sign = lambda x: (x > 0) - (x < 0)          # noqa: E731
    dirs_a = [sign(y.pitch - x.pitch) for x, y in zip(a, a[1:])]
    dirs_b = [sign(y.pitch - x.pitch) for x, y in zip(b, b[1:])]
    length = max(len(dirs_a), len(dirs_b), 1)
    contour = sum(x == y for x, y in zip(dirs_a, dirs_b)) / length
    return (rhythm + contour) / 2


def _catchy(sung: list) -> float:
    """S3: die erste Phrase kommt mit kleiner Veränderung wieder (ganz gleich ist gut, leicht verändert besser), und
    das Anfangsmotiv (die ersten vier Bewegungen) kehrt in derselben Gestalt zurück, gern auf anderer Höhe."""
    found = [p for p in phrases(sung) if len(p) >= 3]
    if len(found) < 2:
        return 0.0
    best = max(_likeness(found[0], p) for p in found[1:])
    phrase = 1.0 if 0.6 <= best < 0.999 else 0.6 if best >= 0.999 else 0.0 if best >= 0.4 else -0.5
    opening = [b.pitch - a.pitch for a, b in zip(sung[:5], sung[1:5])]
    moves = [b.pitch - a.pitch for a, b in zip(sung, sung[1:])]
    later = range(len(found[0]), len(moves) - len(opening) + 1)
    hook = 1.0 if len(opening) == 4 and any(moves[i:i + 4] == opening for i in later) else 0.0
    return 0.7 * phrase + 0.3 * hook


def pick(candidates: list, kind: str, below: Optional[list] = None, top: Optional[int] = None,
         bar_beats: float = 4, targets: Optional[dict] = None, extras=()) -> tuple:
    """Die beste Fassung: (Index, Punkte, Schnitt aller Fassungen). candidates: Listen von MelNotes."""
    scores = [score(c, kind, below, top, bar_beats, targets, extras) for c in candidates]
    best = max(range(len(scores)), key=lambda i: (scores[i], -i))
    return best, scores[best], sum(scores) / len(scores)
