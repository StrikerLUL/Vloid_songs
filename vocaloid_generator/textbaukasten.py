# textbaukasten.py – Text-Baukasten ohne KI (1.6.0)
#
# Setzt aus den von Hand geschriebenen Zeilen in textbausteine.py einen japanischen Liedtext zusammen: Thema,
# Stimmung und ein Titelwort wählen, den Rest macht die App. Jede Sektion des Ablaufs bekommt so viele Zeilen, wie
# ihre Melodie Phrasen singt, und jede Zeile ungefähr so viele Silben, wie bequem in eine Phrase passen (dieselbe
# Rechnung wie der Text-Helfer, lyric_helper.room). Zeilenenden reimen auf den Vokal (Strophe ABAB, Pre-Chorus und
# Bridge AA, im Refrain die beiden mittleren Zeilen), der Refrain beginnt und endet mit dem Titelwort, jede Strophe
# hat ihren eigenen Text ([Verse 2]) und unter jeder Zeile steht die deutsche Übersetzung (> …) fürs Video.
# Jede Zeile lässt sich einzeln gegen eine andere tauschen (swap).
import random
from dataclasses import dataclass, field, replace
from typing import Optional

import textbausteine
from lyric_helper import _bars, room
from lyrics import _JAPANESE, morae, vowel

ROLES = {"Verse": "V", "PreChorus": "P", "Chorus": "C", "Bridge": "B"}
HEADERS = {"Verse": "Verse", "PreChorus": "Pre-Chorus", "Chorus": "Chorus", "Bridge": "Bridge"}
MOODS = {"hell": ("h", "n"), "bittersüß": ("n", "h", "d"), "traurig": ("d", "n")}
SHORTEST, LONGEST = 9, 17          # so lang dürfen Zeilen werden (Silben), auch wenn die Phrase mehr Platz hat
MOST_LINES = 8


@dataclass(frozen=True)
class Zeile:
    role: str                       # V, P, C, B oder H (Hook mit {} für das Titelwort)
    mood: str                       # h, n oder d
    text: str                       # wie im Liedtext (Kanji, Kana, Lesungen von Hand wie 既読[きどく])
    kana: str                       # wie gesungen
    german: str
    theme: str = ""

    @property
    def sung(self) -> list:
        return [m for m in morae(self.kana) if not getattr(m, "melisma", False)]

    @property
    def count(self) -> int:
        return len(self.sung)

    @property
    def rhyme(self) -> str:
        return vowel(self.sung[-1]) or "" if self.sung else ""

    @property
    def romaji(self) -> str:
        from karaoke import _kana_romaji
        return " ".join(_kana_romaji(chunk) for chunk in self.kana.split())

    def fill(self, hook: "Titelwort") -> "Zeile":
        return replace(self, text=self.text.replace("{}", hook.text), kana=self.kana.replace("{}", hook.kana),
                       german=self.german.replace("{}", hook.german))


@dataclass(frozen=True)
class Titelwort:
    text: str
    kana: str
    german: str


@dataclass
class Teil:
    """Eine Sektion des Songs mit ihren Zeilen."""
    kind: str
    number: int                     # das wievielte Vorkommen (1: [Verse], 2: [Verse 2])
    target: int                     # so viele Silben passen bequem in eine Phrase
    lines: list = field(default_factory=list)
    shared: int = 1                 # so oft singt der Song diesen Text (Refrain)

    @property
    def header(self) -> str:
        name = HEADERS[self.kind]
        return f"[{name} {self.number}]" if self.number > 1 else f"[{name}]"


@dataclass
class Liedtext:
    theme: str
    mood: str
    hook: Titelwort
    parts: list = field(default_factory=list)
    seed: int = 0

    def text(self) -> str:
        out = []
        for part in self.parts:
            out.append(part.header)
            for line in part.lines:
                out += [line.text, f"> {line.german}"]
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def used(self) -> set:
        return {line.text for part in self.parts for line in part.lines if line is not None}


def _parse(block: str, theme: str = "") -> list:
    out = []
    for raw in block.strip().splitlines():
        head, kana, german = (x.strip() for x in raw.split("|"))
        role, mood, text = head.split(" ", 2)
        out.append(Zeile(role, mood, text.strip(), kana, german, theme))
    return out


LINES = {theme: _parse(block, theme) for theme, block in textbausteine.LINES.items()}
HOOK_LINES = _parse(textbausteine.HOOKS)
TITLE_WORDS = {theme: [Titelwort(*(x.strip() for x in raw.split("|"))) for raw in block.strip().splitlines()]
               for theme, block in textbausteine.TITLE_WORDS.items()}
THEMES = textbausteine.THEMES


def count() -> int:
    """So viele Bausteine hat der Kasten: Zeilen, Hook-Zeilen und Titelwörter."""
    return sum(map(len, LINES.values())) + len(HOOK_LINES) + sum(map(len, TITLE_WORDS.values()))


def title_word(word: str, german: str = "") -> Optional[Titelwort]:
    """Das Titelwort zu einer Eingabe: ein Titelwort der Liste (japanisch oder deutsch geschrieben) oder ein eigenes
    japanisches Wort; None, wenn es keins von beiden ist (ein deutsches Wort, das nicht in der Liste steht)."""
    word = word.strip()
    if not word:
        return None
    for words in TITLE_WORDS.values():
        for known in words:
            if word in (known.text, plain(known.text), known.kana) or word.lower() == known.german.lower():
                return known
    if not _JAPANESE.search(word):
        return None
    from lyrics import to_kana
    return Titelwort(word, to_kana(word), german.strip() or word)


