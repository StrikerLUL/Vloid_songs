# lyrics.py – Liedtext aus der App in Silben pro Sektion zerlegen
#
# Japanischer Text darf ohne Leerzeichen und mit Kanji kommen: fugashi (MeCab mit UniDic) liefert die
# Lesung, danach wird in Moren zerlegt, also in das, was auf eine Note gesungen wird (きゃ, っ, ん, ー).
# UniDic kennt auch den Tonhöhenakzent jedes Worts (Tokio): jede More merkt sich, ob sie hoch oder tief
# gesprochen wird, damit die Melodie den Wörtern folgen kann.
import functools
import logging
import re

# Schreibweisen der Sektions-Überschriften, die auf den internen Namen zeigen
_SECTION_ALIASES = {
    "verse": "Verse",
    "prechorus": "PreChorus",
    "pre-chorus": "PreChorus",
    "pre chorus": "PreChorus",
    "chorus": "Chorus",
    "bridge": "Bridge",
    "intro": "Intro",
    "outro": "Outro",
    "build-up": "Build-up",
    "buildup": "Build-up",
    "drop": "Drop",
}

_HEADER = re.compile(r"^\[(.+)\]$")
_JAPANESE = re.compile(r"[\u3041-\u30ff\u4e00-\u9fff々〆]")
_KANJI = re.compile(r"[\u4e00-\u9fff々〆]")
# Lesung von Hand vorgeben: 君[きみ] oder 君［きみ］
_FURIGANA = re.compile(r"([\u4e00-\u9fff々〆]+)[\[［]([\u3041-\u30ffー]+)[\]］]")
_SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
# Partikel werden anders gesungen als geschrieben
_PARTICLES = {"は": "わ", "へ": "え", "を": "お"}
# Langer Vokal „ー“ wird als eigener Vokal gesungen: ろー → ろ お
_VOWELS = {v: k for k, row in {"あ": "あかさたなはまやらわがざだばぱぁゃゎ", "い": "いきしちにひみりぎじぢびぴぃ",
                               "う": "うくすつぬふむゆるぐずづぶぷぅゅゔ", "え": "えけせてねへめれげぜでべぺぇ",
                               "お": "おこそとのほもよろをごぞどぼぽぉょ"}.items() for v in row}

log = logging.getLogger(__name__)
_FUNCTION_WORDS = ("助詞", "助動詞")


class Mora(str):
    """
    Eine gesungene Silbe, die sich wie ein normaler String verhält.
    tone: "H" oder "L" im Tonhöhenakzent (None = unbekannt), word_start: erste More eines Worts,
    melisma: keine neue Silbe, sondern der Vokal der vorigen auf einem neuen Ton.
    """

    def __new__(cls, text: str, tone=None, word_start: bool = False, melisma: bool = False):
        obj = super().__new__(cls, text)
        obj.tone, obj.word_start, obj.melisma = tone, word_start, melisma
        return obj

    def __reduce__(self):
        return Mora, (str(self), self.tone, self.word_start, self.melisma)


def normalize_section(name: str) -> str:
    """'[Pre-Chorus]' und 'prechorus' werden beide zu 'PreChorus'."""
    key = name.strip().lower()
    return _SECTION_ALIASES.get(key, name.strip())


def parse_lyrics(text: str) -> dict:
    """
    Zerlegt den Lyrics-Text der App in {Sektion: [Silben]}.
    Format: eine Überschrift wie [Verse] pro Sektion, darunter Silben mit Leerzeichen getrennt.
    Text vor der ersten Überschrift wird ignoriert.
    """
    return {name: [s for line in lines for s in line] for name, lines in section_lines(text).items()}


def section_lines(text: str) -> dict:
    """{Sektion: [[Silben einer Zeile], ...]}: wie parse_lyrics, aber Zeile für Zeile (für den Text zum Mitlesen)."""
    sections = {}
    current = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        header = _HEADER.match(line)
        if header:
            current = normalize_section(header.group(1))
            sections.setdefault(current, [])
        elif current and line:
            sung = syllables(line)
            if sung:
                sections[current].append(sung)
    return {name: lines for name, lines in sections.items() if lines}


