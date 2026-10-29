# textmotive.py – Bilder aus dem Liedtext (1.5.0 V8)
#
# Steht 雨 im Text, regnet es im Video; bei 星 funkeln Sterne, bei 桜 fallen Blüten, bei 既読 wird der Sprech-Teil
# zum Chat. Eine feste Liste von Wörtern, gefunden mit fugashi in der Grundform (走った → 走る), sonst als Textstelle.
# Nur was wirklich im Text steht, taucht auf; steht nichts davon drin, bleibt die Szene des Stils.
import logging
from collections import Counter
from typing import Optional

log = logging.getLogger(__name__)

# Motiv → Wörter, die es auslösen (Grundformen und Schreibweisen)
WORDS = {
    "rain": ("雨", "あめ", "梅雨", "傘", "かさ", "濡れる", "ぬれる", "雨粒", "夕立"),
    "snow": ("雪", "ゆき", "冬", "白い息", "凍る", "こおる"),
    "petals": ("桜", "さくら", "サクラ", "花びら", "花", "はな", "春", "舞う"),
    "stars": ("星", "ほし", "流れ星", "星空", "銀河", "宇宙", "きらきら", "キラキラ", "輝く", "かがやく"),
    "moon": ("月", "つき", "満月", "三日月"),
    "night": ("夜", "よる", "真夜中", "深夜", "闇", "やみ", "暗い", "眠る", "夢", "ゆめ"),
    "sun": ("太陽", "朝", "あさ", "朝焼け", "夕焼け", "光", "ひかり", "眩しい", "まぶしい", "晴れ", "夏"),
    "sea": ("海", "うみ", "波", "なみ", "浜", "泳ぐ"),
    "fire": ("火", "炎", "ほのお", "燃える", "もえる", "熱い", "あつい"),
    "tears": ("涙", "なみだ", "泣く", "なく", "雫", "しずく"),
    "hearts": ("好き", "すき", "恋", "こい", "愛", "あい", "ハート", "キス", "大好き", "ラブ"),
    "chat": ("既読", "未読", "スマホ", "メッセージ", "メール", "通知", "電話", "画面", "返事", "スタンプ", "もしもし"),
    "game": ("ゲーム", "コンティニュー", "コイン", "レベル", "ステージ", "スタート", "セーブ", "プレイヤー",
             "ゲームオーバー"),
    "city": ("街", "まち", "ネオン", "ビル", "駅", "電車", "交差点", "信号"),
    "wind": ("風", "かぜ", "飛ぶ", "とぶ", "羽", "翼", "つばさ"),
    "music": ("歌", "うた", "歌う", "うたう", "メロディー", "音", "おと", "声", "こえ"),
}
# Was davon als Teilchen durchs Bild fliegt; „night“ und „sun“ färben nur
PARTICLES = ("rain", "snow", "petals", "stars", "fire", "tears", "hearts", "sea", "wind", "music")
WEATHER = ("rain", "snow", "petals", "stars")      # höchstens eins davon füllt das ganze Bild


def find(text: str) -> Counter:
    """{Motiv: wie oft} in einem Text (eine Zeile oder der ganze Liedtext). Wörter mit Kanji oder Katakana zählen auch
    als Textstelle (既読 zerlegt das Wörterbuch in zwei Teile), reine Hiragana nur als ganzes Wort (あい nicht in
    はなしあい)."""
    import re
    from lyrics import _FURIGANA
    plain = _FURIGANA.sub(lambda m: m.group(1), text)
    words = Counter(_base_forms(text))
    found = Counter()
    for motif, triggers in WORDS.items():
        for trigger in triggers:
            as_word = words[trigger]
            if len(trigger) >= 2 and not re.fullmatch(r"[\u3041-\u309f]+", trigger):
                as_word = max(as_word, plain.count(trigger))
            found[motif] += as_word
    return +found


def _base_forms(text: str) -> list:
    """Die Wörter des Texts wie geschrieben und, wo sie anders ist, in Grundform (走った → 走る)."""
    from lyrics import _FURIGANA, _tagger
    text = _FURIGANA.sub(lambda m: m.group(1), text)
    tagger = _tagger()
    if tagger is None:
        return []
    out = []
    for word in tagger(text):
        out.append(word.surface)
        lemma = str(getattr(word.feature, "orthBase", None) or getattr(word.feature, "lemma", None) or "")
        lemma = lemma.split("-")[0]
        if lemma and lemma != "*" and lemma != word.surface:
            out.append(lemma)
    return out


def for_lines(lines: list) -> list:
    """Pro Zeile des Liedtexts (karaoke.lines mit "text") ihre Motive als Menge."""
    return [set(find(line.get("text") or "")) for line in lines]


def weather(lines: list) -> Optional[str]:
    """Das Wetter, das den ganzen Song füllt: das häufigste aus WEATHER im Text; None, wenn keins vorkommt."""
    total = Counter()
    for line in lines:
        total.update(find(line.get("text") or ""))
    found = [(total[m], -WEATHER.index(m), m) for m in WEATHER if total[m]]
    return max(found)[2] if found else None


def song_motifs(lines: list) -> Counter:
    total = Counter()
    for line in lines:
        total.update(find(line.get("text") or ""))
    return total