def plain(text: str) -> str:
    """Ohne Lesungen von Hand: 既読[きどく] → 既読."""
    from lyrics import _FURIGANA
    return _FURIGANA.sub(lambda m: m.group(1), text)


def plan(settings) -> list:
    """[Teil] ohne Zeilen: die gesungenen Sektionen des Ablaufs, jede Strophe, jeder Pre-Chorus und jede Bridge mit
    eigenem Text (wenn „Eigener Text für [Verse 2]“ an ist), der Refrain einmal für alle Wiederholungen."""
    seen, out, chorus = {}, [], None
    for kind in settings.active_sections:
        if kind not in ROLES:
            continue
        seen[kind] = seen.get(kind, 0) + 1
        if kind == "Chorus" and chorus is not None:
            chorus.shared += 1
            continue
        if seen[kind] > 1 and not settings.numbered_lyrics:
            continue
        comfortable, _, phrases = room(kind, _bars(settings, kind), settings.bpm, settings.meter)
        part = Teil(kind, seen[kind] if kind != "Chorus" else 1, min(max(comfortable, SHORTEST), LONGEST))
        part.lines = [None] * min(max(phrases, 2), MOST_LINES)
        out.append(part)
        if kind == "Chorus":
            chorus = part
    return out


def _partner(part: Teil, index: int) -> Optional[int]:
    """Mit welcher Zeile diese reimen soll: Strophe ABAB, Pre-Chorus und Bridge AABB, im Refrain die Zeilen zwischen
    den beiden Hooks paarweise."""
    n = len(part.lines)
    if part.kind == "Chorus":
        if index in (0, n - 1):
            return None
        inner = index - 1
        mate = 1 + (inner + 1 if inner % 2 == 0 else inner - 1)
        return mate if 0 < mate < n - 1 else None
    mate = (index + 2 if index % 4 < 2 else index - 2) if part.kind == "Verse" and n >= 4 else \
        (index + 1 if index % 2 == 0 else index - 1)
    return mate if 0 <= mate < n else None


def _is_hook(part: Teil, index: int) -> bool:
    return part.kind == "Chorus" and (index == 0 or (index == len(part.lines) - 1 and len(part.lines) >= 3))


def _pool(song: Liedtext, part: Teil, index: int) -> list:
    if _is_hook(part, index):
        return [h.fill(song.hook) for h in HOOK_LINES]
    role = ROLES[part.kind]
    return [line for line in LINES[song.theme] if line.role == role]


def _score(line: Zeile, song: Liedtext, part: Teil, index: int, rng: random.Random) -> float:
    moods = MOODS[song.mood]
    cost = abs(line.count - part.target)
    cost += 0 if line.mood == moods[0] else (1.5 if line.mood in moods else 6)
    mate = _partner(part, index)
    other = part.lines[mate] if mate is not None else None
    if other is not None and line.rhyme != other.rhyme:
        cost += 3
    return cost + rng.random() * 2.5


def _pick(song: Liedtext, part: Teil, index: int, rng: random.Random, avoid: set) -> Zeile:
    pool = [line for line in _pool(song, part, index) if line.text not in avoid] or _pool(song, part, index)
    return min(pool, key=lambda line: _score(line, song, part, index, rng))


def build(settings, theme: str, mood: str = "bittersüß", hook: Optional[Titelwort] = None,
          seed: Optional[int] = None) -> Liedtext:
    """Ein ganzer Liedtext für den Ablauf in settings; ohne Titelwort nimmt die App eins des Themas."""
    seed = random.randrange(1 << 30) if seed is None else seed
    rng = random.Random(seed)
    hook = hook or rng.choice(TITLE_WORDS[theme])
    song = Liedtext(theme, mood, hook, plan(settings), seed)
    for part in song.parts:
        for index in range(len(part.lines)):
            avoid = song.used()
            if part.kind == "Chorus" and index == len(part.lines) - 1 and part.lines[0] is not None:
                avoid.add(part.lines[0].text)       # zweite Hook-Zeile anders als die erste
            part.lines[index] = _pick(song, part, index, rng, avoid)
    return song


def swap(song: Liedtext, part_index: int, line_index: int, rng: Optional[random.Random] = None) -> Zeile:
    """Tauscht eine Zeile gegen eine andere, die genauso gut passt (Länge, Reim, Stimmung) und noch nicht vorkommt."""
    rng = rng or random.Random()
    part = song.parts[part_index]
    current = part.lines[line_index]
    avoid = song.used() | {current.text}
    part.lines[line_index] = _pick(song, part, line_index, rng, avoid)
    return part.lines[line_index]


def check(song: Liedtext, settings) -> list:
    """[(Zeile, gelesen)] für Zeilen, die die App anders singen würde, als der Baukasten sie meint (nur bei einem
    eigenen Titelwort oder eigenen Lesungen in Lesungen.txt möglich; test_textbau_160 prüft alle Bausteine)."""
    from lyrics import options, syllables
    reading = options(settings)
    out = []
    for part in song.parts:
        for line in part.lines:
            sung = [str(s) for s in syllables(line.text, **reading) if not getattr(s, "melisma", False)]
            if [_same(s) for s in sung] != [_same(s) for s in line.sung]:
                out.append((line, " ".join(sung)))
    return out


def _same(mora: str) -> str:
    return "お" if mora == "を" else str(mora)
