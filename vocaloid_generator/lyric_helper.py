# lyric_helper.py – Text-Helfer Zeile für Zeile (v6 Nr. 12)
#
# Zeigt beim Schreiben, wie eine Zeile gesungen wird, ohne KI: wie viele Silben (Moren) sie hat und wie viele in eine
# Phrase der Melodie bequem passen (rot, wenn es zu viele sind), auf welchem Vokal sie endet (gleicher Endvokal =
# Reim, A/B wie im Reimschema) und wie Kanji gelesen werden. Der Platz rechnet wie melody_writer.allocate: Tempo,
# Takte der Sektion, Silben pro Sekunde je Sektionsart.
import re
from dataclasses import dataclass, field
from typing import Optional

import config
from lyrics import (_HEADER, _KANJI, OCCURRENCE, changes, is_translation, kind_of, normalize_section, options,
                    syllables, vowel)
from melody_writer import SINGING_SHARE, SYLLABLES_PER_SECOND, max_syllables, phrase_bars_for
from song_plan import SLOW_BPM

FAST = 1.3                  # so viel mehr als bequem: schnell gesungen
FEW = 0.35                  # weniger als dieser Anteil: lange Töne
RHYME_LETTERS = "ABCDEFGH"


@dataclass
class Line:
    text: str                       # wie geschrieben
    sung: list                      # Silben, wie gesungen
    room: int = 0                   # so viele passen bequem in eine Phrase
    most: int = 0                   # mehr passen gar nicht hinein
    rhyme: str = ""                 # Endvokal (あ, い, う, え, お, ん)
    letter: str = ""                # Reimschema in der Sektion
    reading: str = ""               # Lesung, wenn Kanji darin sind
    unread: bool = False            # Kanji, die nicht gelesen werden konnten
    changes: list = field(default_factory=list)     # [(geschrieben, gesungen)]: Partikel, Zahlwörter, Lesungen.txt

    @property
    def count(self) -> int:
        return sum(1 for s in self.sung if not getattr(s, "melisma", False))

    @property
    def status(self) -> str:
        """„zu viel“ (passt nicht in eine Phrase), „schnell“, „wenig“ oder „gut“."""
        if self.most and self.count > self.most:
            return "zu viel"
        if self.room and self.count > FAST * self.room:
            return "schnell"
        if self.room and self.count < FEW * self.room:
            return "wenig"
        return "gut"

    def describe(self) -> str:
        n = f"{self.count} Silbe" + ("" if self.count == 1 else "n")
        text = {"zu viel": f"{n}: zu viele für ihre Phrase (höchstens {self.most})",
                "schnell": f"{n}: wird schnell gesungen (bequem bis {self.room})",
                "wenig": f"{n}: lange Töne (Platz für etwa {self.room})",
                "gut": f"{n} (Platz für etwa {self.room})"}[self.status]
        return text if self.room else n


@dataclass
class Section:
    name: str
    kind: str
    bars: int = 0
    lines: list = field(default_factory=list)
    phrases: int = 0                # so viele Phrasen singt die Melodie in der Sektion
    longer: int = 0                 # so viele Takte braucht der Text, wenn es mehr als bars sind
    unused: str = ""                # 1.11.0: warum dieser Text nicht gesungen wird (die Sektion fehlt im Ablauf)

    def note(self) -> str:
        """Was mit dem Text als Ganzes passiert; leer, wenn Zeilen und Phrasen zusammenpassen."""
        if self.unused:
            return self.unused
        if self.longer:
            return f"Der Text braucht {self.longer} statt {self.bars} Takte, die Sektion wird länger."
        if self.phrases and len(self.lines) < self.phrases:
            lines = f"{len(self.lines)} Zeile" + ("" if len(self.lines) == 1 else "n")
            return f"{self.phrases} Phrasen, {lines}: der Text wird wiederholt."
        if self.phrases and len(self.lines) > self.phrases:
            return f"{len(self.lines)} Zeilen auf {self.phrases} Phrasen: Zeilen teilen sich eine Phrase."
        return ""


