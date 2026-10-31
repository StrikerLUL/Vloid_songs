# lyrics.py – Liedtext aus der App in Silben pro Sektion zerlegen
#
# Japanischer Text darf ohne Leerzeichen und mit Kanji kommen: fugashi (MeCab mit UniDic) liefert die
# Lesung, danach wird in Moren zerlegt, also in das, was auf eine Note gesungen wird (きゃ, っ, ん, ー).
# UniDic kennt auch den Tonhöhenakzent jedes Worts (Tokio): jede More merkt sich, ob sie hoch oder tief
# gesprochen wird, damit die Melodie den Wörtern folgen kann.
# Romaji (kimi no koe) wird mit jaconv zu Hiragana, wenn die ganze Zeile aus Romaji besteht oder neben japanischer
# Schrift steht. Englische Wörter (love, baby) werden zu Katakana, so wie man sie in J-Pop singt (ラブ, ベイビー):
# erst eine kleine Liste typischer Song-Wörter, dann das Wörterbuch von alkana, dann das Modell von e2k. NEUTRINO kann
# kein Englisch singen. Ohne diesen Schalter bleiben sie, wie sie sind.
# Mit „Partikel erkennen“ (1.3.0, G6) werden は, へ und を auch in reinen Kana wie Partikel gesungen (わ, え, お), und
# Zahlwörter wie 一回 klingen richtig (readings.py); eigene Lesungen aus Lesungen.txt gelten immer.
import functools
import logging
import re

# Schreibweisen der Sektions-Überschriften, die auf den internen Namen zeigen
_SECTION_ALIASES = {
    "verse": "Verse",
    "strophe": "Verse",
    "prechorus": "PreChorus",
    "pre-chorus": "PreChorus",
    "pre chorus": "PreChorus",
    "pre-refrain": "PreChorus",
    "vorrefrain": "PreChorus",
    "chorus": "Chorus",
    "refrain": "Chorus",
    "bridge": "Bridge",
    "intro": "Intro",
    "outro": "Outro",
    "build-up": "Build-up",
    "buildup": "Build-up",
    "drop": "Drop",
    "rap": "Rap",
    "sprechteil": "Rap",
    "sprechen": "Spoken",
    "gesprochen": "Spoken",
    "spoken": "Spoken",
}

_HEADER = re.compile(r"^\[(.+)\]$")
# Übersetzung zum Mitlesen im Video (1.5.0 V2): eine Zeile mit > darunter, wird nicht gesungen
TRANSLATION = re.compile(r"^\s*[>＞]\s?(.*)$")
# „[Verse 2]“, „[Chorus 3]“, „[2. Strophe]“: der Text nur für dieses Vorkommen der Sektion (Schlüssel „Verse#2“)
_NUMBER_AFTER = re.compile(r"^(.*\D)\s*(\d+)$")
_NUMBER_BEFORE = re.compile(r"^(\d+)\.?\s*(\D.*)$")
OCCURRENCE = "#"
_JAPANESE = re.compile(r"[\u3041-\u30ff\u4e00-\u9fff々〆]")
_KANJI = re.compile(r"[\u4e00-\u9fff々〆]")
# Lesung von Hand vorgeben: 君[きみ] oder 君［きみ］
_KATAKANA_WORD = re.compile(r"[\u30a1-\u30faー]+")
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
# Ein Wort in Romaji (Hepburn): Silben aus Konsonant und Vokal, ん als n oder n', verdoppelte Konsonanten für っ
_ROMAJI = re.compile(r"^(?:(?:[kgsztdnhbpmr]y?|sh|ch|j|ts|f|v)?[aiueo]|y[auo]|w[ao]|n'?(?![aiueoy])|n'"
                     r"|([kgsztdhbpmrjfc])(?=\1)|t(?=ch))+$")
_LATIN = re.compile(r"[A-Za-zāīūēōâîûêô]")
_MACRONS = str.maketrans({"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ee", "ō": "ou",
                          "â": "aa", "î": "ii", "û": "uu", "ê": "ee", "ô": "ou"})
