# readings.py – Wörter richtig lesen (1.3.0, G6)
#
# UniDic liest Zahl und Zählwort einzeln und ohne die Lautänderung, die man spricht: 一回 wird „いちかい“ statt
# „いっかい“, 三本 „さんほん“ statt „さんぼん“. Mit „Partikel erkennen“ schreibt die App solche Wörter vor dem Lesen in
# Kana um: ein paar feste Wörter (EXCEPTIONS) und Zahl + Zählwort nach den Regeln der Aussprache (COUNTERS). Eigene
# Lesungen stehen in Lesungen.txt im Datenordner, eine pro Zeile als „Wort=Lesung“; sie gelten immer, eine leere oder
# fehlende Datei ändert nichts.
import logging
import os
import re

import config

log = logging.getLogger(__name__)

FILE = "Lesungen.txt"
ACTIVE = True               # „Partikel erkennen“ wirkt (die Tests schalten es ab, damit ihre Songs wie in 1.2 singen)
# Wörter, die das Wörterbuch falsch liest (oder anders, als man sie singt)
EXCEPTIONS = {
    "一途": "いちず", "一目惚れ": "ひとめぼれ", "明日": "あした", "一択": "いったく", "十分間": "じゅっぷんかん",
    "十分": "じゅうぶん", "一晩": "ひとばん", "一番星": "いちばんぼし", "一粒": "ひとつぶ", "一昨日": "おととい",
    "明後日": "あさって", "一日中": "いちにちじゅう", "一遍": "いっぺん", "一羽": "いちわ", "一通り": "ひととおり",
    "一回り": "ひとまわり", "一足先": "ひとあしさき", "千本桜": "せんぼんざくら",
    "こんにちは": "こんにちわ", "こんばんは": "こんばんわ",
}
DIGITS = {"一": "いち", "二": "に", "三": "さん", "四": "よん", "五": "ご", "六": "ろく", "七": "なな", "八": "はち",
          "九": "きゅう"}
UNITS = {"十": "じゅう", "百": "ひゃく", "千": "せん", "万": "まん"}
# Ziffer und Stelle, die sich beim Zusammensprechen ändern (三百 さんびゃく)
JOINED = {("さん", "ひゃく"): "さんびゃく", ("ろく", "ひゃく"): "ろっぴゃく", ("はち", "ひゃく"): "はっぴゃく",
          ("さん", "せん"): "さんぜん", ("はち", "せん"): "はっせん"}
# Zählwort: (Lesung, nach einem kleinen っ, nach さん/なん/せん/まん, Art). Art "k" und "h": っ nach いち, ろく, はち,
# じゅう, ひゃく; Art "s": っ nur nach いち, はち, じゅう, ひゃく
COUNTERS = {
    "回": ("かい", "かい", "かい", "k"), "階": ("かい", "かい", "がい", "k"), "個": ("こ", "こ", "こ", "k"),
    "ヶ月": ("かげつ", "かげつ", "かげつ", "k"), "か月": ("かげつ", "かげつ", "かげつ", "k"),
    "カ月": ("かげつ", "かげつ", "かげつ", "k"), "軒": ("けん", "けん", "げん", "k"),
    "頭": ("とう", "とう", "とう", "k"), "点": ("てん", "てん", "てん", "k"), "通": ("つう", "つう", "つう", "k"),
    "着": ("ちゃく", "ちゃく", "ちゃく", "k"),
    "冊": ("さつ", "さつ", "さつ", "s"), "足": ("そく", "そく", "ぞく", "s"),
    "週間": ("しゅうかん", "しゅうかん", "しゅうかん", "s"),
    "本": ("ほん", "ぽん", "ぼん", "h"), "杯": ("はい", "ぱい", "ばい", "h"), "匹": ("ひき", "ぴき", "びき", "h"),
    "分": ("ふん", "ぷん", "ぷん", "h"), "歩": ("ほ", "ぽ", "ぽ", "h"), "発": ("はつ", "ぱつ", "ぱつ", "h"),
    "泊": ("はく", "ぱく", "ぱく", "h"), "拍": ("はく", "ぱく", "ぱく", "h"), "品": ("ひん", "ぴん", "ぴん", "h"),
}
_HUNDRED = ("ひゃく", "びゃく", "ぴゃく")
SMALL_TSU = {"k": ("いち", "ろく", "はち", "じゅう") + _HUNDRED, "h": ("いち", "ろく", "はち", "じゅう") + _HUNDRED,
             "s": ("いち", "はち", "じゅう") + _HUNDRED}