def syllables(line: str) -> list:
    """
    Eine Textzeile als Silben zum Singen. Japanisch wird in Moren zerlegt, ob mit Leerzeichen oder ohne,
    Kanji werden vorher gelesen. Wörter ohne japanische Schrift bleiben ganz (wie bisher).
    """
    tokens = line.split()
    if len(tokens) > 1 and all(_JAPANESE.search(t) and not _KANJI.search(t) for t in tokens):
        # Kana mit Leerzeichen zwischen den Silben (よ る の ま ち): als ganzen Satz lesen, damit die Wörter
        # und ihr Akzent erkannt werden; die Silben bleiben genau so, wie sie dastehen
        spaced = [m for t in tokens for m in morae(to_kana(t))]
        whole = accented_morae("".join(tokens))
        if [str(m) for m in whole] == spaced:
            return whole
    out = []
    for token in tokens:
        if _JAPANESE.search(token):
            out += accented_morae(token)
        else:
            out.append(token)
    return out


def accented_morae(text: str) -> list:
    """
    Moren mit Tonhöhenakzent: 君の声 → き(L) み(H) の(H) こ(H) え(L). Wörter beginnen mit word_start,
    Partikel bleiben auf der Höhe, die das Wort davor ihnen lässt. Ohne Wörterbuch nur die Moren.
    """
    out, flat_before = [], False
    for reading, pos1, accent in _words(text):
        ms = morae(reading)
        if not ms:
            continue
        if pos1 in _FUNCTION_WORDS:
            level = ("H" if flat_before else "L") if out and out[-1].tone else None
            out += [Mora(m, level) for m in ms]
            continue
        tones = _tones(len(ms), accent) if len(ms) > 1 or accent is not None else [None]
        out += [Mora(m, t, word_start=i == 0) for i, (m, t) in enumerate(zip(ms, tones))]
        flat_before = accent == 0
    return out


def _tones(n: int, accent) -> list:
    """Hoch/tief jeder More eines Worts mit n Moren; accent = Position des Akzentkerns (0 = flach)."""
    if accent is None:
        return [None] * n
    if accent == 1:
        return ["H"] + ["L"] * (n - 1)
    return ["L"] + ["H" if accent == 0 or i < accent else "L" for i in range(1, n)]


def vowel(syllable: str):
    """Der Vokal, auf dem eine Silbe weiterklingt (か → あ, きゃ → あ, ん → ん); None bei っ und Fremdwörtern."""
    if not syllable or syllable[-1] == "っ":
        return None
    if syllable[-1] == "ん":
        return "ん"
    return _VOWELS.get(syllable[-1])


def morae(kana: str) -> list:
    """'きゃっとー' → ['きゃ', 'っ', 'と', 'お']; alles außer Kana fällt weg."""
    out = []
    for ch in _hiragana(kana):
        if ch in _SMALL and out:
            out[-1] += ch
        elif "\u3041" <= ch <= "\u3096":
            out.append(ch)
        elif ch == "ー" and out and out[-1][-1] in _VOWELS:
            out.append(_VOWELS[out[-1][-1]])
    return out


def to_kana(text: str) -> str:
    """Japanischer Text als Hiragana so, wie er gesungen wird (Partikel は → わ). Reine Kana bleiben, wie sie sind."""
    text = _FURIGANA.sub(lambda m: m.group(2), text)
    if not _KANJI.search(text):
        return _hiragana(text)
    if _tagger() is None:
        return _hiragana(_KANJI.sub("", text))
    return "".join(reading for reading, _, _ in _words(text))


def _words(text: str) -> list:
    """[(Lesung in Hiragana, Wortart, Akzentkern oder None)] eines japanischen Texts."""
    text = _FURIGANA.sub(lambda m: m.group(2), text)
    tagger = _tagger()
    if tagger is None:
        return [(_hiragana(_KANJI.sub("", text)), "", None)]
    as_written = not _KANJI.search(text)        # reine Kana: so singen, wie geschrieben
    out = []
    for word in tagger(text):
        reading = getattr(word.feature, "kana", None)
        if as_written or not reading or reading == "*":
            reading = word.surface if _JAPANESE.search(word.surface) else ""
        reading = _hiragana(reading)
        pos1 = getattr(word.feature, "pos1", "")
        if pos1 == "助詞" and reading in _PARTICLES and not as_written:
            reading = _PARTICLES[reading]
        out.append((reading, pos1, _accent(getattr(word.feature, "aType", None))))
    return out


def _accent(value):
    """UniDic-Akzent wie "1" oder "2,0" → 1 bzw. 2; "*" → None."""
    first = str(value or "").split(",")[0]
    return int(first) if first.isdigit() else None


def _hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


@functools.lru_cache(maxsize=1)
def _tagger():
    try:
        import fugashi
        return fugashi.Tagger()
    except Exception as e:                       # fehlendes Wörterbuch oder fugashi nicht installiert
        log.warning("Kanji können nicht gelesen werden (%s); bitte den Text in Hiragana schreiben", e)
        return None