_PUNCTUATION = ",.!?;:\"()[]「」、。…~〜-"


class Mora(str):
    """
    Eine gesungene Silbe, die sich wie ein normaler String verhält.
    tone: "H" oder "L" im Tonhöhenakzent (None = unbekannt), word_start: erste More eines Worts,
    melisma: keine neue Silbe, sondern der Vokal der vorigen auf einem neuen Ton.
    long (1.7.0): das Melisma steht als „ー“ im Text (パスワード), zählt also in der Zeile wie geschrieben mit; ein
    Melisma, das erst die Melodie dazuschreibt, steht nicht im Text.
    """

    def __new__(cls, text: str, tone=None, word_start: bool = False, melisma: bool = False, long: bool = False):
        obj = super().__new__(cls, text)
        obj.tone, obj.word_start, obj.melisma, obj.long = tone, word_start, melisma, long
        return obj

    def __reduce__(self):
        return Mora, (str(self), self.tone, self.word_start, self.melisma, self.long)


def normalize_section(name: str) -> str:
    """'[Pre-Chorus]' und 'prechorus' werden beide zu 'PreChorus'. Mit Nummer ('[Verse 2]', '[2. Strophe]') gilt der
    Text nur für dieses Vorkommen: 'Verse#2'; '[Verse 1]' ist derselbe Text wie '[Verse]'."""
    text = name.strip()
    number = 1
    after, before = _NUMBER_AFTER.match(text), _NUMBER_BEFORE.match(text)
    if after:
        text, number = after.group(1).strip(), int(after.group(2))
    elif before:
        number, text = int(before.group(1)), before.group(2).strip()
    kind = _SECTION_ALIASES.get(text.lower(), text)
    return f"{kind}{OCCURRENCE}{number}" if number > 1 else kind


def for_occurrence(lyrics: dict, kind: str, number: int):
    """Der eigene Text des number-ten Vorkommens einer Sektionsart ('[Verse 2]'); None, wenn es keinen hat."""
    return lyrics.get(f"{kind}{OCCURRENCE}{number}") if number > 1 else None


def kind_of(key: str) -> str:
    """'Verse#2' → 'Verse'."""
    return key.split(OCCURRENCE)[0]


def shared_only(lyrics: dict) -> dict:
    """Ohne die Texte einzelner Vorkommen ('Verse#2'): jede Wiederholung singt den Text des ersten (wie bis 1.1)."""
    return {key: value for key, value in lyrics.items() if OCCURRENCE not in key}


def options(settings) -> dict:
    """Wie der Text der Einstellungen gelesen wird, als Schlüsselwörter für parse_lyrics, section_lines und syllables."""
    import readings
    return {"romaji": settings.romaji, "english": settings.english_kana,
            "smart": settings.smart_readings and readings.ACTIVE, "own": readings.own_readings()}


def parse_lyrics(text: str, romaji: bool = True, english: bool = False, smart: bool = False,
                 own: dict = None) -> dict:
    """
    Zerlegt den Lyrics-Text der App in {Sektion: [Silben]}.
    Format: eine Überschrift wie [Verse] pro Sektion, darunter Silben mit Leerzeichen getrennt.
    Text vor der ersten Überschrift wird ignoriert. english: englische Wörter als Katakana singen. smart: Partikel und
    Zahlwörter erkennen, own: eigene Lesungen {Wort: Lesung} (readings.py).
    """
    return {name: [s for line in lines for s in line]
            for name, lines in section_lines(text, romaji, english, smart, own).items()}


def section_lines(text: str, romaji: bool = True, english: bool = False, smart: bool = False,
                  own: dict = None) -> dict:
    """{Sektion: [[Silben einer Zeile], ...]}: wie parse_lyrics, aber Zeile für Zeile (für den Text zum Mitlesen)."""
    return {name: [sung for _, sung, _ in lines]
            for name, lines in sung_lines(text, romaji, english, smart, own).items()}


