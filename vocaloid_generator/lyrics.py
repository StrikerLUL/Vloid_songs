# lyrics.py – Liedtext aus der App in Silben pro Sektion zerlegen
#
# Japanischer Text darf ohne Leerzeichen und mit Kanji kommen: fugashi (MeCab mit UniDic) liefert die
# Lesung, danach wird in Moren zerlegt, also in das, was auf eine Note gesungen wird (きゃ, っ, ん, ー).
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
    sections = {}
    current = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        header = _HEADER.match(line)
        if header:
            current = normalize_section(header.group(1))
            sections.setdefault(current, [])
        elif current and line:
            sections[current].extend(syllables(line))
    return {name: sylls for name, sylls in sections.items() if sylls}


def syllables(line: str) -> list:
    """
    Eine Textzeile als Silben zum Singen. Japanisch wird in Moren zerlegt, ob mit Leerzeichen oder ohne,
    Kanji werden vorher gelesen. Wörter ohne japanische Schrift bleiben ganz (wie bisher).
    """
    out = []
    for token in line.split():
        if _JAPANESE.search(token):
            out += morae(to_kana(token))
        else:
            out.append(token)
    return out


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
    tagger = _tagger()
    if tagger is None:
        return _hiragana(_KANJI.sub("", text))
    out = []
    for word in tagger(text):
        reading = getattr(word.feature, "kana", None)
        if not reading or reading == "*":
            reading = word.surface if _JAPANESE.search(word.surface) else ""
        reading = _hiragana(reading)
        if getattr(word.feature, "pos1", "") == "助詞" and reading in _PARTICLES:
            reading = _PARTICLES[reading]
        out.append(reading)
    return "".join(out)


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
