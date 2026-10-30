# textbausteine.py – Die Zeilen des Text-Baukastens (1.6.0): von Hand geschrieben, ohne KI
#
# Acht Themen mit je 66 Zeilen (26 Strophe, 12 Pre-Chorus, 16 Refrain, 12 Bridge), sechs Titelwörtern und 24
# Hook-Zeilen für den Refrain, in die das Titelwort kommt (zusammen 600). Eine Zeile pro Eintrag:
#     Rolle Stimmung Text | Lesung | Deutsch
# Rolle: V Strophe, P Pre-Chorus, C Refrain, B Bridge, H Hook mit {} für das Titelwort. Stimmung: h hell, n beides,
# d traurig. Die Lesung steht so, wie gesungen wird (Partikel は, へ, を als わ, え, お); test_textbau_160 prüft, dass
# die App jede Zeile genau so liest. Wo das Wörterbuch falsch liest, steht die Lesung von Hand dabei (既読[きどく]).
# Silben (Moren), Romaji und Reim rechnet textbaukasten.py aus der Lesung.

THEMES = {
    "liebe": "Liebe und Sehnsucht",
    "abschied": "Abschied und Erinnerung",
    "sommer": "Sommer und Feuerwerk",
    "nacht": "Stadt bei Nacht und Regen",
    "traum": "Träume und Aufbruch",
    "online": "Bildschirm und Einsamkeit",
    "kampf": "Mut und Kampf",
    "winter": "Winter und Schnee",
}

# Titelwörter: Text | Lesung | Deutsch
TITLE_WORDS = {
    "liebe": """
恋心 | こいごころ | Verliebtheit
約束 | やくそく | Versprechen
片想い | かたおもい | heimliche Liebe
赤い糸 | あかいいと | roter Faden
指輪 | ゆびわ | Ring
ラブレター | らぶれたー | Liebesbrief
""",
    "abschied": """
さよなら | さよなら | Lebewohl
思い出 | おもいで | Erinnerung
手紙 | てがみ | Brief
桜 | さくら | Kirschblüte
写真 | しゃしん | Foto
最終電車 | さいしゅうでんしゃ | letzter Zug
""",
    "sommer": """
花火 | はなび | Feuerwerk
夏祭り | なつまつり | Sommerfest
向日葵 | ひまわり | Sonnenblume
青い空 | あおいそら | blauer Himmel
波音 | なみおと | Wellenrauschen
サイダー | さいだー | Limonade
""",
    "nacht": """
ネオン | ねおん | Neonlicht
雨音 | あまおと | Regenrauschen
真夜中 | まよなか | Mitternacht
傘 | かさ | Regenschirm
交差点 | こうさてん | Kreuzung
月明かり | つきあかり | Mondlicht
""",
    "traum": """
未来 | みらい | Zukunft
夢 | ゆめ | Traum
翼 | つばさ | Flügel
地図 | ちず | Landkarte
一番星[いちばんぼし] | いちばんぼし | erster Stern
光 | ひかり | Licht
""",
    "online": """
既読[きどく] | きどく | Gelesen
通知 | つうち | Benachrichtigung
画面 | がめん | Bildschirm
アバター | あばたー | Avatar
電波 | でんぱ | Funkwelle
パスワード | ぱすわーど | Passwort
""",
    "kampf": """
炎 | ほのお | Flamme
運命 | うんめい | Schicksal
拳 | こぶし | Faust
叫び | さけび | Schrei
雷鳴 | らいめい | Donner
魂 | たましい | Seele
""",
    "winter": """
粉雪 | こなゆき | Pulverschnee
白い息 | しろいいき | weißer Atem
マフラー | まふらー | Schal
星空 | ほしぞら | Sternenhimmel
冬の朝 | ふゆのあさ | Wintermorgen
雪明かり | ゆきあかり | Schneelicht
""",
}

# Hook-Zeilen für den Refrain, für alle Themen; {} ist das Titelwort (im Deutschen angesprochen, ohne Artikel)
HOOKS = """
H n {} {} 今 輝いて | {} {} いま かがやいて | {}, {}, leuchte jetzt
H d {}よ 消えないで | {}よ きえないで | {}, verschwinde nicht
H h {}よ 空まで 飛んでいけ | {}よ そらまで とんでいけ | {}, flieg bis in den Himmel
H n ねえ {} 聞こえるかな | ねえ {} きこえるかな | Hey, {}, kannst du mich hören?
H d {} {} 届かない | {} {} とどかない | {}, {}, ich erreiche dich nicht
H h {} {} 鳴り響け | {} {} なりひびけ | {}, {}, erklinge laut
H n 忘れないで {} | わすれないで {} | Vergiss mich nicht, {}
H d 抱きしめたまま {} | だきしめたまま {} | Ich halte dich fest, {}
H h 走りだせ {} | はしりだせ {} | Lauf los, {}
H n {}よ 今夜だけは | {}よ こんやだけわ | {}, nur heute Nacht
H d ずっと 待ってたよ {} | ずっと まってたよ {} | Ich habe so lange gewartet, {}
H h 何度でも 叫ぶよ {} | なんどでも さけぶよ {} | Immer wieder rufe ich dich, {}
H n {} この手に もう一度 | {} このてに もういちど | {}, komm noch einmal in meine Hand
H d 泣かないで {} | なかないで {} | Weine nicht, {}
H h 輝いて {} 今 | かがやいて {} いま | Leuchte, {}, jetzt
H n {}よ どうか 終わらないで | {}よ どうか おわらないで | {}, bitte hör nicht auf
H d 消えてしまう前に {} | きえてしまうまえに {} | Bevor du verschwindest, {}
H h 響け 響け {} | ひびけ ひびけ {} | Erklinge, erklinge, {}
H n ねえ {} 笑って | ねえ {} わらって | Hey, {}, lach doch
H h {}に 願いを込めて | {}に ねがいおこめて | {}, in dich lege ich meinen Wunsch
H d {}だけが 残った | {}だけが のこった | Nur du bist geblieben, {}
H n {} もう一度だけ | {} もういちどだけ | {}, nur noch einmal
H h {}と 踊ろう 朝まで | {}と おどろう あさまで | {}, lass uns bis zum Morgen tanzen
H d 遠ざかる {} | とおざかる {} | Du entfernst dich, {}
"""