def sung_lines(text: str, romaji: bool = True, english: bool = False, smart: bool = False,
               own: dict = None) -> dict:
    """{Sektion: [(Zeile wie geschrieben, [Silben], Übersetzung oder "")]}: die gesungenen Zeilen mit ihrem Text fürs
    Video. Eine Zeile mit > direkt darunter ist ihre Übersetzung; sie wird nicht gesungen."""
    sections = {}
    current = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        header = _HEADER.match(line)
        translated = TRANSLATION.match(line)
        if header:
            current = normalize_section(header.group(1))
            sections.setdefault(current, [])
        elif translated:
            if current and sections[current] and not sections[current][-1][2]:
                written, sung, _ = sections[current][-1]
                sections[current][-1] = (written, sung, translated.group(1).strip())
        elif current and line:
            sung = syllables(line, romaji, english, smart, own)
            if sung:
                sections[current].append((line, sung, ""))
    return {name: lines for name, lines in sections.items() if lines}


def is_translation(line: str) -> bool:
    return bool(TRANSLATION.match(line))


def shown(line: str) -> str:
    """Eine Zeile so, wie sie im Video steht: ohne Lesungen von Hand (君[きみ] → 君), Kana mit Leerzeichen zwischen
    den Silben (よ る の) zusammengezogen, Wörter mit einem Leerzeichen getrennt."""
    line = _FURIGANA.sub(lambda m: m.group(1), line.strip())
    tokens = line.split()
    if len(tokens) > 2 and all(len(morae(t)) == 1 and _JAPANESE.search(t) for t in tokens):
        return "".join(tokens)
    return " ".join(tokens)


def shown_parts(line: str) -> list:
    """[(Stück, Moren)]: die Zeile wie im Video (shown) in Wörtern, jedes mit so vielen Moren, wie es gesungen
    ungefähr dauert. Das Video färbt danach Wort für Wort im Takt der Silben. Ohne Wörterbuch zählt jedes Zeichen:
    Kana eine More (kleine keine), Kanji zwei, lateinische Buchstaben eine halbe."""
    text = shown(line)
    tagger = _tagger()
    parts = []
    if tagger is not None and _JAPANESE.search(text):
        pos, before = 0, ""
        for word in tagger(text):
            at = text.find(word.surface, pos)
            if at < 0:
                continue
            if at > pos:                                    # Leerzeichen und Zeichen, die das Wörterbuch überspringt
                parts.append((text[pos:at], 0.0))
            reading = getattr(word.feature, "kana", None)
            if not reading or reading == "*" or not _KANJI.search(word.surface):
                reading = word.surface
            weight = float(_weight(_hiragana(reading)))
            pos1, pos2 = getattr(word.feature, "pos1", ""), getattr(word.feature, "pos2", "")
            # Hilfsverben, Endungen und て/たら gehören zum Wort davor: wasureta, oikakete, hashitteta
            joined = pos1 in ("助動詞", "接尾辞") or (pos1 == "助詞" and pos2 == "接続助詞") or \
                (parts and parts[-1][0].endswith(("っ", "ッ")))
            # 1.7.0: eine Vorsilbe gehört zum Wort danach (既読 → kidoku), Katakana-Wörter hintereinander sind eines
            # (ログアウト → roguauto)
            joined = joined or before == "接頭辞" or (_KATAKANA_WORD.fullmatch(word.surface) is not None and
                                                      bool(parts) and _KATAKANA_WORD.fullmatch(parts[-1][0]) is not None)
            if joined and at == pos and parts and parts[-1][1] > 0:
                parts[-1] = (parts[-1][0] + word.surface, parts[-1][1] + weight)
            else:
                parts.append((word.surface, weight))
            pos, before = at + len(word.surface), pos1
        if pos < len(text):
            parts.append((text[pos:], 0.0))
        if sum(n for _, n in parts) > 0:
            return parts
    return [(c, _weight(c)) for c in text]


def _weight(text: str) -> float:
    total = 0.0
    for c in text:
        if c in _SMALL:
            continue
        if _KANJI.search(c):
            total += 2.0
        elif _JAPANESE.search(c) or c == "ー":
            total += 1.0
        elif c.isalnum():
            total += 0.5
    return total


