# rezepte.py – Song-Rezepte mit Beispieltext (v6 Nr. 13)
#
# Fertige Ausgangspunkte zum Ausprobieren: Stil, Tempo, Tonart, Takt, Ablauf und ein eigener Beispieltext, der zu
# Ablauf und Tempo passt. Anders als eine Vorlage bringt ein Rezept den Text mit. Alle Texte sind für die App
# geschrieben (keine Liedtexte echter Songs); „wie Idol“ heißt: so gebaut (schnell, Rap-Teil, Idol-Rufe), nicht
# nachgemacht. Laden setzt Seed, Neu-Würfeln und Änderungen an der Melodie zurück: es entsteht ein neuer Song.
from dataclasses import dataclass, field

from settings import SongSettings

FRESH = {"seed": None, "variations": {}, "melody_edits": {}, "melody_lengths": {}, "phrase_fixes": {},
         "custom_chords": {}, "section_bars": {}, "remix_from": "", "remix_bpm": 0, "melody_midi": ""}


@dataclass(frozen=True)
class Recipe:
    name: str
    about: str
    values: dict
    lyrics: str
    extra: dict = field(default_factory=dict)       # Schalter, die das Rezept braucht (Rap-Stimme, Rufe …)


RECIPES = (
    Recipe(
        "Hologram Star (wie Idol)",
        "Schnell und strahlend wie „Idol“: Rap-Teil von der VOICEVOX-Sprechstimme, Idol-Rufe im Refrain, Tonart "
        "wechselt im letzten Refrain.",
        {"style": "Idol-Pop", "bpm": 166, "key": "A", "scale": "minor", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Rap", "Verse", "PreChorus", "Chorus",
                             "Bridge", "Chorus", "Outro"], "section_bars": {"Rap": 16}},
        "[Verse]\nひかりのなかで わらうきみ\nだれもしらない ほんとうのかお\nステージのうえ ゆめをうたう\n"
        "うそもほんとも ぜんぶあいして\n"
        "[PreChorus]\nめをそらさないで いまだけは\nこのむねのおと きこえるでしょう\n"
        "[Chorus]\nホログラムスター きらめいて\nとどかないほど たかくとんで\nホログラムスター そのえがおで\n"
        "せかいをぜんぶ とりこにして\n"
        "[Rap]\nいちばんぼし ねらいさだめて\nまけずぎらい ひみつのレシピ\nカメラのまえ ポーズきめて\n"
        "きょうもかんぺき むてきのアイドル\n"
        "[Bridge]\nほんとうのわたしを みつけて\nひかりがきえても そばにいて",
        {"rap_voice": True, "idol_calls": True}),
    Recipe(
        "Mitternachtsfahrt (schnell und dunkel)",
        "Dark Vocaloid mit 180 BPM in d-Moll: harte Gitarren, Drop nach dem zweiten Refrain, Vocal Chops im Drop.",
        {"style": "Dark Vocaloid", "bpm": 180, "key": "D", "scale": "minor", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Drop",
                             "Bridge", "Chorus", "Outro"]},
        "[Verse]\nまよなかのみち はしりだす\nしんごうはあか それでもいく\nこわれたまちの かげをぬけて\n"
        "だれかのこえが よんでいる\n"
        "[PreChorus]\nにげられないなら たたかえばいい\nこのよるがあけるまで\n"
        "[Chorus]\nミッドナイト はしれ はしれ\nかなしみごと ふりきって\nミッドナイト さけべ さけべ\n"
        "あしたなんて いらないから\n"
        "[Bridge]\nつめたいかぜが ほほをきる\nそれでもぼくは とまらない",
        {"vocal_chops": True}),
    Recipe(
        "Letzter Sommerregen (Ballade)",
        "Ruhige Ballade in G-Dur mit 72 BPM: Klavier und Streicher, am Ende langsamer mit gehaltenem Schlussakkord.",
        {"style": "Ballade", "bpm": 72, "key": "G", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]},
        "[Verse]\nなつのおわりの あめのにおい\nふたりでみてた まどのそと\nかさをわすれた あのひのこと\n"
        "いまもときどき おもいだすよ\n"
        "[Chorus]\nさよならは いわないで\nこのあめが やむまでは\nきみのこえを わすれないように\n"
        "そっとめを とじるから\n"
        "[Bridge]\nいつかまた あえるなら\nそのときは わらってね",
        {"ritardando": True}),
    Recipe(
        "Sakura Kiss (Idol-Pop)",
        "Fröhlicher Idol-Pop in D-Dur mit 150 BPM: Rufe „はい！はい！“ in jedem Refrain und „ふっふー“ davor.",
        {"style": "Idol-Pop", "bpm": 150, "key": "D", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge",
                             "Chorus", "Outro"]},
        "[Verse]\nさくらのはなが まうみちで\nきみをみつけた はるのあさ\nどきどきしてる このきもち\n"
        "とどけたいよ いますぐに\n"
        "[PreChorus]\nいっぽずつ ちかづいて\nゆうきをだして\n"
        "[Chorus]\nさくらキッス はじめての\nこいのいろは ピンクいろ\nさくらキッス わらってよ\n"
        "きみとならば むてきだよ\n"
        "[Bridge]\nはなびらが ちっても\nこのおもいは かれないよ",
        {"idol_calls": True}),
    Recipe(
        "Neon City Night (City Pop)",
        "City Pop mit 108 BPM in F-Dur: Septakkorde, Slap-Bass und Bläser, entspannt groovend.",
        {"style": "City Pop", "bpm": 108, "key": "F", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Solo",
                             "Chorus", "Outro"], "section_bars": {"Verse": 8, "PreChorus": 4, "Chorus": 8}},
        "[Verse]\nネオンのまちを ドライブして\nラジオからながれる なつかしいうた\nきみのよこがお ガラスにうつる\n"
        "このままよるが つづけばいい\n"
        "[PreChorus]\nかぜがはこぶ しおのかおり\nゆっくりと\n"
        "[Chorus]\nシティナイト ふたりだけの\nひみつのばしょへ つれていって\nシティナイト ほしくずを\n"
        "ポケットにいれて かえろうよ",
        {}),
    Recipe(
        "Sky Drop (Future Bass)",
        "Future Bass mit 150 BPM in C-Dur: breite Synth-Akkorde, Vocal Chops im Intro und im Drop.",
        {"style": "Future Bass", "bpm": 150, "key": "C", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Drop", "Verse", "PreChorus", "Chorus",
                             "Drop", "Outro"]},
        "[Verse]\nあおいそらに てをのばして\nくもをこえて どこまでも\nちいさなゆめを かかえたまま\n"
        "かぜにのって とんでいこう\n"
        "[PreChorus]\nカウントダウン むねがなる\nいまだ\n"
        "[Chorus]\nスカイハイ とびたって\nひかりのなかへ おちていく\nスカイハイ もういちど\n"
        "このせかいを だきしめて",
        {"vocal_chops": True}),
    Recipe(
        "Walzer im Mondlicht (3/4)",
        "Ein Walzer im 3/4-Takt mit 108 BPM in e-Moll: Bum-Tschak-Tschak, Ballade mit langsamem Schluss.",
        {"style": "Ballade", "bpm": 108, "key": "E", "scale": "minor", "meter": "3/4",
         "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]},
        "[Verse]\nつきのひかりの したでおどる\nだれもいない よるのひろば\nくるくるまわる ゆめのなか\n"
        "きみのてを はなさない\n"
        "[Chorus]\nワルツをおどろう ふたりで\nあさがくるまで このままで\nつきがしずむ そのときまで\n"
        "わたしをわすれないで",
        {"ritardando": True}),
    Recipe(
        "Rocket Heart (Rock)",
        "Rock mit 170 BPM in e-Moll: verzerrte Gitarren, Double-Kick im Refrain, Gitarrensolo, Rufe „おい！“.",
        {"style": "Rock", "bpm": 170, "key": "E", "scale": "minor", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Solo",
                             "Bridge", "Chorus", "Outro"]},
        "[Verse]\nエンジンかけて とびだそう\nほしのかなたへ まっすぐに\nこわいものなんて なにもない\n"
        "このこころが ロケットさ\n"
        "[PreChorus]\nさんにいいち いくぞ\nさけべ\n"
        "[Chorus]\nロケットハート もえあがれ\nだれにもとめられない\nロケットハート つきぬけろ\n"
        "そらのはてまで\n"
        "[Bridge]\nころんでも なんどでも\nたちあがる",
        {"idol_calls": True}),
    Recipe(
        "Regentag zum Lernen (Lo-Fi)",
        "Lo-Fi mit 82 BPM in F-Dur: Swing, Knistern und weiche Klavierakkorde, leise gesungen.",
        {"style": "Lo-Fi", "bpm": 82, "key": "F", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]},
        "[Verse]\nあめのおとが まどをたたく\nあたたかいおちゃ ノートをひらく\nゆっくりでいい いそがないで\n"
        "きょうのぶんだけ すすもう\n"
        "[Chorus]\nレイニーデイ ここにいて\nしずかなじかん ふたりきり\nレイニーデイ あしたはきっと\n"
        "はれるといいね",
        {"lofi_texture": True}),
    # 1.5.0: die drei neuen Stile, mit deutscher Übersetzung unter jeder Zeile („> …“) fürs Musikvideo
    Recipe(
        "Kirschblütenklinge (Wafuu-Rock)",
        "Wafuu-Rock mit 162 BPM in d-Moll: Shamisen, Koto und Shakuhachi zur Rockband, Taiko im Refrain, die "
        "Melodie in der japanischen Fünftonleiter.",
        {"style": "Wafuu-Rock", "bpm": 162, "key": "D", "scale": "minor", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Interlude", "Verse", "PreChorus", "Chorus",
                             "Bridge", "Chorus", "Outro"]},
        "[Verse]\nはなびらが まうよるに\n> In der Nacht, in der Blütenblätter tanzen\n"
        "かたなのような つきがでる\n> geht ein Mond auf wie ein Schwert\n"
        "とおいまつりの たいこのおと\n> die Trommeln eines fernen Festes\n"
        "むねのおくで ひびいてる\n> hallen tief in meiner Brust\n"
        "[PreChorus]\nいまこそ かぜをきれ\n> Jetzt zerschneide den Wind\n"
        "[Chorus]\nさくら さくら まいあがれ\n> Kirschblüten, steigt auf\n"
        "このいのち もやしつくせ\n> verbrenn dieses Leben ganz\n"
        "さくら さくら ちりゆけど\n> Kirschblüten, auch wenn ihr fallt\n"
        "こころは いつまでも\n> das Herz bleibt für immer\n"
        "[Bridge]\nしずかに めをとじて\n> Ich schließe still die Augen\n"
        "あなたを おもう\n> und denke an dich"),
    Recipe(
        "Grammophon-Tanz (Electro-Swing)",
        "Electro-Swing mit 124 BPM in g-Moll: Walking Bass, Bläser und Ragtime-Klavier im Swing über der "
        "durchgehenden Bassdrum, die erste Zeile klingt wie aus dem Grammophon.",
        {"style": "Electro-Swing", "bpm": 124, "key": "G", "scale": "minor", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Drop",
                             "Chorus", "Outro"]},
        "[Verse]\nふるいレコード まわりだす\n> Die alte Platte fängt an, sich zu drehen\n"
        "ぼうしをかぶって ステップふむ\n> Hut auf und die ersten Schritte\n"
        "きんいろのよる シャンデリア\n> eine goldene Nacht, Kronleuchter\n"
        "だれもかれもが おどってる\n> und alle, alle tanzen\n"
        "[PreChorus]\nほら スイング スイング\n> Komm, Swing, Swing\n"
        "[Chorus]\nダンス ダンス とまらない\n> Tanzen, tanzen, wir hören nicht auf\n"
        "ひだりみぎ くるりとまわれ\n> links, rechts, einmal herumgedreht\n"
        "ダンス ダンス あさまでずっと\n> tanzen, tanzen, bis zum Morgen\n"
        "このリズムに のって\n> auf diesem Rhythmus"),
    Recipe(
        "Glitzer-Overload (Hyperpop)",
        "Hyperpop mit 168 BPM in E-Dur: Chip-Leads, Supersaws, verzerrter Bass und Wirbel-Hi-Hats, die Stimme hart "
        "auf die Töne gezogen; alles absichtlich zu viel.",
        {"style": "Hyperpop", "bpm": 168, "key": "E", "scale": "major", "meter": "4/4",
         "active_sections": ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge",
                             "Drop", "Chorus", "Outro"]},
        "[Verse]\nきらきら ピクセル はじけとぶ\n> Glitzernde Pixel platzen auseinander\n"
        "ボリュームは いつも マックスで\n> die Lautstärke immer auf Maximum\n"
        "ネオンの あめが ふりそそぐ\n> es regnet Neon\n"
        "スクリーンの むこうへ ジャンプ\n> Sprung hinter den Bildschirm\n"
        "[PreChorus]\nもっと もっと はやく\n> Mehr, mehr, schneller\n"
        "[Chorus]\nグリッチ ハート ばくはつしそう\n> Glitch-Herz, gleich explodiert es\n"
        "ぜんぶ ぜんぶ ひかりになれ\n> alles, alles, werde Licht\n"
        "グリッチ ハート とまらないで\n> Glitch-Herz, hör nicht auf\n"
        "せかいを ぬりかえて\n> mal die Welt neu an\n"
        "[Bridge]\nちいさなこえで ないてた\n> Mit leiser Stimme hab ich geweint\n"
        "でも もう だいじょうぶ\n> aber jetzt ist alles gut"),
)


def names() -> list:
    return [r.name for r in RECIPES]


def get(name: str) -> Recipe:
    for recipe in RECIPES:
        if recipe.name == name:
            return recipe
    raise ValueError(f"Kein Rezept „{name}“. Es gibt: {', '.join(names())}")


def apply(name: str, settings: SongSettings) -> SongSettings:
    """Die Einstellungen mit Stil, Tempo, Tonart, Takt, Ablauf und Text des Rezepts; ein neuer Song (ohne Seed).
    Stimme, Engine, Pfade und Mix bleiben."""
    recipe = get(name)
    return settings.with_updates(**{**FRESH, **recipe.values, **recipe.extra, "lyrics": recipe.lyrics})