LINES = {
    "liebe": """
V h 交差点で 君を見つけた | こうさてんで きみおみつけた | An der Kreuzung habe ich dich entdeckt
V h 春の風が 背中を押した | はるのかぜが せなかおおした | Der Frühlingswind hat mich angeschoben
V n 目が合うたび 胸が鳴るの | めがあうたび むねがなるの | Jedes Mal, wenn sich unsere Blicke treffen, klopft mein Herz
V n 言いかけた言葉 飲み込んで | いいかけたことば のみこんで | Das Wort, das ich fast gesagt hätte, schlucke ich hinunter
V d 窓の外 雨が降り出した | まどのそと あめがふりだした | Draußen vor dem Fenster fängt es an zu regnen
V n 君の笑顔 思い出してる | きみのえがお おもいだしてる | Ich denke an dein Lächeln
V h 同じ歌を 口ずさんだ | おなじうたお くちずさんだ | Wir haben dasselbe Lied gesummt
V d 送れないまま 消したメッセージ | おくれないまま けしためっせーじ | Die Nachricht, die ich nie abschickte, habe ich gelöscht
V n 帰り道 少し遠回り | かえりみち すこしとおまわり | Auf dem Heimweg mache ich einen kleinen Umweg
V h 隣で笑う 君がいた | となりでわらう きみがいた | Du warst da und hast neben mir gelacht
V d 本当の気持ち 隠してた | ほんとうのきもち かくしてた | Meine wahren Gefühle habe ich versteckt
V n 夕焼けが 二人を染めた | ゆうやけが ふたりおそめた | Das Abendrot hat uns beide gefärbt
V h 君の名前を そっと呼んだ | きみのなまえお そっとよんだ | Ganz leise habe ich deinen Namen gerufen
V d 届かない 想いばかり 増えて | とどかない おもいばかり ふえて | Nur die Gefühle, die dich nicht erreichen, werden mehr
V n 指先が 少し触れた | ゆびさきが すこしふれた | Unsere Fingerspitzen haben sich kurz berührt
V h 明日[あした]も会える それだけで | あしたもあえる それだけで | Dass ich dich morgen wiedersehe, reicht mir schon
V d 君の隣は わたしじゃない | きみのとなりわ わたしじゃない | Neben dir ist nicht mein Platz
V n 何度も 読み返した手紙 | なんども よみかえしたてがみ | Den Brief habe ich immer wieder gelesen
V h 心が ふわり 浮かんでく | こころが ふわり うかんでく | Mein Herz schwebt leicht davon
V d 眠れない夜に 君を想う | ねむれないよるに きみおおもう | In schlaflosen Nächten denke ich an dich
V n 改札の前で 手を振った | かいさつのまえで ておふった | Vor der Sperre habe ich dir gewinkt
V h 君がくれた 小さな勇気 | きみがくれた ちいさなゆうき | Der kleine Mut, den du mir gegeben hast
V d 嘘でもいいから 好きと言って | うそでもいいから すきといって | Sag, dass du mich liebst, auch wenn es gelogen ist
V n 時計の針が 進まない | とけいのはりが すすまない | Die Uhrzeiger bewegen sich nicht
V h 偶然を 運命と呼びたい | ぐうぜんお うんめいとよびたい | Ich möchte den Zufall Schicksal nennen
V d 君の香りが まだ残る | きみのかおりが まだのこる | Dein Duft ist immer noch da
P n もう少しだけ 近づきたい | もうすこしだけ ちかづきたい | Ich will dir nur ein bisschen näher kommen
P h 鼓動が 速くなっていく | こどうが はやくなっていく | Mein Herzschlag wird immer schneller
P d 言えないまま 季節が過ぎる | いえないまま きせつがすぎる | Ungesagt ziehen die Jahreszeiten vorbei
P n 胸の奥で 何[なに]かが鳴る | むねのおくで なにかがなる | Tief in meiner Brust klingt etwas
P h 今なら 言える気がする | いまなら いえるきがする | Jetzt könnte ich es sagen, glaube ich
P d 遠すぎて 手が届かない | とおすぎて てがとどかない | Du bist zu weit weg, ich erreiche dich nicht
P n 確かめたいよ 君の気持ち | たしかめたいよ きみのきもち | Ich will wissen, was du fühlst
P h 世界が 色づいていく | せかいが いろづいていく | Die Welt bekommt Farbe
P d 涙が こぼれそうで | なみだが こぼれそうで | Mir kommen gleich die Tränen
P n ほら 風が 変わった | ほら かぜが かわった | Sieh, der Wind hat sich gedreht
P h 一歩[いっぽ]だけ 踏み出してみる | いっぽだけ ふみだしてみる | Ich wage einen einzigen Schritt
P d 答えなんて 知りたくない | こたえなんて しりたくない | Die Antwort will ich gar nicht wissen
C h 好きだよって 叫びたい | すきだよって さけびたい | Ich will laut rufen, dass ich dich liebe
C h 君と二人 どこまでも | きみとふたり どこまでも | Du und ich, wohin auch immer
C n この想い 隠せない | このおもい かくせない | Dieses Gefühl kann ich nicht verbergen
C d 届かなくても 好きでいる | とどかなくても すきでいる | Auch wenn es dich nicht erreicht, liebe ich dich weiter
C h 世界中[せかいじゅう]に 響かせたい | せかいじゅうに ひびかせたい | Ich will es in der ganzen Welt erklingen lassen
C n 君の隣で 笑いたい | きみのとなりで わらいたい | Ich will neben dir lachen
C d 叶わなくても 忘れない | かなわなくても わすれない | Auch wenn es nicht wahr wird, vergesse ich es nicht
C h 恋をしたんだ 今 ここで | こいおしたんだ いま ここで | Ich habe mich verliebt, jetzt, hier
C n 何度でも 君に会いたい | なんどでも きみにあいたい | Ich will dich wieder und wieder sehen
C d 涙の数だけ 強くなる | なみだのかずだけ つよくなる | Mit jeder Träne werde ich stärker
C h 手をつないで 走りだそう | ておつないで はしりだそう | Lass uns Hand in Hand loslaufen
C n ずっと ずっと 君がいい | ずっと ずっと きみがいい | Für immer, für immer will ich dich
C d 胸が痛いほど 君が好き | むねがいたいほど きみがすき | Ich liebe dich so sehr, dass es weh tut
C h 恋の魔法 解けないで | こいのまほう とけないで | Liebeszauber, lös dich nicht auf
C n 二人だけの 秘密の歌 | ふたりだけの ひみつのうた | Unser geheimes Lied, nur für uns zwei
C d さよならより 先に 抱きしめて | さよならより さきに だきしめて | Umarme mich, bevor wir Lebewohl sagen
B n もしも 君が いなかったら | もしも きみが いなかったら | Wenn es dich nicht gäbe
B d 夜明け前が 一番 寒い | よあけまえが いちばん さむい | Vor der Morgendämmerung ist es am kältesten
B h 雨上がりの 虹を 見に行こう | あめあがりの にじお みにいこう | Lass uns nach dem Regen den Regenbogen ansehen
B n 遠回りした 時間も 宝物[たからもの] | とおまわりした じかんも たからもの | Auch die Umwege sind ein Schatz
B d 壊れそうな 心 抱えて | こわれそうな こころ かかえて | Mit einem Herzen, das fast zerbricht
B h 怖くないよ 君がいるから | こわくないよ きみがいるから | Ich habe keine Angst, weil du da bist
B n 季節が 巡っても | きせつが めぐっても | Auch wenn die Jahreszeiten vergehen
B d 最後に一度だけ 名前を呼んで | さいごにいちどだけ なまえおよんで | Ruf ein letztes Mal meinen Namen
B h 君が笑えば 世界が晴れる | きみがわらえば せかいがはれる | Wenn du lachst, wird die Welt klar
B n 言葉より 確かなもの | ことばより たしかなもの | Etwas, das sicherer ist als Worte
B d 忘れたふりは もうできない | わすれたふりわ もうできない | Ich kann nicht mehr so tun, als hätte ich es vergessen
B h 遠い未来も 君と見たい | とおいみらいも きみとみたい | Auch die ferne Zukunft will ich mit dir sehen
""",
    "abschied": """
V n 桜並木を 一人で歩く | さくらなみきお ひとりであるく | Allein gehe ich die Kirschbaumallee entlang
V d 空っぽの部屋に 夕陽が差す | からっぽのへやに ゆうひがさす | In das leere Zimmer fällt die Abendsonne
V n 古い写真 色あせてた | ふるいしゃしん いろあせてた | Das alte Foto war verblasst
V h 笑い合った 放課後の道 | わらいあった ほうかごのみち | Der Weg nach der Schule, auf dem wir zusammen lachten
V d 最後の言葉 思い出せない | さいごのことば おもいだせない | Ich kann mich an die letzten Worte nicht erinnern
V n 改札を抜けて 振り返る | かいさつおぬけて ふりかえる | Ich gehe durch die Sperre und schaue zurück
V d 君のいない 春が来た | きみのいない はるがきた | Ein Frühling ohne dich ist gekommen
V h 黒板の 落書きのまま | こくばんの らくがきのまま | So wie das Gekritzel an der Tafel
V n 電車の窓に 映る街 | でんしゃのまどに うつるまち | Die Stadt, die sich im Zugfenster spiegelt
V d 鍵を返して 扉を閉めた | かぎおかえして とびらおしめた | Ich gab den Schlüssel zurück und schloss die Tür
V n 段ボールに 詰めた日々 | だんぼーるに つめたひび | Die Tage, die ich in Kartons gepackt habe
V h 夏の終わりの 約束を | なつのおわりの やくそくお | Das Versprechen vom Ende des Sommers
V d 寂しいなんて 言えなかった | さびしいなんて いえなかった | Dass ich einsam bin, konnte ich nicht sagen
V n 時計の針を 戻せたら | とけいのはりお もどせたら | Wenn ich die Uhr zurückdrehen könnte
V h 卒業式の 青い空 | そつぎょうしきの あおいそら | Der blaue Himmel bei der Abschlussfeier
V d 返事のない 手紙を書く | へんじのない てがみおかく | Ich schreibe einen Brief, auf den keine Antwort kommt
V n 君の声が 遠くなる | きみのこえが とおくなる | Deine Stimme wird immer leiser
V h 秘密基地は もうないけど | ひみつきちわ もうないけど | Unser Geheimversteck gibt es nicht mehr, aber
V d ホームに一人 立ち尽くす | ほーむにひとり たちつくす | Allein stehe ich wie erstarrt auf dem Bahnsteig
V n 見慣れた景色が 変わってく | みなれたけしきが かわってく | Die vertraute Landschaft verändert sich
V h ふざけて撮った 写真がある | ふざけてとった しゃしんがある | Es gibt Fotos, die wir aus Spaß gemacht haben
V d 君の席は 空いたまま | きみのせきわ あいたまま | Dein Platz bleibt leer
V n 春風[はるかぜ]が 髪を揺らす | はるかぜが かみおゆらす | Der Frühlingswind spielt mit meinem Haar
V h ありがとうを言いそびれた | ありがとうおいいそびれた | Danke zu sagen habe ich verpasst
V d 涙の跡を 隠して笑う | なみだのあとお かくしてわらう | Ich verstecke die Tränenspuren und lache
V n 同じ空の下 君はいる | おなじそらのした きみわいる | Unter demselben Himmel bist du
P n 振り向いたら 泣いてしまう | ふりむいたら ないてしまう | Wenn ich mich umdrehe, muss ich weinen
P d 引き止める言葉 探してた | ひきとめることば さがしてた | Ich suchte nach Worten, um dich aufzuhalten
P h 笑顔で 送り出したい | えがおで おくりだしたい | Ich will dich mit einem Lächeln verabschieden
P n 発車のベルが 鳴り響く | はっしゃのべるが なりひびく | Die Abfahrtsglocke schrillt
P d 行かないでって 言えなくて | いかないでって いえなくて | Ich konnte nicht sagen: Geh nicht
P h 新しい季節が 呼んでる | あたらしいきせつが よんでる | Eine neue Jahreszeit ruft
P n 手を振る君が 小さくなる | ておふるきみが ちいさくなる | Du winkst und wirst immer kleiner
P d 心に穴が あいたみたい | こころにあなが あいたみたい | Als hätte mein Herz ein Loch
P h 前を向いて 歩きだそう | まえおむいて あるきだそう | Lass uns nach vorn schauen und losgehen
P n 最後に一つ 聞かせてよ | さいごにひとつ きかせてよ | Sag mir zum Schluss noch eins
P d 時間よ 止まって | じかんよ とまって | Zeit, bleib stehen
P h 涙は ここに置いていく | なみだわ ここにおいていく | Die Tränen lasse ich hier
C d さよなら 大好きな人 | さよなら だいすきなひと | Leb wohl, mein liebster Mensch
C n 忘れないよ 君のこと | わすれないよ きみのこと | Ich vergesse dich nicht
C h ありがとう 出会えたこと | ありがとう であえたこと | Danke, dass wir uns begegnet sind
C d 戻れない日々を 抱きしめて | もどれないひびお だきしめて | Ich halte die Tage fest, zu denen es kein Zurück gibt
C h 笑顔のままで 手を振るよ | えがおのままで ておふるよ | Mit einem Lächeln winke ich dir zu
C n 遠く離れても 同じ空 | とおくはなれても おなじそら | Auch weit weg ist es derselbe Himmel
C d 君がいた 季節が終わる | きみがいた きせつがおわる | Die Jahreszeit, in der du da warst, endet
C h また会う日まで 元気でね | またあうひまで げんきでね | Mach's gut bis zum Wiedersehen
C n 思い出が 背中を押す | おもいでが せなかおおす | Die Erinnerungen schieben mich an
C d 涙が止まらない 今日だけは | なみだがとまらない きょうだけわ | Nur heute hören die Tränen nicht auf
C h 桜舞う道で また会おう | さくらまうみちで またあおう | Auf dem Weg mit fallenden Kirschblüten sehen wir uns wieder
C n 胸の中で 生きている | むねのなかで いきている | Du lebst in meinem Herzen weiter
C d 最後まで 言えなかった 好き | さいごまで いえなかった すき | Das „Ich liebe dich“, das ich bis zuletzt nicht sagen konnte
C h 新しい道で 輝いて | あたらしいみちで かがやいて | Leuchte auf deinem neuen Weg
C n ありふれた 日々が 宝物[たからもの] | ありふれた ひびが たからもの | Die gewöhnlichen Tage sind ein Schatz
C d 君のいない 未来へ | きみのいない みらいえ | In eine Zukunft ohne dich
B n もしも時間が 戻るなら | もしもじかんが もどるなら | Wenn die Zeit zurücklaufen könnte
B d 本当は ずっと 怖かった | ほんとうわ ずっと こわかった | In Wahrheit hatte ich die ganze Zeit Angst
B h 君がくれた 全部が 力になる | きみがくれた ぜんぶが ちからになる | Alles, was du mir gegeben hast, gibt mir Kraft
B n 季節は巡り また春が来る | きせつわめぐり またはるがくる | Die Jahreszeiten drehen sich, wieder kommt der Frühling
B d 会いたいよ 今すぐに | あいたいよ いますぐに | Ich will dich sehen, sofort
B h いつか笑って 話せるよね | いつかわらって はなせるよね | Eines Tages können wir lachend darüber reden, oder?
B n 離れても 繋がってる | はなれても つながってる | Auch getrennt sind wir verbunden
B d 最後の夜に 星を数えた | さいごのよるに ほしおかぞえた | In der letzten Nacht habe ich die Sterne gezählt
B h 君の分まで 生きていく | きみのぶんまで いきていく | Ich lebe auch für dich weiter
B n 時が経てば 分かるのかな | ときがたてば わかるのかな | Werde ich es verstehen, wenn Zeit vergeht?
B d 声を聞かせて もう一度 | こえおきかせて もういちど | Lass mich deine Stimme noch einmal hören
B h さよならは始まりの言葉 | さよならわはじまりのことば | Lebewohl ist ein Wort des Anfangs
""",
    "sommer": """
V h 蝉の声が 響く午後 | せみのこえが ひびくごご | Ein Nachmittag, an dem die Zikaden zirpen
V h 自転車で 坂を下る | じてんしゃで さかおくだる | Mit dem Fahrrad fahre ich den Hang hinunter
V n 麦わら帽子 風[かぜ]に飛んだ | むぎわらぼうし かぜにとんだ | Der Strohhut ist im Wind davongeflogen
V h 青い海が 光ってる | あおいうみが ひかってる | Das blaue Meer glitzert
V n 浴衣の君に 見とれてた | ゆかたのきみに みとれてた | Ich konnte den Blick nicht von dir im Yukata lassen
V d 夏休みが 終わっていく | なつやすみが おわっていく | Die Sommerferien gehen zu Ende
V h ラムネの瓶を 鳴らして笑う | らむねのびんお ならしてわらう | Wir klappern mit der Limonadenflasche und lachen
V n 入道雲[にゅうどうぐも]が 背を伸ばす | にゅうどうぐもが せおのばす | Die Gewitterwolke reckt sich in die Höhe
V h 裸足で 砂浜を走る | はだしで すなはまおはしる | Barfuß renne ich über den Strand
V d 夕立の後 君がいない | ゆうだちのあと きみがいない | Nach dem Sommerregen bist du nicht mehr da
V n かき氷 半分こしよう | かきごおり はんぶんこしよう | Lass uns das Wassereis teilen
V h 日焼けした腕 伸ばしてみた | ひやけしたうで のばしてみた | Ich strecke meinen sonnengebräunten Arm aus
V d 夏の匂いが 胸を刺す | なつのにおいが むねおさす | Der Geruch des Sommers sticht mir ins Herz
V n 線香花火 落ちないで | せんこうはなび おちないで | Wunderkerze, fall nicht herunter
V h 君と行く 夏祭り | きみといく なつまつり | Mit dir zum Sommerfest
V n 風鈴の音 揺れている | ふうりんのおと ゆれている | Der Klang des Windspiels schwingt
V d 置いてきた 夏の約束 | おいてきた なつのやくそく | Das Sommerversprechen, das ich zurückließ
V h 冷たいサイダー 弾[はじ]ける泡 | つめたいさいだー はじけるあわ | Kalte Limonade, platzende Bläschen
V n 陽炎の中 君が揺れる | かげろうのなか きみがゆれる | Im Hitzeflimmern schwankst du
V h 波の音に 誘われて | なみのおとに さそわれて | Vom Rauschen der Wellen gelockt
V d 焼けたアスファルト 一人きり | やけたあすふぁると ひとりきり | Auf dem heißen Asphalt, ganz allein
V n 君の横顔 夕陽に溶ける | きみのよこがお ゆうひにとける | Dein Profil schmilzt in der Abendsonne
V h 夏空に 手を伸ばした | なつぞらに ておのばした | Ich streckte die Hand zum Sommerhimmel
V d 思い出だけが 焼き付いてる | おもいでだけが やきついてる | Nur die Erinnerungen haben sich eingebrannt
V n 遠くで 祭囃子が鳴る | とおくで まつりばやしがなる | In der Ferne spielt die Festmusik
V h 君の浴衣 金魚の柄 | きみのゆかた きんぎょのがら | Dein Yukata mit Goldfischmuster
P h 夜空が 開く その時 | よぞらが ひらく そのとき | In dem Moment, in dem sich der Nachthimmel öffnet
P n カウントダウン 始まるよ | かうんとだうん はじまるよ | Der Countdown beginnt
P d この夏が 終わる前に | このなつが おわるまえに | Bevor dieser Sommer endet
P h 胸が高鳴る 夏の夜 | むねがたかなる なつのよる | Eine Sommernacht, in der mein Herz schneller schlägt
P n 人混みの中 手を繋いだ | ひとごみのなか ておつないだ | Im Gedränge haben wir uns an den Händen gehalten
P d 言えなかった 言葉が 熱い | いえなかった ことばが あつい | Die ungesagten Worte brennen
P h もうすぐ 光が 咲くよ | もうすぐ ひかりが さくよ | Gleich blüht das Licht auf
P n 時間よ どうか 止まれ | じかんよ どうか とまれ | Zeit, bitte bleib stehen
P d 来年も ここにいるかな | らいねんも ここにいるかな | Ob wir nächstes Jahr wieder hier sind?
P h 走れ 走れ 夏の果てまで | はしれ はしれ なつのはてまで | Lauf, lauf bis ans Ende des Sommers
P n 見上げた空 息を止めて | みあげたそら いきおとめて | Ich schaue zum Himmel und halte den Atem an
P d 終わらないでと 願ってた | おわらないでと ねがってた | Ich wünschte mir, es möge nie enden
C h 夜空に咲いた 大輪の花 | よぞらにさいた たいりんのはな | Eine große Blume, die am Nachthimmel erblüht
C h 君と見上げた 夏の空 | きみとみあげた なつのそら | Der Sommerhimmel, zu dem wir aufsahen
C n 一瞬の光 焼き付けて | いっしゅんのひかり やきつけて | Das Licht eines Augenblicks brenne ich mir ein
C d 消えないで 夏の魔法 | きえないで なつのまほう | Verschwinde nicht, Sommerzauber
C h 最高の夏に しようよ | さいこうのなつに しようよ | Lass es uns zum besten Sommer machen
C n この瞬間を 忘れない | このしゅんかんお わすれない | Diesen Moment vergesse ich nicht
C d 散っていく 光の粒 | ちっていく ひかりのつぶ | Lichtkörner, die zerstieben
C h 弾[はじ]けるように 笑い合おう | はじけるように わらいあおう | Lass uns lachen, dass es nur so sprüht
C n 永遠みたいな 一瞬を | えいえんみたいな いっしゅんお | Einen Augenblick, der wie die Ewigkeit ist
C d 夏が終わっても 好きでいて | なつがおわっても すきでいて | Hab mich lieb, auch wenn der Sommer endet
C h 太陽みたいに 輝いて | たいようみたいに かがやいて | Leuchte wie die Sonne
C n 来年も 隣にいてね | らいねんも となりにいてね | Bleib auch nächstes Jahr an meiner Seite
C d 煙の向こう 君が遠い | けむりのむこう きみがとおい | Hinter dem Rauch bist du so weit weg
C h 夏の真ん中 飛び込もう | なつのまんなか とびこもう | Lass uns mitten in den Sommer springen
C n 心に咲いた 花火の音 | こころにさいた はなびのおと | Der Knall des Feuerwerks, das in meinem Herzen blühte
C d 季節の終わりに 泣かないで | きせつのおわりに なかないで | Weine nicht am Ende der Jahreszeit
B n 波が全部 さらっていく | なみがぜんぶ さらっていく | Die Wellen nehmen alles mit
B d 秋の風が もうすぐ来る | あきのかぜが もうすぐくる | Bald kommt der Herbstwind
B h 星が降るような 夜だから | ほしがふるような よるだから | Weil es eine Nacht ist, in der Sterne zu fallen scheinen
B n 砂に書いた 二人の名前 | すなにかいた ふたりのなまえ | Unsere Namen, in den Sand geschrieben
B d 祭りの後の 静けさに | まつりのあとの しずけさに | In der Stille nach dem Fest
B h もう一度 あの夏へ | もういちど あのなつえ | Noch einmal in jenen Sommer
B n 汗が光る 帰り道 | あせがひかる かえりみち | Der Heimweg, auf dem der Schweiß glänzt
B d 残り火だけが 揺れている | のこりびだけが ゆれている | Nur die Glut flackert noch
B h 子どもみたいに はしゃいでた | こどもみたいに はしゃいでた | Wir haben herumgetollt wie Kinder
B n 夕焼け色の サイダー瓶 | ゆうやけいろの さいだーびん | Eine abendrotfarbene Limonadenflasche
B d 君の影を 追いかけて | きみのかげお おいかけて | Ich jage deinem Schatten nach
B h この夏は 一度きり | このなつわ いちどきり | Diesen Sommer gibt es nur einmal
""",
    "nacht": """
V n ネオンの海を 泳いでる | ねおんのうみお およいでる | Ich schwimme durch ein Meer aus Neon
V d 濡れたアスファルト 光る信号 | ぬれたあすふぁると ひかるしんごう | Nasser Asphalt, leuchtende Ampeln
V n 傘も差さずに 歩いてた | かさもささずに あるいてた | Ich bin ohne Schirm gegangen
V d 終電の窓 映る僕 | しゅうでんのまど うつるぼく | Mein Spiegelbild im Fenster der letzten Bahn
V h 眠らない街が 呼んでいる | ねむらないまちが よんでいる | Die Stadt, die nie schläft, ruft
V n コンビニの灯り 白すぎて | こんびにのあかり しろすぎて | Das Licht im Kombini ist zu weiß
V d 雨音だけが 話しかける | あまおとだけが はなしかける | Nur das Regenrauschen spricht mit mir
V n 高架下[こうかした]で 君を待つ | こうかしたで きみおまつ | Unter der Hochbahn warte ich auf dich
V h 午前二時の 秘密の散歩 | ごぜんにじの ひみつのさんぽ | Ein geheimer Spaziergang um zwei Uhr morgens
V d 水たまりに 揺れる月 | みずたまりに ゆれるつき | Der Mond, der in der Pfütze zittert
V n イヤホンで 世界を消した | いやほんで せかいおけした | Mit Kopfhörern habe ich die Welt ausgeblendet
V h ビルの隙間に 星を探す | びるのすきまに ほしおさがす | Zwischen den Hochhäusern suche ich Sterne
V d 誰もいない 交差点 | だれもいない こうさてん | Eine Kreuzung, auf der niemand ist
V n 濡れた髪を かき上げて | ぬれたかみお かきあげて | Ich streiche mir das nasse Haar zurück
V h タクシーの赤いランプ 流れてく | たくしーのあかいらんぷ ながれてく | Die roten Lichter der Taxis ziehen vorbei
V d 冷めたコーヒー 一人きり | さめたこーひー ひとりきり | Kalter Kaffee, ganz allein
V n 窓を叩く 雨のリズム | まどおたたく あめのりずむ | Der Rhythmus des Regens, der ans Fenster klopft
V h 踊るように 雨を蹴る | おどるように あめおける | Ich trete in den Regen, als würde ich tanzen
V d 鳴らない電話 握りしめて | ならないでんわ にぎりしめて | Ich umklammere das Telefon, das nicht klingelt
V n 街灯の下 影が伸びる | がいとうのした かげがのびる | Unter der Straßenlaterne wird der Schatten lang
V h 夜風が 頬を撫でてく | よかぜが ほおおなでてく | Der Nachtwind streicht mir über die Wange
V d 傘を忘れた 君を思う | かさおわすれた きみおおもう | Ich denke an dich, wie du den Schirm vergessen hast
V n 地下鉄の風 背中に受けて | ちかてつのかぜ せなかにうけて | Den Wind der U-Bahn im Rücken
V h 夜の向こうへ 走り出す | よるのむこうえ はしりだす | Ich renne los, auf die andere Seite der Nacht
V d 雨に消えた 君の声 | あめにきえた きみのこえ | Deine Stimme, die im Regen verschwand
V n 赤い傘が 遠ざかる | あかいかさが とおざかる | Der rote Schirm entfernt sich
P n 雨が止む その前に | あめがやむ そのまえに | Bevor der Regen aufhört
P d 心まで 濡れてしまう | こころまで ぬれてしまう | Selbst mein Herz wird nass
P h 信号が 青に変わる | しんごうが あおにかわる | Die Ampel springt auf Grün
P n 誰かの声が 聞きたくて | だれかのこえが ききたくて | Weil ich irgendeine Stimme hören will
P d 朝が来なければ いいのに | あさがこなければ いいのに | Wenn nur der Morgen nicht käme
P h 夜が 僕らを 隠してく | よるが ぼくらお かくしてく | Die Nacht versteckt uns
P n ひとつ ふたつ 灯りが消える | ひとつ ふたつ あかりがきえる | Eins, zwei, die Lichter gehen aus
P d 傘の中 二人きり | かさのなか ふたりきり | Zu zweit unter dem Schirm
P h 鼓動と雨が 重なる | こどうとあめが かさなる | Herzschlag und Regen werden eins
P n 遠くで 雷が鳴った | とおくで かみなりがなった | In der Ferne hat es gedonnert
P d 涙か雨か 分からない | なみだかあめか わからない | Ich weiß nicht, ob es Tränen oder Regen sind
P h 今夜は 帰りたくない | こんやわ かえりたくない | Heute Nacht will ich nicht nach Hause
C h 雨の街で 踊ろうよ | あめのまちで おどろうよ | Lass uns in der Regenstadt tanzen
C n 真夜中の ネオンサイン | まよなかの ねおんさいん | Neonschilder um Mitternacht
C d 濡れたままで 抱きしめて | ぬれたままで だきしめて | Umarm mich, so nass, wie ich bin
C h 眠らない夜を 走り抜けて | ねむらないよるお はしりぬけて | Wir rennen durch die schlaflose Nacht
C n 光の粒が 降ってくる | ひかりのつぶが ふってくる | Lichtkörner fallen herab
C d 雨音に 隠した涙 | あまおとに かくしたなみだ | Tränen, versteckt im Regenrauschen
C h 夜明けまで 離さないで | よあけまで はなさないで | Lass mich bis zum Morgengrauen nicht los
C n この街の どこかで君が | このまちの どこかできみが | Irgendwo in dieser Stadt bist du
C d 傘はもう いらないよ | かさわもう いらないよ | Einen Schirm brauche ich nicht mehr
C h 夜空を 塗り替えよう | よぞらお ぬりかえよう | Lass uns den Nachthimmel neu anmalen
C n 青い信号 君へ続く | あおいしんごう きみえつづく | Grüne Ampeln führen zu dir
C d 止まない雨は ないけれど | やまないあめわ ないけれど | Jeder Regen hört irgendwann auf, aber
C h 都会の星に なりたいな | とかいのほしに なりたいな | Ich will ein Stern der Großstadt sein
C n 雨上がりの 街が光る | あめあがりの まちがひかる | Die Stadt glänzt nach dem Regen
C d ひとりぼっちの ミッドナイト | ひとりぼっちの みっどないと | Allein um Mitternacht
C h 手を伸ばせば 夜が明ける | ておのばせば よるがあける | Wenn ich die Hand ausstrecke, wird es Tag
B n 誰もが 孤独を 抱えて | だれもが こどくお かかえて | Jeder trägt seine Einsamkeit
B d 雨はまだ 止みそうにない | あめわまだ やみそうにない | Der Regen hört so bald nicht auf
B h 夜明けの色を 見に行こう | よあけのいろお みにいこう | Lass uns die Farbe der Morgendämmerung ansehen
B n 窓に書いた 君の名前 | まどにかいた きみのなまえ | Dein Name, ans Fenster geschrieben
B d 消えそうな 灯りを守る | きえそうな あかりおまもる | Ich beschütze das Licht, das gleich erlischt
B h 雲の隙間 月が笑う | くものすきま つきがわらう | Durch die Wolkenlücke lacht der Mond
B n この雨も いつか止む | このあめも いつかやむ | Auch dieser Regen hört irgendwann auf
B d 始発を待つ ホームの隅 | しはつおまつ ほーむのすみ | In der Ecke des Bahnsteigs, wartend auf den ersten Zug
B h 朝焼けが 街を染める | あさやけが まちおそめる | Das Morgenrot färbt die Stadt
B n 遠い街の 明かりが揺れる | とおいまちの あかりがゆれる | Die Lichter der fernen Stadt flackern
B d 濡れた手紙 読めないまま | ぬれたてがみ よめないまま | Der nasse Brief bleibt ungelesen
B h 傘を閉じて 空を見よう | かさおとじて そらおみよう | Lass uns den Schirm schließen und zum Himmel sehen
""",
    "traum": """
V h 小さな部屋で 夢を描いた | ちいさなへやで ゆめおえがいた | In einem kleinen Zimmer habe ich meinen Traum gemalt
V n ノートの隅の 落書きが | のーとのすみの らくがきが | Das Gekritzel am Rand des Heftes
V d 笑われても 諦めない | わらわれても あきらめない | Auch wenn sie mich auslachen, gebe ich nicht auf
V h 朝の光が 窓を叩く | あさのひかりが まどおたたく | Das Morgenlicht klopft ans Fenster
V n 地図にない道を 選んだ | ちずにないみちお えらんだ | Ich habe einen Weg gewählt, der auf keiner Karte steht
V d 転んだ数だけ 傷がある | ころんだかずだけ きずがある | Ich habe so viele Narben, wie ich hingefallen bin
V h スニーカーの紐 結び直す | すにーかーのひも むすびなおす | Ich binde meine Turnschuhe neu
V n 鏡の中の 自分に問う | かがみのなかの じぶんにとう | Ich frage mein Spiegelbild
V d 夜の机で 一人戦う | よるのつくえで ひとりたたかう | Nachts am Schreibtisch kämpfe ich allein
V h 憧れの背中を 追いかけて | あこがれのせなかお おいかけて | Ich jage meinem Vorbild hinterher
V n 遠い街の 名前を呼ぶ | とおいまちの なまえおよぶ | Ich rufe den Namen einer fernen Stadt
V d 不安ばかり 胸を占める | ふあんばかり むねおしめる | Die Angst füllt meine ganze Brust
V h 汗も涙も 力になる | あせもなみだも ちからになる | Schweiß und Tränen werden zu Kraft
V n ギター抱えて 旅に出る | ぎたーかかえて たびにでる | Mit der Gitarre im Arm gehe ich auf Reisen
V d 誰にも見えない 涙を拭く | だれにもみえない なみだおふく | Ich wische Tränen weg, die niemand sieht
V h 昨日の僕を 追い越して | きのうのぼくお おいこして | Ich überhole mein Ich von gestern
V n 夢の欠片を 拾い集める | ゆめのかけらお ひろいあつめる | Ich sammle die Scherben meines Traums
V d 届かない星に 手を伸ばす | とどかないほしに ておのばす | Ich strecke die Hand nach einem unerreichbaren Stern
V h 始まりの鐘が 鳴っている | はじまりのかねが なっている | Die Glocke des Anfangs läutet
V n 回り道も 悪くないさ | まわりみちも わるくないさ | Auch ein Umweg ist nicht schlecht
V d 負けそうな夜を 越えてきた | まけそうなよるお こえてきた | Ich habe Nächte überstanden, in denen ich fast aufgab
V h 新しい靴で 駆け出した | あたらしいくつで かけだした | Mit neuen Schuhen bin ich losgerannt
V n 白いページに 未来を書く | しろいぺーじに みらいおかく | Auf eine weiße Seite schreibe ich die Zukunft
V d 一人きりの 帰り道 | ひとりきりの かえりみち | Der Heimweg ganz allein
V h 夜明けの空が 背中を押す | よあけのそらが せなかおおす | Der Himmel im Morgengrauen schiebt mich an
V n 僕だけの 答えを探す | ぼくだけの こたえおさがす | Ich suche meine eigene Antwort
P h 怖くても 進むんだ | こわくても すすむんだ | Auch wenn ich Angst habe, gehe ich weiter
P n 心の声が 叫んでる | こころのこえが さけんでる | Die Stimme meines Herzens schreit
P d 何度 倒れても | なんど たおれても | Wie oft ich auch falle
P h 扉の向こうへ 行くんだ | とびらのむこうえ いくんだ | Ich gehe durch die Tür hinaus
P n 今 この瞬間に 賭けて | いま このしゅんかんに かけて | Ich setze alles auf diesen Moment
P d 震える手を 握りしめ | ふるえるてお にぎりしめ | Ich balle meine zitternde Hand
P h 風が 背中を押してる | かぜが せなかおおしてる | Der Wind schiebt mich an
P n 見えない明日[あした]を信じて | みえないあしたおしんじて | Ich glaube an ein Morgen, das ich nicht sehe
P d 弱い自分に さよなら | よわいじぶんに さよなら | Lebewohl, mein schwaches Ich
P h ほら 光が 見えてきた | ほら ひかりが みえてきた | Sieh, da kommt Licht in Sicht
P n 夢の続きを 見に行こう | ゆめのつづきお みにいこう | Lass uns sehen, wie der Traum weitergeht
P d 逃げ出したい 夜もあった | にげだしたい よるもあった | Es gab Nächte, in denen ich fliehen wollte
C h 走れ 未来へ 今すぐ | はしれ みらいえ いますぐ | Lauf in die Zukunft, sofort
C h 夢を 掴みに行こう | ゆめお つかみにいこう | Lass uns den Traum ergreifen
C n 誰も知らない 空の果てへ | だれもしらない そらのはてえ | Bis ans Ende des Himmels, das niemand kennt
C d 泣いた分だけ 強くなれ | ないたぶんだけ つよくなれ | Werde so viel stärker, wie du geweint hast
C h 光の中へ 飛び込もう | ひかりのなかえ とびこもう | Lass uns ins Licht springen
C n 僕らの物語は 続く | ぼくらのものがたりわ つづく | Unsere Geschichte geht weiter
C d 諦めないで 最後まで | あきらめないで さいごまで | Gib nicht auf, bis zum Schluss
C h 翼広げて 高く飛べ | つばさひろげて たかくとべ | Breite die Flügel aus und flieg hoch
C n 昨日より 遠くへ行ける | きのうより とおくえいける | Ich komme weiter als gestern
C d 傷だらけでも 前を向け | きずだらけでも まえおむけ | Auch voller Wunden, schau nach vorn
C h 世界中[せかいじゅう]に 届け この歌 | せかいじゅうに とどけ このうた | Erreich die ganze Welt, du mein Lied
C n まだ見ぬ景色を 探しに行こう | まだみぬけしきお さがしにいこう | Lass uns Landschaften suchen, die wir noch nicht kennen
C d 涙を力に 変えていく | なみだおちからに かえていく | Ich verwandle Tränen in Kraft
C h 夢の続きは ここから | ゆめのつづきわ ここから | Der Traum geht hier weiter
C n 一歩[いっぽ]ずつ 進んでいこう | いっぽずつ すすんでいこう | Lass uns Schritt für Schritt weitergehen
C d 負けないで 心の炎 | まけないで こころのほのお | Gib nicht auf, Flamme in meinem Herzen
B n 振り返れば 足跡が続く | ふりかえれば あしあとがつづく | Wenn ich zurückschaue, sehe ich meine Spuren
B d 本当は 泣きたかった | ほんとうわ なきたかった | In Wahrheit wollte ich weinen
B h 一人じゃないと 気づいたよ | ひとりじゃないと きづいたよ | Ich habe gemerkt, dass ich nicht allein bin
B n 遠回りした 日々にも 意味がある | とおまわりした ひびにも いみがある | Auch die Tage auf Umwegen haben einen Sinn
B d 暗闇の中 光を探す | くらやみのなか ひかりおさがす | Im Dunkeln suche ich das Licht
B h 夢は逃げない 君が走れば | ゆめわにげない きみがはしれば | Der Traum läuft nicht weg, wenn du rennst
B n 空はどこまでも 続いてる | そらわどこまでも つづいてる | Der Himmel geht endlos weiter
B d 迷っても 間違っても | まよっても まちがっても | Auch wenn ich mich verirre, auch wenn ich Fehler mache
B h 今 生まれ変わる時 | いま うまれかわるとき | Jetzt ist die Zeit, neu geboren zu werden
B n 小さな一歩[いっぽ]が 未来になる | ちいさないっぽが みらいになる | Ein kleiner Schritt wird zur Zukunft
B d 折れた翼も いつか治る | おれたつばさも いつかなおる | Auch gebrochene Flügel heilen irgendwann
B h 新しい朝が 来るよ | あたらしいあさが くるよ | Ein neuer Morgen kommt
""",
    "online": """
V d 真夜中の 青い画面 | まよなかの あおいがめん | Der blaue Bildschirm um Mitternacht
V n スクロールする 指が止まる | すくろーるする ゆびがとまる | Der scrollende Finger hält inne
V d 既読[きどく]がつかない メッセージ | きどくがつかない めっせーじ | Eine Nachricht, die keiner liest
V h 画面越しに 君と笑う | がめんごしに きみとわらう | Durch den Bildschirm lache ich mit dir
V n 通知の音で 目が覚める | つうちのおとで めがさめる | Der Benachrichtigungston weckt mich
V d いいねの数で 心を測る | いいねのかずで こころおはかる | Ich messe mein Herz an der Zahl der Likes
V n 名前も知らない 君の声 | なまえもしらない きみのこえ | Deine Stimme, und ich kenne nicht einmal deinen Namen
V h 電波に乗せて 歌を送る | でんぱにのせて うたおおくる | Ich schicke mein Lied über die Funkwellen
V d 充電が切れた 夜は長い | じゅうでんがきれた よるわながい | Der Akku ist leer, die Nacht ist lang
V n 加工した 笑顔の写真 | かこうした えがおのしゃしん | Ein bearbeitetes Foto meines Lächelns
V h 知らない誰かと 繋がった | しらないだれかと つながった | Ich habe mich mit jemandem verbunden, den ich nicht kenne
V d ログアウトしても 消えない | ろぐあうとしても きえない | Auch nach dem Ausloggen verschwindet es nicht
V n パスワードは君の誕生日[たんじょうび] | ぱすわーどわきみのたんじょうび | Das Passwort ist dein Geburtstag
V h ヘッドホンの中 君がいる | へっどほんのなか きみがいる | In meinen Kopfhörern bist du
V d 返信待ちの 午前三時 | へんしんまちの ごぜんさんじ | Drei Uhr morgens, wartend auf eine Antwort
V n 液晶の光 浴びている | えきしょうのひかり あびている | Ich bade im Licht des Displays
V h 絵文字ひとつで 救われた | えもじひとつで すくわれた | Ein einziges Emoji hat mich gerettet
V d 本当の僕は 誰も知らない | ほんとうのぼくわ だれもしらない | Mein wahres Ich kennt niemand
V n タイムラインが 流れてく | たいむらいんが ながれてく | Die Timeline fließt vorbei
V h ゼロとイチの 間で踊る | ぜろといちの あいだでおどる | Ich tanze zwischen Null und Eins
V d 画面の中でしか 泣けない | がめんのなかでしか なけない | Nur vor dem Bildschirm kann ich weinen
V n 圏外の空 見上げてる | けんがいのそら みあげてる | Ich schaue zum Himmel ohne Netz
V h ノイズの奥で 君が呼ぶ | のいずのおくで きみがよぶ | Hinter dem Rauschen rufst du mich
V d 消せない履歴 増えていく | けせないりれき ふえていく | Der Verlauf, den ich nicht löschen kann, wächst
V n ブルーライトに 溶けていく | ぶるーらいとに とけていく | Ich löse mich im Blaulicht auf
V h アバターの僕は 自由に飛ぶ | あばたーのぼくわ じゆうにとぶ | Mein Avatar fliegt frei
P d 既読[きどく]のままで 夜が明ける | きどくのままで よるがあける | Gelesen, unbeantwortet, und es wird Morgen
P n 指先ひとつで 終わる世界 | ゆびさきひとつで おわるせかい | Eine Welt, die mit einer Fingerspitze endet
P h 画面の向こうへ 手を伸ばす | がめんのむこうえ ておのばす | Ich strecke die Hand durch den Bildschirm
P n 本当の声を 聞かせてよ | ほんとうのこえお きかせてよ | Lass mich deine echte Stimme hören
P d 繋がるほど 一人になる | つながるほど ひとりになる | Je mehr ich verbunden bin, desto einsamer werde ich
P h 電源を切って 外へ出よう | でんげんおきって そとえでよう | Lass uns abschalten und rausgehen
P n 通知を全部 オフにした | つうちおぜんぶ おふにした | Ich habe alle Benachrichtigungen ausgeschaltet
P d 誰か 僕を見つけて | だれか ぼくおみつけて | Irgendwer, finde mich
P h 回線越しに 鼓動が鳴る | かいせんごしに こどうがなる | Über die Leitung schlägt ein Herz
P n 読み込み中の 心のまま | よみこみちゅうの こころのまま | Mit einem Herzen, das noch lädt
P d 未読のまま 眠りたい | みどくのまま ねむりたい | Ich will schlafen, ohne es gelesen zu haben
P h エラーだらけでも 進め | えらーだらけでも すすめ | Auch voller Fehler, geh weiter
C h 画面を割って 会いに行く | がめんおわって あいにいく | Ich zerbreche den Bildschirm und komme zu dir
C n 電波の海で 君を探す | でんぱのうみで きみおさがす | Im Meer der Funkwellen suche ich dich
C d 既読[きどく]スルーで 構わない | きどくするーで かまわない | Lies es ruhig und antworte nicht
C h 回線越しの ラブソング | かいせんごしの らぶそんぐ | Ein Liebeslied über die Leitung
C n ログインしたら 君がいた | ろぐいんしたら きみがいた | Als ich mich einloggte, warst du da
C d 繋がってるのに 一人きり | つながってるのに ひとりきり | Verbunden und doch allein
C h 世界中[せかいじゅう]に 拡散して | せかいじゅうに かくさんして | Verbreite es in der ganzen Welt
C n 画面越しでも 伝わるかな | がめんごしでも つたわるかな | Ob es dich auch durch den Bildschirm erreicht?
C d 通知を待って 夜が終わる | つうちおまって よるがおわる | Ich warte auf eine Nachricht, und die Nacht endet
C h ゼロから始まる 恋のコード | ぜろからはじまる こいのこーど | Ein Liebescode, der bei Null beginnt
C n 本当の僕を 見つけて | ほんとうのぼくお みつけて | Finde mein wahres Ich
C d 消えたアカウント 君の名前 | きえたあかうんと きみのなまえ | Ein gelöschtes Konto, dein Name
C h オフラインで 会いたいよ | おふらいんで あいたいよ | Ich will dich offline treffen
C n 光る画面に 願いを込めて | ひかるがめんに ねがいおこめて | Ich lege meinen Wunsch in den leuchtenden Bildschirm
C d 削除できない 想いがある | さくじょできない おもいがある | Es gibt Gefühle, die ich nicht löschen kann
C h 電波に乗って 君まで届け | でんぱにのって きみまでとどけ | Reite auf den Funkwellen bis zu dir
B n スマホを置いて 空を見た | すまほおおいて そらおみた | Ich legte das Handy weg und sah zum Himmel
B d 画面が割れて 僕が映る | がめんがわれて ぼくがうつる | Der Bildschirm ist zerbrochen, ich spiegle mich darin
B h 本物の声で 名前を呼んで | ほんもののこえで なまえおよんで | Ruf meinen Namen mit deiner echten Stimme
B n データじゃない 温もりが欲しい | でーたじゃない ぬくもりがほしい | Ich will Wärme, keine Daten
B d アカウントごと 消えたくなる | あかうんとごと きえたくなる | Ich möchte mitsamt meinem Konto verschwinden
B h 電源を落として 君に会う | でんげんおおとして きみにあう | Ich schalte ab und treffe dich
B n 誰かのいいねより 君の一言 | だれかのいいねより きみのひとこと | Lieber ein Wort von dir als irgendein Like
B d 残りわずかな バッテリー | のこりわずかな ばってりー | Der Akku ist fast leer
B h 画面の外に 春が来てた | がめんのそとに はるがきてた | Draußen vor dem Bildschirm war der Frühling gekommen
B n 圏外の場所で 待ってるよ | けんがいのばしょで まってるよ | Ich warte an einem Ort ohne Netz
B d 保存したままの 君の声 | ほぞんしたままの きみのこえ | Deine gespeicherte Stimme
B h ログアウトして 走り出す | ろぐあうとして はしりだす | Ich logge mich aus und renne los
""",
    "kampf": """
V n 灰色の空 裂いていく | はいいろのそら さいていく | Ich reiße den grauen Himmel auf
V d 錆びた剣を 握りしめる | さびたけんお にぎりしめる | Ich umklammere das rostige Schwert
V h 立ち上がれ 何度でも | たちあがれ なんどでも | Steh auf, immer wieder
V n 砂嵐の中 前を見る | すなあらしのなか まえおみる | Im Sandsturm schaue ich nach vorn
V d 傷だらけの 拳を上げて | きずだらけの こぶしおあげて | Ich hebe meine verwundete Faust
V h 鼓動が 戦えと叫ぶ | こどうが たたかえとさけぶ | Mein Herzschlag schreit: Kämpfe
V n 背負った過去を 振り払う | せおったかこお ふりはらう | Ich schüttle die Vergangenheit ab, die ich trage
V d 誰も信じられない夜 | だれもしんじられないよる | Eine Nacht, in der ich niemandem trauen kann
V h 燃える瞳で 睨みつけろ | もえるひとみで にらみつけろ | Starr sie mit brennenden Augen an
V n 崩れた壁を 乗り越えて | くずれたかべお のりこえて | Über die eingestürzte Mauer hinweg
V d 奪われたものを 取り戻す | うばわれたものお とりもどす | Ich hole mir zurück, was mir genommen wurde
V h 嵐の中を 駆け抜ける | あらしのなかお かけぬける | Ich renne durch den Sturm
V n 弱さを知って 強くなる | よわさおしって つよくなる | Wer seine Schwäche kennt, wird stark
V d 冷たい雨に 打たれても | つめたいあめに うたれても | Auch wenn kalter Regen auf mich prasselt
V h 限界なんて 越えてやる | げんかいなんて こえてやる | Grenzen überschreite ich einfach
V n 静かに燃える 青い炎 | しずかにもえる あおいほのお | Eine still brennende blaue Flamme
V d 倒れた仲間の 声がする | たおれたなかまの こえがする | Ich höre die Stimmen gefallener Freunde
V h 運命なんて ぶっ壊せ | うんめいなんて ぶっこわせ | Zerschlag das Schicksal
V n 刻まれた傷が 道を示す | きざまれたきずが みちおしめす | Die eingeritzten Narben zeigen den Weg
V d 暗闇が 僕を飲み込む | くらやみが ぼくおのみこむ | Die Dunkelheit verschlingt mich
V h 雷鳴が 合図を鳴らす | らいめいが あいずおならす | Der Donner gibt das Signal
V n 失うものは もう何[なに]もない | うしなうものわ もうなにもない | Ich habe nichts mehr zu verlieren
V d 心の鎖を 引きちぎる | こころのくさりお ひきちぎる | Ich reiße die Ketten meines Herzens ab
V h 叫べ 喉が枯れるまで | さけべ のどがかれるまで | Schrei, bis deine Stimme versagt
V n 夜明けを待たずに 走り出す | よあけおまたずに はしりだす | Ohne auf den Morgen zu warten, renne ich los
V d 折れそうな心 叩き起こす | おれそうなこころ たたきおこす | Ich rüttle mein fast gebrochenes Herz wach
P h 今こそ 立ち上がる時 | いまこそ たちあがるとき | Jetzt ist die Zeit aufzustehen
P n 震える足で 前へ | ふるえるあしで まええ | Mit zitternden Beinen nach vorn
P d 逃げ場なんて どこにもない | にげばなんて どこにもない | Es gibt nirgendwo einen Fluchtweg
P h 目を覚ませ 戦う時だ | めおさませ たたかうときだ | Wach auf, es ist Zeit zu kämpfen
P n 静寂を 切り裂いて | せいじゃくお きりさいて | Ich zerschneide die Stille
P d 迷いを捨てて 剣を抜け | まよいおすてて けんおぬけ | Lass den Zweifel fallen und zieh das Schwert
P h 炎が 体を走る | ほのおが からだおはしる | Feuer rast durch meinen Körper
P n カウントゼロで 飛び出せ | かうんとぜろで とびだせ | Bei null spring los
P d 涙なんか 見せはしない | なみだなんか みせわしない | Tränen zeige ich niemals
P h 拳を握れ 空へ | こぶしおにぎれ そらえ | Balle die Faust, zum Himmel
P n 息を吸って 目を開けろ | いきおすって めおあけろ | Atme ein und öffne die Augen
P d 終わりにはしない ここで | おわりにわしない ここで | Hier wird es nicht enden
C h 叫べ 叫べ 魂ごと | さけべ さけべ たましいごと | Schrei, schrei mit ganzer Seele
C h 運命を 撃ち抜け | うんめいお うちぬけ | Durchschieß das Schicksal
C n 燃え上がれ この炎 | もえあがれ このほのお | Lodere auf, du Flamme
C d 傷ついても 止まらない | きずついても とまらない | Auch verwundet halte ich nicht an
C h 限界を 越えていけ | げんかいお こえていけ | Geh über deine Grenzen hinaus
C n 誰にも 負けはしない | だれにも まけわしない | Ich verliere gegen niemanden
C d 闇を裂いて 光になれ | やみおさいて ひかりになれ | Zerreiß die Dunkelheit und werde Licht
C h 拳を突き上げろ 今 | こぶしおつきあげろ いま | Reck jetzt die Faust in die Luft
C n 何度でも 立ち上がれ | なんどでも たちあがれ | Steh immer wieder auf
C d 倒れても 牙を剥け | たおれても きばおむけ | Auch wenn du fällst, zeig die Zähne
C h 嵐を呼べ 雷よ鳴れ | あらしおよべ かみなりよなれ | Ruf den Sturm, Donner, grolle
C n 僕らの声で 世界を変えろ | ぼくらのこえで せかいおかえろ | Ändere die Welt mit unseren Stimmen
C d 痛みさえ 力に変えて | いたみさえ ちからにかえて | Selbst den Schmerz verwandle ich in Kraft
C h 未来を この手で掴め | みらいお このてでつかめ | Ergreif die Zukunft mit dieser Hand
C n 命を 燃やし尽くせ | いのちお もやしつくせ | Verbrenne dein Leben ganz
C d 最後の一人になっても | さいごのひとりになっても | Auch wenn sonst niemand mehr übrig ist
B n 守りたいものが ある | まもりたいものが ある | Es gibt etwas, das ich beschützen will
B d 本当は 怖かったんだ | ほんとうわ こわかったんだ | In Wahrheit hatte ich Angst
B h 背中を預ける 仲間がいる | せなかおあずける なかまがいる | Ich habe Freunde, denen ich meinen Rücken anvertraue
B n 静かな夜明け 剣を置く | しずかなよあけ けんおおく | Im stillen Morgengrauen lege ich das Schwert nieder
B d 失ったものを 数えない | うしなったものお かぞえない | Ich zähle nicht, was ich verloren habe
B h 光が 闇を貫く | ひかりが やみおつらぬく | Licht durchbohrt die Dunkelheit
B n 戦う理由を 思い出せ | たたかうりゆうお おもいだせ | Erinnere dich, warum du kämpfst
B d 血の味がする 風の中 | ちのあじがする かぜのなか | Im Wind, der nach Blut schmeckt
B h 誓いの言葉を 胸に刻め | ちかいのことばお むねにきざめ | Präge dir die Worte des Schwurs ins Herz
B n 遠い空で 誰かが待つ | とおいそらで だれかがまつ | Unter einem fernen Himmel wartet jemand
B d 崩れ落ちる 城の上で | くずれおちる しろのうえで | Auf der einstürzenden Burg
B h 最後の一撃 今 放て | さいごのいちげき いま はなて | Der letzte Schlag, entfessle ihn jetzt
""",
    "winter": """
V n 白い息が 空に溶ける | しろいいきが そらにとける | Der weiße Atem löst sich im Himmel auf
V h 初雪が 街を包む | はつゆきが まちおつつむ | Der erste Schnee hüllt die Stadt ein
V d かじかんだ手を ポケットに | かじかんだてお ぽけっとに | Die klammen Hände in der Tasche
V n イルミネーション 揺れる街 | いるみねーしょん ゆれるまち | Die Stadt mit den flackernden Lichterketten
V h 君と並んで 雪を踏む | きみとならんで ゆきおふむ | Neben dir stapfe ich durch den Schnee
V d 凍える夜に 君を想う | こごえるよるに きみおおもう | In der eisigen Nacht denke ich an dich
V n 窓の外は 一面の白 | まどのそとわ いちめんのしろ | Draußen ist alles weiß
V h マフラーを 君に巻いた | まふらーお きみにまいた | Ich wickelte dir meinen Schal um
V d 足跡が 一つだけ | あしあとが ひとつだけ | Nur eine einzige Fußspur
V n 温かい缶を 両手で包む | あたたかいかんお りょうてでつつむ | Ich halte die warme Dose mit beiden Händen
V h 雪だるまを 二人で作る | ゆきだるまお ふたりでつくる | Zu zweit bauen wir einen Schneemann
V d 冬の駅で 立ち止まる | ふゆのえきで たちどまる | Am Winterbahnhof bleibe ich stehen
V n 街路樹に 灯りがともる | がいろじゅに あかりがともる | In den Straßenbäumen gehen Lichter an
V h 頬を赤く 染めた君 | ほおおあかく そめたきみ | Du mit geröteten Wangen
V d 届かない 手紙が積もる | とどかない てがみがつもる | Briefe, die nie ankommen, stapeln sich wie Schnee
V n 静かに降る 粉雪の音 | しずかにふる こなゆきのおと | Das Geräusch des leise fallenden Pulverschnees
V h 星が近い 冬の夜 | ほしがちかい ふゆのよる | Eine Winternacht, in der die Sterne nah sind
V d 冷たい指先 震えてた | つめたいゆびさき ふるえてた | Die kalten Fingerspitzen zitterten
V n 暖炉の前で 本を読む | だんろのまえで ほんおよむ | Vor dem Kamin lese ich ein Buch
V h 雪の結晶 手のひらに | ゆきのけっしょう てのひらに | Eine Schneeflocke in meiner Handfläche
V d 凍った道で 一人転ぶ | こおったみちで ひとりころぶ | Allein rutsche ich auf dem vereisten Weg aus
V n 君のコートの ポケットの中 | きみのこーとの ぽけっとのなか | In der Tasche deines Mantels
V h 白い世界に 足跡つけて | しろいせかいに あしあとつけて | Ich hinterlasse Spuren in der weißen Welt
V d 雪に埋[う]もれた 約束 | ゆきにうもれた やくそく | Ein Versprechen, im Schnee begraben
V n 鐘の音が 遠く響く | かねのおとが とおくひびく | Glockenklang hallt aus der Ferne
V h 君の手を 握りしめた | きみのてお にぎりしめた | Ich hielt deine Hand ganz fest
P n 雪がやむ その前に | ゆきがやむ そのまえに | Bevor der Schnee aufhört
P h 鼓動で 胸が温かい | こどうで むねがあたたかい | Mein Herzschlag wärmt meine Brust
P d 寒さのせいに したくて | さむさのせいに したくて | Ich will es auf die Kälte schieben
P n 白い吐息 重ねたい | しろいといき かさねたい | Ich will unseren weißen Atem vereinen
P h 今夜 雪が 降るといいな | こんや ゆきが ふるといいな | Hoffentlich schneit es heute Nacht
P d 凍りついた 心のまま | こおりついた こころのまま | Mit erstarrtem Herzen
P n 時が止まる 雪の中 | ときがとまる ゆきのなか | Im Schnee bleibt die Zeit stehen
P h 寄り添えば 寒くないよ | よりそえば さむくないよ | Wenn wir uns aneinanderschmiegen, ist es nicht kalt
P d 溶けてしまう 前に言わなきゃ | とけてしまう まえにいわなきゃ | Ich muss es sagen, bevor es schmilzt
P n 鐘が鳴ったら 伝えよう | かねがなったら つたえよう | Wenn die Glocke läutet, sag ich es dir
P h 冬の星座が 瞬[またた]いた | ふゆのせいざが またたいた | Die Wintersternbilder funkelten
P d 春なんて 来なければいい | はるなんて こなければいい | Wenn doch nur kein Frühling käme
C h 降り積もる 想いを君へ | ふりつもる おもいおきみえ | Meine Gefühle häufen sich wie Schnee, für dich
C h 白い世界で 抱きしめて | しろいせかいで だきしめて | Umarm mich in der weißen Welt
C n 粉雪のように 舞い踊れ | こなゆきのように まいおどれ | Tanze wie Pulverschnee
C d 溶けないで この想い | とけないで このおもい | Schmilz nicht, du mein Gefühl
C h 君がいれば 冬も暖かい | きみがいれば ふゆもあたたかい | Wenn du da bist, ist selbst der Winter warm
C n 星降る夜に 願いをかけた | ほしふるよるに ねがいおかけた | In der Sternennacht habe ich mir etwas gewünscht
C d 雪が全部 隠してくれる | ゆきがぜんぶ かくしてくれる | Der Schnee versteckt alles
C h 二人の足跡 どこまでも | ふたりのあしあと どこまでも | Unsere Fußspuren, endlos weit
C n 白い息で 君を呼ぶ | しろいいきで きみおよぶ | Mit weißem Atem rufe ich dich
C d 凍えた心 温めて | こごえたこころ あたためて | Wärme mein erfrorenes Herz
C h 輝く街で 踊ろうよ | かがやくまちで おどろうよ | Lass uns in der funkelnden Stadt tanzen
C n この冬を 忘れない | このふゆお わすれない | Diesen Winter vergesse ich nicht
C d 春が来たら 消えてしまう | はるがきたら きえてしまう | Wenn der Frühling kommt, verschwindet es
C h 雪の花を 君に贈る | ゆきのはなお きみにおくる | Ich schenke dir eine Schneeblume
C n 静かな夜に 鐘が鳴る | しずかなよるに かねがなる | In der stillen Nacht läutet die Glocke
C d 一人きりの ホワイトクリスマス | ひとりきりの ほわいとくりすます | Weiße Weihnachten ganz allein
B n 雪解けの音が 聞こえる | ゆきどけのおとが きこえる | Ich höre die Schneeschmelze
B d 白い景色に 一人きり | しろいけしきに ひとりきり | Allein in der weißen Landschaft
B h 春になっても 隣にいて | はるになっても となりにいて | Bleib an meiner Seite, auch wenn es Frühling wird
B n 凍った湖 星を映す | こおったみずうみ ほしおうつす | Der zugefrorene See spiegelt die Sterne
B d 消えた温もり 探してる | きえたぬくもり さがしてる | Ich suche die verschwundene Wärme
B h 吹雪の中でも 迷わない | ふぶきのなかでも まよわない | Selbst im Schneesturm verirre ich mich nicht
B n 長い夜も いつか明ける | ながいよるも いつかあける | Auch die lange Nacht endet irgendwann
B d 雪の下で 眠る花 | ゆきのしたで ねむるはな | Eine Blume, die unter dem Schnee schläft
B h 君の笑顔が 雪を溶かす | きみのえがおが ゆきおとかす | Dein Lächeln schmilzt den Schnee
B n 窓に書いた 小さなハート | まどにかいた ちいさなはーと | Ein kleines Herz, ans Fenster gemalt
B d 最後の雪が 舞い落ちる | さいごのゆきが まいおちる | Der letzte Schnee fällt tanzend herab
B h 春を待つ 木々のように | はるおまつ きぎのように | Wie die Bäume, die auf den Frühling warten
""",
}