def syllables(line: str, romaji: bool = True, english: bool = False, smart: bool = False,
              own: dict = None) -> list:
    """
    Eine Textzeile als Silben zum Singen. Japanisch wird in Moren zerlegt, ob mit Leerzeichen oder ohne,
    Kanji werden vorher gelesen. romaji: Romaji wird vorher japanisch (romaji_to_kana). english: übrige Wörter in
    lateinischer Schrift werden zu Katakana (english_to_kana); ohne bleiben sie ganz (wie bisher). smart: Partikel
    auch in reinen Kana und Zahlwörter erkennen; own: eigene Lesungen {Wort: Lesung}.
    """
    line = _respelled(line, romaji, english, smart, own)
    tokens = line.split()
    if len(tokens) > 1 and all(_JAPANESE.search(t) and not _KANJI.search(t) for t in tokens):
        # Kana mit Leerzeichen zwischen den Silben (よ る の ま ち): als ganzen Satz lesen, damit die Wörter
        # und ihr Akzent erkannt werden; die Silben bleiben genau so, wie sie dastehen (bis auf die Partikel)
        spaced = [m for t in tokens for m in morae(to_kana(t))]
        whole = accented_morae("".join(tokens), smart)
        if len(whole) == len(spaced) and all(str(a) == b or (smart and _PARTICLES.get(b) == str(a))
                                             for a, b in zip(whole, spaced)):
            return whole
    out = []
    for token in tokens:
        if _JAPANESE.search(token):
            out += accented_morae(token, smart)
        else:
            out.append(token)
    return out


def _respelled(line: str, romaji: bool, english: bool, smart: bool, own: dict, found: list = None) -> str:
    """Die Zeile vor dem Lesen: eigene Lesungen, Romaji und Englisch, dann (smart) Zahlwörter in Kana."""
    import readings
    if own:
        line = readings.respell(_FURIGANA.sub(lambda m: m.group(2), line), False, own, found)
    if romaji or english:
        line = latin_to_kana(line, romaji, english)
    if smart:
        line = readings.respell(_FURIGANA.sub(lambda m: m.group(2), line), True, None, found)
    return line


def changes(line: str, romaji: bool = True, english: bool = False, smart: bool = False, own: dict = None) -> list:
    """[(geschrieben, gesungen)]: was eigene Lesungen und „Partikel erkennen“ an der Zeile ändern (für den Text-Helfer)."""
    found = []
    line = _respelled(line, romaji, english, smart, own, found)
    if smart:
        written, sung = syllables(line, False, False), syllables(line, False, False, True)
        if len(written) == len(sung):
            found += [(str(a), str(b)) for a, b in zip(written, sung) if _PARTICLES.get(str(a)) == str(b)]
    return list(dict.fromkeys(found))


def romaji_to_kana(line: str) -> str:
    """
    'kimi no koe' → 'きみ の こえ'. Eine Zeile nur aus lateinischen Buchstaben wird umgewandelt, wenn jedes Wort Romaji
    ist (sonst ist sie wohl Englisch); neben japanischer Schrift wird jedes Wort umgewandelt, das Romaji ist.
    """
    tokens = line.split()
    latin = {t: _romaji_kana(t) for t in tokens if _LATIN.search(t) and not _JAPANESE.search(t)}
    if not latin:
        return line
    if not any(_JAPANESE.search(t) for t in tokens) and not all(latin.values()):
        return line
    return " ".join(latin.get(t) or t for t in tokens)