NASAL = ("さん", "なん", "せん", "ぜん", "まん")
YON_TOO = ("分", "歩", "発", "泊", "拍")          # nach よん wie nach さん: よんぷん
# Zahl aus Kanji und ein Zählwort dahinter; davor steht kein Kanji (唯一本気 ist kein „一本“, 三十分 kein „十分“)
_NOT_AFTER_KANJI = r"(?<![\u4e00-\u9fff々〆])"
_NUMBER = re.compile(_NOT_AFTER_KANJI + r"([一二三四五六七八九十百千万]+|何)("
                     + "|".join(sorted(COUNTERS, key=len, reverse=True)) + ")")
_EXCEPTION = re.compile(_NOT_AFTER_KANJI + "(" + "|".join(sorted(EXCEPTIONS, key=len, reverse=True)) + ")")
_KANA = re.compile(r"^[ぁ-ヿー]+$")


def number_kana(number: str):
    """Die Lesung einer Zahl in Kanji (三百 → さんびゃく, 何 → なん); None, wenn es keine Zahl ist (一二)."""
    if number == "何":
        return "なん"
    out, digit = "", None
    for ch in number:
        if ch in DIGITS:
            if digit is not None:
                return None
            digit = DIGITS[ch]
        else:
            unit = UNITS[ch]
            if digit is None or (digit == "いち" and unit != "まん"):
                out += unit
            else:
                out += JOINED.get((digit, unit), digit + unit)
            digit = None
    return out + (digit or "")


def counted(number: str, counter: str):
    """Zahl + Zählwort, wie man es spricht (一回 → いっかい, 三本 → さんぼん); None, wenn es keine Zahl ist."""
    kana = number_kana(number)
    if not kana:
        return None
    plain, after_tsu, after_n, kind = COUNTERS[counter]
    for end in SMALL_TSU[kind]:
        if kana.endswith(end):
            return kana[:-1] + "っ" + after_tsu
    if kana.endswith(NASAL) or (kana.endswith("よん") and counter in YON_TOO):
        return kana + after_n
    return kana + plain


def respell(text: str, smart: bool = True, own: dict = None, found: list = None) -> str:
    """
    Der Text mit den eigenen Lesungen (own) und, wenn smart, mit den Wörtern aus EXCEPTIONS und Zahl + Zählwort in Kana.
    found: hier landen die Änderungen als (Wort, Lesung), für den Text-Helfer.
    """
    own = own or {}
    found = [] if found is None else found
    for word in sorted(own, key=len, reverse=True):
        if word in text:
            text = text.replace(word, own[word])
            found.append((word, own[word]))
    if not smart:
        return text

    def exception(m):
        found.append((m.group(1), EXCEPTIONS[m.group(1)]))
        return EXCEPTIONS[m.group(1)]

    def change(m):
        kana = counted(m.group(1), m.group(2))
        if kana is None:
            return m.group(0)
        found.append((m.group(0), kana))
        return kana
    return _NUMBER.sub(change, _EXCEPTION.sub(exception, text))


TEMPLATE = """# Eigene Lesungen für den Liedtext, eine pro Zeile: Wort=Lesung in Kana
# Sie gelten immer, auch ohne „Partikel erkennen“. Zeilen mit # am Anfang sind Notizen. Beispiele:
# 明日=あした
# 運命=さだめ
# Tokyo=とうきょう
"""


def path() -> str:
    return os.path.join(config.DATA_DIR, FILE)


def ensure_file() -> str:
    """Lesungen.txt mit einer Anleitung anlegen, wenn es sie noch nicht gibt. Rückgabe: der Pfad."""
    target = path()
    if not os.path.exists(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
    return target


def own_readings() -> dict:
    """{Wort: Lesung in Hiragana} aus Lesungen.txt; leer, wenn es die Datei nicht gibt. Zeilen mit # sind Notizen."""
    try:
        with open(path(), encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    out = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word, sep, reading = (part.strip() for part in line.partition("="))
        reading = reading.replace(" ", "")
        if not sep or not word or not _KANA.match(reading):
            log.warning("%s, Zeile %d: bitte als „Wort=Lesung in Kana“ schreiben (%s)", FILE, number, line)
            continue
        out[word] = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in reading)
    return out