def room(kind: str, bars: int, bpm: float, meter: str = "4/4") -> tuple:
    """(bequem, höchstens, Phrasen): Silben in einer Phrase dieser Sektion, wie melody_writer.allocate verteilt."""
    if kind not in SYLLABLES_PER_SECOND or bars <= 0:
        return 0, 0, 0
    bar_beats = 3 if meter == "3/4" else 4
    bar_steps = 12 if meter == "3/4" else 16
    pb = phrase_bars_for(bars, bpm, bar_beats)
    seconds = pb * bar_beats * 60.0 / bpm
    return (int(round(SYLLABLES_PER_SECOND[kind] * seconds * SINGING_SHARE)), max_syllables(pb, bar_steps),
            max(bars // pb, 1))


def _bars(settings, kind: str) -> int:
    """Takte der Sektion, in denen die Melodie entsteht (wie song_plan.build_plan: langsame Songs halb so viele, im
    6/8-Takt zwei 6/8-Takte pro Takt)."""
    bars = settings.section_bars.get(kind) or config.SECTION_CONFIG.get(kind, {}).get("bars", 0)
    if settings.meter == "6/8":
        return (bars + 1) // 2
    return bars // 2 if settings.bpm < SLOW_BPM and bars >= 8 else bars


def check(settings, text: Optional[str] = None) -> list:
    """[Section] mit ihren Zeilen; text: der Liedtext, sonst settings.lyrics."""
    from lyrics import _tagger
    text = settings.lyrics if text is None else text
    reading = options(settings)
    out, current = [], None
    for raw in (text or "").splitlines():
        line = raw.strip()
        header = _HEADER.match(line)
        if header:
            name = normalize_section(header.group(1))
            kind = kind_of(name)
            current = Section(name, kind, _bars(settings, kind))
            out.append(current)
            continue
        if not line or is_translation(line):          # Übersetzung fürs Video, wird nicht gesungen
            continue
        if current is None:
            current = Section("", "")
            out.append(current)
        sung = syllables(line, **reading)
        last = next((str(s) for s in reversed(sung) if not getattr(s, "melisma", False)), "")
        has_kanji = bool(_KANJI.search(line))
        current.lines.append(Line(line, sung, rhyme=vowel(last) or "",
                                  reading="".join(str(s) for s in sung) if has_kanji else "",
                                  changes=changes(line, **reading),
                                  unread=has_kanji and _tagger() is None and bool(_KANJI.search(_bare(line)))))
    for sec in out:
        sec.unused = unused(sec, settings)
        comfortable, most, sec.phrases = room(sec.kind, sec.bars, settings.bpm, settings.meter)
        share = sec.phrases / max(len(sec.lines), sec.phrases, 1)       # mehr Zeilen als Phrasen: weniger Platz
        for line in sec.lines:
            line.room, line.most = int(round(comfortable * share)), int(most * share)
        letters = {}
        for line in sec.lines:
            if line.rhyme:
                line.letter = letters.setdefault(line.rhyme, RHYME_LETTERS[min(len(letters), len(RHYME_LETTERS) - 1)])
        total = sum(line.count for line in sec.lines)
        bar_steps = 12 if settings.meter == "3/4" else 16
        bars = sec.bars
        while bars and total > max_syllables(bars, bar_steps):
            bars *= 2
        sec.longer = bars if bars != sec.bars else 0
    return out


def unused(sec: "Section", settings) -> str:
    """1.11.0: Ein Text, den der Song nicht singt, weil seine Sektion im Ablauf nicht vorkommt ([Sprechen] ohne
    Sprechteil, [Verse 3] bei zwei Strophen). Bis 1.10 fiel er still weg; im Video fehlten dann ganze Zeilen."""
    active = list(getattr(settings, "active_sections", None) or ())
    if not sec.kind or not sec.lines or not active:
        return ""
    from gui.labels import SECTIONS
    name = SECTIONS.get(sec.kind, sec.kind)
    have = active.count(sec.kind)
    number = int(sec.name.split(OCCURRENCE)[1]) if OCCURRENCE in sec.name else 1
    if not have:
        return (f"„{name}“ kommt im Ablauf nicht vor: dieser Text wird nicht gesungen. Im Tab Ablauf eine Sektion "
                f"„{name}“ dazunehmen oder den Text unter eine vorhandene Überschrift schreiben.")
    if number > 1 and not getattr(settings, "numbered_lyrics", True):
        return (f"Eigene Texte je Vorkommen sind aus: die {number}. „{name}“ singt den Text der ersten. Im Tab Text den Schalter "
                "„Eigener Text für [Verse 2], [Chorus 3] …“ einschalten.")
    if number > have:
        return (f"Der Ablauf hat nur {have}× „{name}“: der Text für die {number}. wird nicht gesungen. Im Tab Ablauf "
                "eine weitere dazunehmen.")
    return ""


def _bare(line: str) -> str:
    """Die Zeile ohne Kanji, denen eine Lesung von Hand folgt (君[きみ])."""
    from lyrics import _FURIGANA
    return _FURIGANA.sub("", line)


# ── Namensvorschlag fürs Video (1.11.0) ──────────────────────────────────────────
_TITLE_LINE = re.compile(r"^\s*(?:#+\s*|(?:titel|title|name|songname)\s*[:：=]\s*)(.+?)\s*$", re.IGNORECASE)
_TITLE_TRIM = "「」『』\"'“”„‚‘’!?！？。、,.…~〜-—♪☆★ "


def title_suggestion(text: str) -> str:
    """
    Ein Name für Titelkarte und YouTube, wenn der Song noch keinen hat: steht vor der ersten Überschrift eine Zeile
    „Titel: …“ oder „# …“, diese; sonst der Anfang der ersten Refrainzeile (der Hook, so heißen viele Vocaloid-Songs:
    „くるくる くるくる“ → „くるくる“); sonst die erste gesungene Zeile. "" ohne Text.
    1.11.0: bis 1.10 stand das Feld leer, und schnell getippt stand dann „f“ groß am Anfang des Videos.
    """
    sections, current, before = {}, None, []
    for raw in (text or "").splitlines():
        line = raw.strip()
        header = _HEADER.match(line)
        if header:
            current = kind_of(normalize_section(header.group(1)))
            sections.setdefault(current, [])
            continue
        if not line or is_translation(line):
            continue
        (sections[current] if current is not None else before).append(line)
    for line in before:
        found = _TITLE_LINE.match(line)
        if found:
            return _tidy_title(found.group(1))
    hook = (sections.get("Chorus") or [None])[0]
    if hook:
        words = hook.split()
        if words and sum(map(len, words)) <= 1.3 * len(words):      # Silbe für Silbe getrennt: „い ま う た う“
            words = ["".join(words)]
        first = _tidy_title(words[0]) if words else ""
        if len(first) >= 2 and len(set(words)) < len(words):      # ein wiederholter Hook: einmal reicht
            return first
        return _tidy_title(" ".join(words))
    first_line = next((lines[0] for lines in sections.values() if lines), "")
    return _tidy_title(first_line)


def _tidy_title(text: str, most: int = 24) -> str:
    from lyrics import _FURIGANA
    text = _FURIGANA.sub(lambda m: m.group(1), text).strip(_TITLE_TRIM)
    return text if len(text) <= most else text[:most].rstrip() + "…"


def unused_notes(settings) -> list:
    """1.11.0: die Hinweise zu Texten, die der Ablauf nicht singt (unused), ohne den Rest der Prüfung (schnell, auch
    ohne Wörterbuch): eine Zeile je Abschnitt."""
    out, current = [], None
    for raw in (getattr(settings, "lyrics", "") or "").splitlines():
        line = raw.strip()
        header = _HEADER.match(line)
        if header:
            name = normalize_section(header.group(1))
            current = Section(name, kind_of(name))
            out.append(current)
        elif line and not is_translation(line) and current is not None:
            current.lines.append(line)
    return [note for note in (unused(sec, settings) for sec in out) if note]