def latin_to_kana(line: str, romaji: bool = True, english: bool = True) -> str:
    """
    Wörter in lateinischer Schrift singbar machen. Romaji wie bei romaji_to_kana: wenn die ganze Zeile Romaji ist oder
    das Wort neben japanischer Schrift steht. english: alle anderen werden Katakana ('I love you' → 'アイ ラブ ユー',
    auch wenn „you“ wie Romaji aussieht, weil die Zeile Englisch ist; 'kimi no koe love' → 'きみ の こえ ラブ').
    """
    tokens = line.split()
    latin = {t for t in tokens if _LATIN.search(t) and not _JAPANESE.search(t)}
    if not latin:
        return line
    as_romaji = {t: _romaji_kana(t) for t in latin} if romaji else {}
    japanese = any(_JAPANESE.search(t) for t in tokens)
    share = sum(bool(as_romaji.get(t)) for t in latin) / len(latin)
    # Mit Englisch darf eine Romaji-Zeile ein englisches Wort haben (kimi no koe love); sonst muss alles Romaji sein
    romaji_ok = japanese or share >= (ROMAJI_LINE_SHARE if english else 1.0)
    out = []
    for t in tokens:
        if t not in latin:
            out.append(t)
        elif romaji_ok and as_romaji.get(t):
            out.append(as_romaji[t])
        elif english:
            out.append(english_to_kana(t))
        else:
            out.append(t)
    return " ".join(out)


# Ab diesem Anteil an Romaji-Wörtern ist eine Zeile Romaji (die übrigen Wörter sind Englisch), darunter Englisch
ROMAJI_LINE_SHARE = 0.75
# Song-Wörter, wie sie in J-Pop gesungen werden; vor dem Wörterbuch, das sie anders liest (yeah → ヤー)
SONG_WORDS = {"yeah": "イェー", "yeh": "イェー", "oh": "オー", "ooh": "ウー", "ah": "アー", "baby": "ベイビー",
              "love": "ラブ", "hey": "ヘイ", "wow": "ワオ", "la": "ラ", "na": "ナ", "my": "マイ", "you": "ユー",
              "i": "アイ", "me": "ミー", "uh": "ア", "woah": "ウォー", "whoa": "ウォー", "go": "ゴー"}
# ヴ (v) gibt es nicht in jeder Stimme: wie im Alltag als b singen
_V_KANA = {"ヴァ": "バ", "ヴィ": "ビ", "ヴェ": "ベ", "ヴォ": "ボ", "ヴュ": "ビュ", "ヴ": "ブ"}


def english_to_kana(token: str) -> str:
    """'love' → 'ラブ', 'forever,' → 'フォーエバー'. Satzzeichen fallen weg; was nicht klappt, bleibt, wie es war."""
    word = re.sub(r"[^a-z']", "", token.lower()).replace("'", "")
    if not word:
        return token
    kana = SONG_WORDS.get(word) or _dictionary_kana(word) or _model_kana(word)
    if not kana:
        return token
    for v, b in _V_KANA.items():
        kana = kana.replace(v, b)
    return kana


def _dictionary_kana(word: str) -> str:
    try:
        import alkana
        return alkana.get_kana(word) or ""
    except Exception as e:  # noqa: BLE001 – ohne Wörterbuch bleibt das Modell
        log.debug("alkana: %s", e)
        return ""


@functools.lru_cache(maxsize=1)
def _english_model():
    try:
        from e2k import C2K
        return C2K()
    except Exception as e:  # noqa: BLE001
        log.debug("e2k nicht verfügbar: %s", e)
        return None


def _model_kana(word: str) -> str:
    model = _english_model()
    if model is None:
        return ""
    try:
        kana = model(word)
    except Exception as e:  # noqa: BLE001
        log.debug("e2k %s: %s", word, e)
        return ""
    return kana if kana and all("\u30a0" <= c <= "\u30ff" for c in kana) else ""


def _romaji_kana(token: str) -> str:
    """Ein Wort in Romaji als Hiragana, sonst ""."""
    core = token.lower().translate(_MACRONS).strip(_PUNCTUATION)
    if not core or not _ROMAJI.match(core):
        return ""
    import jaconv
    kana = jaconv.alphabet2kana(re.sub(r"nn(?=[aiueoy])", "n'n", core)).replace("'", "")
    return kana if kana and all("\u3041" <= c <= "\u309f" or c == "ー" for c in kana) else ""


def accented_morae(text: str, smart: bool = False) -> list:
    """
    Moren mit Tonhöhenakzent: 君の声 → き(L) み(H) の(H) こ(H) え(L). Wörter beginnen mit word_start,
    Partikel bleiben auf der Höhe, die das Wort davor ihnen lässt. Ohne Wörterbuch nur die Moren. smart: Partikel
    auch in reinen Kana erkennen.
    """
    out, flat_before = [], False
    for reading, pos1, accent in _words(text, smart):
        ms = morae(reading)
        if not ms:
            continue
        if pos1 in _FUNCTION_WORDS:
            level = ("H" if flat_before else "L") if out and out[-1].tone else None
            out += [Mora(m, level, melisma=_held(m), long=_long(m)) for m in ms]
            continue
        tones = _tones(len(ms), accent) if len(ms) > 1 or accent is not None else [None]
        out += [Mora(m, t, word_start=i == 0, melisma=_held(m), long=_long(m))
                for i, (m, t) in enumerate(zip(ms, tones))]
        flat_before = accent == 0
    return out


def _held(m) -> bool:
    return bool(getattr(m, "melisma", False))


def _long(m) -> bool:
    return bool(getattr(m, "long", False))


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
    """'きゃっとー' → ['きゃ', 'っ', 'と', 'お']; alles außer Kana fällt weg. Der Vokal aus „ー“ ist eine Mora mit
    melisma=True: kein neuer Einsatz, die Silbe davor klingt weiter (für NEUTRINO wird daraus wieder ー)."""
    out = []
    for ch in _hiragana(kana):
        if ch in _SMALL and out:
            out[-1] += ch
        elif "\u3041" <= ch <= "\u3096":
            out.append(ch)
        elif ch == "ー" and out and out[-1][-1] in _VOWELS:
            out.append(Mora(_VOWELS[out[-1][-1]], melisma=True, long=True))
    return out


def to_kana(text: str) -> str:
    """Japanischer Text als Hiragana so, wie er gesungen wird (Partikel は → わ). Reine Kana bleiben, wie sie sind."""
    text = _FURIGANA.sub(lambda m: m.group(2), text)
    if not _KANJI.search(text):
        return _hiragana(text)
    if _tagger() is None:
        return _hiragana(_KANJI.sub("", text))
    return "".join(reading for reading, _, _ in _words(text))


def _words(text: str, smart: bool = False) -> list:
    """[(Lesung in Hiragana, Wortart, Akzentkern oder None)] eines japanischen Texts. Reine Kana werden gesungen, wie
    sie dastehen; mit smart auch dort die Partikel は, へ, を wie gesprochen."""
    text = _FURIGANA.sub(lambda m: m.group(2), text)
    tagger = _tagger()
    if tagger is None:
        return [(_hiragana(_KANJI.sub("", text)), "", None)]
    as_written = not _KANJI.search(text)        # reine Kana: so singen, wie geschrieben
    out, pos = [], 0
    for word in tagger(text):
        at = text.find(word.surface, pos)
        pos = at + len(word.surface) if at >= 0 else pos
        reading = getattr(word.feature, "kana", None)
        if as_written or not reading or reading == "*":
            reading = word.surface if _JAPANESE.search(word.surface) else ""
        reading = _hiragana(reading)
        pos1 = getattr(word.feature, "pos1", "")
        if pos1 == "助詞" and reading in _PARTICLES and (not as_written or smart and _particle_at(text, at)):
            reading = _PARTICLES[reading]
        out.append((reading, pos1, _accent(getattr(word.feature, "aType", None))))
    return out


def _particle_at(text: str, at: int) -> bool:
    """In reinen Kana: ist は oder へ an dieser Stelle wirklich die Partikel? Nur wenn der Rest ab hier auch mit ihr
    beginnt (in „はしりだせ“ gehört は zum Verb). を ist immer die Partikel."""
    if at < 0:
        return False
    if text[at] == "を":
        return True
    first = next(iter(_tagger()(text[at:])), None)
    return first is not None and first.surface == text[at] and getattr(first.feature, "pos1", "") == "助詞"


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
