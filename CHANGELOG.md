# Was ist neu

Jede Version hat hier einen Abschnitt. Die App zeigt ihn einmal nach einem Update (Hilfe › Was ist neu).

## 1.6.1

Fehler behoben, die beim Durchsehen des ganzen Projekts nach 1.6.0 aufgefallen sind. Neue Funktionen gibt es keine, an
deinen Einstellungen ändert sich nichts.

- **Handy und PC erzeugten gleichzeitig.** Mit dem Handy als Fernbedienung (oder zwei offenen Fenstern) ließ sich auf
  jedem Gerät ein Song starten, während der andere noch lief. Beide schrieben in denselben Ausgabeordner, also
  überschrieben sie sich die Spuren, und „Abbrechen“ auf einem Gerät brach beide ab. Jetzt entsteht immer nur ein Song
  auf einmal; das andere Gerät sagt „Auf einem anderen Gerät … entsteht gerade ein Song“. Das gilt für Song, Album,
  Hooks, Stimmen-Casting, Remix, Video, YouTube-Paket, Wieder öffnen und das Hör-Duell.
- **Zugangscode fürs Handy sicherer:** Nach acht falschen Codes wartete ein Gerät immer nur eine Minute; wer im WLAN
  lange genug probierte, hätte die sechs Ziffern in ein paar Wochen gefunden. Jetzt dauert jede weitere Sperre doppelt
  so lange (2, 4, 8 … Minuten, höchstens eine Stunde). Der richtige Code setzt das zurück.
- **Musikvideo schneller:** Für die Wellenform maß jedes Bild den lautesten Moment des ganzen Songs neu. Bei einem Song
  von vier Minuten kostete das etwa eine Minute pro Video; jetzt wird er einmal gemessen.
- **KI-Bilder gehören zu ihrem Song:** Alle Songs teilen sich den Ausgabeordner, und ein neuer Song im selben Stil (mit
  denselben Bildern im Text) bekam die Bilder des vorigen. Jetzt malt jeder Song seine eigenen; ein zweites Video
  desselben Songs nimmt weiter die schon gemalten.
- **Nach einem Update** ergänzt die Setup.exe jetzt auch die KI-Bilder um neue Pakete, wie schon die Bewertung.
- **Video-Link messen:** Scheiterte die Messung mit einem Fehler ohne Text, blieb die Meldung aus.

## 1.6.0

Diese Version macht die App einfacher und fragt mehr dein Ohr: eine einfache Ansicht mit drei Qualitätsstufen, ein
Hör-Duell, das blind vergleicht, ein Text-Baukasten ohne KI, eine Spannungskurve für den Ablauf, Video-Links als
Vorbild und das Handy als Fernbedienung. Dazu arbeitet die App nicht mehr in OneDrive. Ohne Zeichnung, mit der
Stimmung in der Mitte und in der Profi-Ansicht klingt jeder Song wie in 1.5.

**Einfach anfangen** (oben „Einfach“ und „Profi“)

- **Einfache Ansicht** (ab Werk an): Stil, Stimmung (ruhig bis wild), Stimme, Länge, Qualität, Text und „Song
  machen“. Alles andere bleibt, wie es in der Profi-Ansicht (den Tabs) steht.
- **Qualität:** Schnell (ohne Melodiesuche, Verstärker-Modelle und Hör-Check), Gut (alles, was an ist, die Stimme
  singt einmal) oder Beste (die Stimme singt zweimal, aus jeder Phrase zählt die sauberste Fassung). Eine Stufe schaltet
  nur ab, nie etwas ein, das du ausgeschaltet hast. Unter der Stufe steht, wie lange der letzte Song damit dauerte.
- **Was steckt in diesem Song?** (Tab Verlauf, ⓘ bei jedem Song): Stil, Tempo, Tonart, Stimme, gewürfelter Charakter,
  Akkorde, welche Schalter an und aus waren und was anders ist als jetzt.

**Hör-Duell** (unter dem Player und in der einfachen Ansicht)

- Der Refrain deines Songs entsteht zweimal, einmal mit und einmal ohne eine Funktion, gleich laut und blind (A und B
  werden ausgelost). Du sagst „A besser“, „B besser“ oder „gleich“; am Ende übernimmt die App die Gewinner. 40
  Funktionen aus Stimme, Melodie, Klang und Mix stehen zur Wahl.
- **Aufgeräumt** (Pfade › App, „Schalter ausblenden, die im Hör-Duell keinen Unterschied machten“): was im Duell
  „gleich“ klang, ist aus und verschwindet aus den Tabs.

**Text-Baukasten** (Tab Text „Text-Baukasten“, in der einfachen Ansicht „Text bauen“)

- Setzt einen japanischen Liedtext aus 600 von Hand geschriebenen Bausteinen zusammen, ohne KI: acht Themen (Liebe,
  Abschied, Sommer, Nacht, Traum, Online, Kampf, Winter), drei Stimmungen und ein Titelwort aus der Liste oder ein
  eigenes.
- Passend zu Ablauf und Tempo: so viele Zeilen, wie die Melodie Phrasen singt, so viele Silben, wie bequem
  hineinpassen, Reime am Zeilenende, das Titelwort am Anfang und Ende des Refrains, eigener Text für die zweite
  Strophe und unter jeder Zeile die deutsche Übersetzung fürs Video. Jede Zeile lässt sich einzeln tauschen.
- Jede Zeile ist geprüft: die App singt sie so, wie sie gemeint ist, mit und ohne „Partikel erkennen“.

**Spannungskurve** (Tab Song, unter dem Ablauf, `--ohne-spannungskurve`)

- Ein Regler pro Sektion, auch pro Wiederholung (der zweite Refrain anders als der erste). Höher: kräftigeres
  Schlagzeug, mehr Fills und Becken, die Band voller und im Mix lauter. Tiefer: weicher, Bläser, Glocken, Gegenstimme
  und Percussion setzen aus, im Mix leiser; ganz unten spielt die erste Hälfte als Breakdown ohne Schlagzeug.
- Die **Stimmung** der einfachen Ansicht verschiebt alle Sektionen, die du nicht gezogen hast.

**Video-Link als Vorbild** (Tab Song, bei den Vorbildern, ab Werk aus)

- Statt einer Datei ein Link (YouTube, Niconico, SoundCloud, Bilibili …): die App lädt nur den Ton in einen
  temporären Ordner, misst Tempo, Tonart, Stil, Ablauf und Akkorde und löscht ihn wieder. Drei Knöpfe übernehmen
  Tempo und Tonart, den Stil oder Ablauf und Akkorde für deinen Song. Mastering nach Vorbild braucht weiter die Datei.
- YouTube erlaubt das Herunterladen nur, wo es selbst einen Knopf dafür anbietet: gedacht für eigene Videos und solche,
  deren Rechteinhaber zustimmt.

**Speicher**

- **Nicht mehr in OneDrive** (Pfade › App, `--arbeit-im-ausgabeordner` schaltet es ab): liegt der Ausgabeordner in
  OneDrive, arbeitet die App in `%LOCALAPPDATA%\Vloid Songs` (Spuren, Gesang zum Wiederverwenden, Verlauf, Projekte).
  Der alte Verlauf bleibt sichtbar, jede fertige MP3 kommt zusätzlich in den Unterordner `MP3` im OneDrive-Ordner.
- **Warnung bei wenig Platz:** unter 5 GB frei warnt die App vor dem Erzeugen und im Systemcheck.

**Handy als Fernbedienung** (Hilfe › Handy als Fernbedienung, ab Werk aus)

- Die App ist im WLAN erreichbar (Port 8090). Handy oder Tablet scannen den QR-Code und bedienen sie im Browser: Text
  tippen, Song erzeugen, anhören, mit „MP3 aufs Handy“ herunterladen. Dateien (Vorbilder, Summen, eigene Gesangsspur)
  lädt man hoch. Die Seite steht auf dem Handy untereinander, erst die Einstellungen, darunter der Player.
- Jedes andere Gerät als der PC braucht einen sechsstelligen Zugangscode (im QR-Code schon drin; der Browser merkt
  sich den Zugang 30 Tage). Nach acht falschen Codes wartet ein Gerät eine Minute. „Neuen Code würfeln“ sperrt alle
  Geräte wieder aus.
- Solange ein Song entsteht, schläft der PC nicht ein (auch beim Album über Nacht); der Bildschirm darf ausgehen.

**Behoben**

- README nennt die aktuelle Version, Anleitung und Testliste keine alte Setup-Datei und kein altes Update mehr.

## 1.5.0

Diese Version macht aus dem Lyric-Video ein Musikvideo, das dem Song folgt, bringt drei neue Stile, bessere Melodien
und Abläufe, eine Stimme, die mit dem Text atmet, und einen eigenen Produzentenstil. Jede Neuerung hat einen Schalter
und eine Option auf der Kommandozeile; alles aus klingt und sieht aus wie in 1.4.

**Musikvideo** (neuer Tab Video, `--ohne-musikvideo`)

- **Das Bild folgt dem Song:** jede Sektion ist ein eigener Akt (Strophe ruhig, Refrain hell und voll, Bridge
  anders), Bewegung auf Kick und Snare, dazu was gerade passiert. Die App schreibt dafür eine Songkarte
  (`songkarte.json`) mit Sektionen, Schlägen, Akkorden, Schlagzeug und Melodie.
- **Eine Szene pro Stil:** Anime-Opening (J-Pop), Glitch (Dark), Textkunst aus Zeichen wie ein altes Spiel (Kawaii),
  Bühne (Rock), Fenster bei Nacht (Ballade), 80er (City Pop), Kreis (Future Bass), Tunnel (Drum and Bass), Zimmer
  (Lo-Fi), Bühne mit Leuchtstäben (Idol), Wafuu, Art déco, Hyperpop. Jede Szene lässt sich für jeden Stil wählen.
- **Bewegung:** „wie der Stil“, „ruhig und elegant“ oder „viel Bewegung“ (`--video-bewegung`). Blitze nie öfter als
  dreimal pro Sekunde und nie grell.
- **Text:** wie du ihn geschrieben hast, mit Kanji und Wort für Wort eingefärbt, darunter die Romaji und deine
  Übersetzung. Die Übersetzung schreibst du im Tab Text in eine eigene Zeile mit „>“ davor unter die japanische; sie
  wird nicht gesungen.
- **Was im Bild ist:** Akkord mit dem nächsten, die Gesangsmelodie als Notenlinie, das Spektrum des Mixes, eine
  Ablaufleiste, Titelkarte und Abspann, und Bilder aus deinem Text (Regen bei 雨, Sterne bei 星, Chat-Blasen bei 既読):
  nur was im Text steht, damit nichts Unpassendes im Bild ist. Jedes davon mit eigenem Schalter.
- **Eigene Figur** (optional): ein PNG, das im Takt hüpft und den Mund öffnet, solange gesungen wird.
- **KI-Bild pro Sektion** (optional, Hilfe › Einrichten › KI-Bilder fürs Video, etwa 4 GB): LCM Dreamshaper malt für
  jede Sektion ein Bild passend zu Stil und Text.
- **Video-Vorschau (10 s)** ab dem ersten Refrain, in Sekunden statt Minuten. **YouTube-Kapitel** in der Beschreibung.

**Neue Stile**

- **Wafuu-Rock:** Rockband mit Shamisen, Koto und Shakuhachi, Taiko-Toms, Melodie in der japanischen Fünftonleiter.
- **Electro-Swing:** Walking Bass, Swing, Bläser und Four-on-the-Floor.
- **Hyperpop:** 808, wirbelnde Hi-Hats, Chip-Leads, Reese-Bass und große Sprünge.

**Songs**

- **Wie dieser Song** (Tab Song bei den Vorbildern, `--ohne-vorbild-ablauf`): die App misst das wichtigste Vorbild
  ganz durch, mit Tempo, Tonart, Ablauf (Intro, Strophe, Pre-Chorus, Refrain …), Takten und Akkorden als Stufen.
  „Ablauf und Akkorde übernehmen“ setzt sie für deinen Song; `--vom-vorbild` übernimmt sie mit.
- **Wichtige Wörter betonen** (`--ohne-schluesselwoerter`): „Beste Melodie suchen“ legt das Kernwort des Refrains
  hoch oder lang auf die betonte Zeit und gibt Gefühlswörtern wie 好き, 涙 und さよなら lange Töne.
- **Ohrwurm-Wertung** (`--ohne-ohrwurm`): im Refrain gewinnt die Fassung, deren erste Phrase leicht verändert
  wiederkommt und deren Anfangsmotiv zurückkehrt.
- **Refrains steigern sich** (`--ohne-refrain-steigerung`): der erste Refrain ist schlanker, der letzte spielt mit
  allem.

**Stimme** (Tab Gesang)

- **Ausdruck aus dem Text** (`--ohne-text-ausdruck`): Zeilen mit traurigen Wörtern singt sie leiser und dunkler,
  Zeilen mit lauten Wörtern kräftiger und heller.
- **Lange Töne leben** (`--ohne-schwellen`): gehaltene Töne mitten in der Phrase schwellen an.
- **Lebendige Doppelung** (`--ohne-lebendige-doppelung`): die Doppelung im Refrain wandert wie ein zweiter Take.
- **Hör-Check** (optional, Hilfe › Einrichten › Hör-Check, etwa 500 MB, `--ohne-hoercheck`): nach dem Singen hört eine
  japanische Spracherkennung ab, ob man jede Zeile versteht. Unter dem Player steht, welche Zeilen undeutlich sind und
  welche Wörter die App vielleicht falsch liest; Einzelheiten in `hoer_check.txt` im Songordner.
- Für die Stimme bringt weiter eine aktuelle NEUTRINO-Ausgabe am meisten (ab 3.2.2); Hilfe › Einrichten zeigt, welche
  du hast.

**Charakter**

- **J-Pop und Idol getrennt** (Tab Band, `--ohne-jpop-idol-trennung`): J-Pop Energy ist jetzt eine Anison-Band mit
  Gitarrenriff, Powerchords, Lead-Gitarre und Rock-Grooves und spielt keine „Royal Road“ mehr, sondern vi–IV–V–I,
  I–V–vi–IV und den Anlauf bVI–bVII vor dem Refrain. Idol-Pop bleibt Tanz-Pop mit Royal Road, jetzt mit
  Synth-Bläsern, Disco-Oktaven im Bass und Rufen wie aus dem Publikum vor dem Refrain.
- **Dein Produzentenstil** (Tab Band, `--produzent NAME`, `--ohne-produzent`): dein Name steht im Abspann, in der
  YouTube-Beschreibung und als Künstler der MP3 („Name feat. MERROW“). Jeder Song beginnt mit deinem Producer-Tag,
  vier Tönen aus deinem Namen (`--ohne-producer-tag`), im Erkennungsklang, der auch die Glocken spielt
  (`--erkennungsklang`). Deine typische Akkordwendung (`--akkordwendung`) spielt der Refrain in zwei von drei Songs.
  Die Lieblingsstimme für alle Stile wählst du im Tab Gesang.
- **Geschmack lernen** (Tab Verlauf, `--ohne-geschmack`): jeder Song im Verlauf hat einen Daumen für Klang, Melodie,
  Stimme und Groove. Die App würfelt danach öfter, was dir gefiel, und seltener, was nicht. Ein Song merkt sich den
  Geschmack, mit dem er entstand, damit derselbe Seed derselbe Song bleibt.
- **Stile mischen** (Tab Song, `--mische STIL --mischanteil 0.3`, `--ohne-stil-mischung`): ein zweiter Stil mit
  Anteil, etwa Rock mit 30 % Kawaii Chiptune. Ein Teil der Instrumente, Grooves und Akkordfolgen kommt aus ihm.

## 1.4.0

Diese Version gibt jedem Stil und jedem Song seinen eigenen Charakter und macht die Stimme schöner. Bis 1.3 teilten
sich alle Stile dieselben Akkordfolgen, dieselben Regeln für die Melodie und denselben Hall, und zwei Songs eines
Stils hatten dieselben Klänge und Grooves; deshalb klang so vieles ähnlich. Jede Neuerung hat einen Schalter und eine
Option auf der Kommandozeile; alles aus klingt wie in 1.3.

**Charakter je Stil**

- **Akkorde je Stil** (Tab Song, `--ohne-stil-akkorde`): eigene Akkordfolgen für Strophe, Pre-Chorus, Refrain und
  Bridge und eigene Kadenzen in den Refrain und zum Schluss. Rock mit bVII und bVI–bVII–I, Dark Vocaloid in Moll mit
  bII und harmonischer Dominante, City Pop und Lo-Fi mit Septakkorden und ii7–V7–Imaj7, die Ballade mit dem Kanon,
  laufendem Bass und Vsus4–V vor dem Refrain, Idol-Pop mit der „Royal Road“ IV–V–iii–vi.
- **Melodie-Charakter je Stil** (Tab Song, `--ohne-melodie-charakter`): Kawaii und Idol-Pop singen kurz, abgesetzt
  und hüpfend, die Ballade gebunden in Schritten mit weiten Bögen, Rock gerufen mit Quarten, Quinten und Synkopen, City
  Pop und Lo-Fi zurückgelehnt nach dem Schlag, Lo-Fi eng und tief, Dark Vocaloid dicht und dramatisch. „Beste Melodie
  suchen“ bewertet nach dem Stil.
- **Arrangement je Stil** (Tab Band, `--ohne-stil-arrangement`): Rock abgedämpft vor dem Refrain und mit Gitarrensolo
  über Powerchords in der Bridge, die Ballade im Refrain ohne Gitarre und Synth, Dark Vocaloid mit Staccato-Streichern,
  Kawaii mit Glitzer-Glocken und Antwort-Melodie, City Pop mit Bläsern und Congas.
- **Klangbild je Stil** (Tab Mix, `--ohne-klangbild`): eigener Hall (Größe, Dämpfung, Vorverzögerung), eigenes Delay
  auf dem Gesang, eigene Klangfarbe des Masters, Stereobreite und Sättigung der Band. Die Ballade weit und weich, Lo-Fi
  klein, warm und dumpf, Rock trocken und nach vorn, Future Bass riesig und breit, City Pop glänzend.

**Charakter pro Song**

- **Charakter pro Song** (Tab Band, `--ohne-song-charakter`): jeder Song würfelt aus seinem Seed, was zum Stil passt:
  die Klänge von Klavier, Gitarre, Lead, Glocken, Bläsern und Gegenstimme, die Synth-Stimmen, die Grooves von Strophe
  und Refrain, die Spielweisen von Bass, Klavier und Gitarre, das Intro (volle Band, leise, Schlagzeug und Bass, nur
  die Hook) und den Schluss (klingt aus, harter Stopp, wird leiser). Im Protokoll steht „Charakter: …“.

**Stimme** (Tab Gesang)

- **Wohlfühlbereich der Stimme** (`--ohne-wohlfuehlbereich`): jede NEUTRINO-Stimme singt laut studio-neutrino.com in
  einem Tempobereich am schönsten (MERROW etwa 80 bis 140 BPM). Liegt der Song weit daneben, nennt das Protokoll
  installierte Stimmen, die dort schöner singen. Kennt die NEUTRINO-Ausgabe keinen StyleShift (vor 3.2.2), singt
  NEUTRINO den Song am Stück statt in Teilen, die dort nur Zeit und Schnitte kosteten.
- **Sanfte Nachbearbeitung** (`--ohne-sanfte-nachbearbeitung`): Vibrato, Übergänge und Verzierungen werden nur dort neu
  gerechnet, wo sich die Tonhöhe hörbar ändert; der Rest bleibt, wie NEUTRINO ihn gesungen hat. Kaum hörbare
  Formant-Verschiebungen (Idol ×1,04, Dark ×0,95) fallen weg, weil sie die Stimme nur aufrauen.
- **Weichere Gesangskette** (`--ohne-weiche-gesangskette`): der erste Kompressor greift mit höchstens 3:1 und 6 ms
  statt 6:1 in 1 ms zu und lässt Silbeneinsätze stehen; die Präsenz ist breiter und sitzt höher, der Glanz bei 12 kHz.

Für die Stimme bringt eine neue NEUTRINO-Ausgabe am meisten: seit 3.2.2 mit neuem Vocoder deutlich sauberer, und erst
dann klingen Strophe und Refrain verschieden. Hilfe › Einrichten zeigt, welche Ausgabe du hast.

## 1.3.1

Fehler behoben, die beim Durchsehen des ganzen Codes aufgefallen sind. Neue Funktionen gibt es keine, an deinen
Einstellungen ändert sich nichts.

- **Mehrere Fassungen: der Player spielte nicht die beste.** Mit automatischer Bewertung stand „Geladen ist die
  beste“, zu hören (und in Noten, Text und Export) war aber die zuletzt erzeugte: alle Fassungen schreiben
  nacheinander in denselben Ordner. Jetzt entsteht die beste am Ende dort noch einmal; ihr Gesang bleibt, nur Band und
  Mix werden neu gerechnet. Dasselbe beim Album über Nacht für den ersten Song des Albums.
- **„Beste Note zuerst“ sortierte nicht** (Tab Verlauf und `--verlauf --sortieren bewertung`): die Note stand beim
  Song, beim Sortieren wurde sie aber nie gefunden.
- **Wieder öffnen sang Songs mit Rap- oder Sprech-Teil neu**, obwohl ihr Gesang aufgehoben war.
- **Einstellungen sicherer gespeichert:** Stürzte die App genau beim Speichern ab, blieb eine halbe Datei, und beim
  nächsten Start stand alles auf Standard. Jetzt bleibt die alte Datei ganz, bis die neue fertig ist.
- **Alte MP3 in einem Player offen:** Hatte ein anderes Programm `final_song.mp3` offen, scheiterte der ganze Song kurz
  vor Schluss. Jetzt bleibt er als WAV, mit einem Hinweis im Protokoll.
- **Hilfe › Einrichten** zeigt jetzt auch bei Surge XT und den Gitarren-Verstärkern, wie viel Platz sie belegen, und
  kann sie entfernen.
- **Downloads:** „Bessere Klänge“ lädt nach einem Verbindungsabbruch noch einmal, statt die Datei aufzugeben. Eine beim
  Update nur halb geladene Setup.exe wird nicht mehr gestartet.
- **NEUTRINO:** Steht der Aufruf in der `Run.bat` in Anführungszeichen, singt NEUTRINO trotzdem (vorher sang dann
  VOICEVOX oder die Vorschau-Stimme).
- **`datenordner.txt`** klappt auch, wenn der Windows-Editor ein unsichtbares Zeichen an den Anfang schreibt, und mit
  einem Ordner ohne Laufwerk (er liegt dann im Programmordner).
- **Kommandozeile:** Ein Wert außerhalb des Bereichs, z. B. `--bpm 300`, gibt eine Meldung statt eines Absturzes.

## 1.3.0

Diese Version macht Gesang, Melodie und Band besser. Jede Neuerung hat einen Schalter (oder Regler) und eine Option
auf der Kommandozeile; ausgeschaltet klingt alles wie in 1.2.

**Gesang** (Tab Gesang)

- **Tonhöhe glätten** (Regler, `--ohne-tonhoehe-glaetten`): schiefe Töne werden sanft zur Note gezogen, Vibrato und
  Übergänge bleiben.
- **Härte zähmen** (`--ohne-haerte-zaehmen`): wie das Plugin soothe2 werden nur die Frequenzen leiser, die bei hohen,
  lauten Tönen gerade schrill herausstechen.
- **Verzierungen** (Regler, `--ohne-verzierungen`): dezent wie in J-Pop und Vocaloid: Shakuri (von unten in den Ton),
  Fall am Phrasenende und Kobushi (ein kleiner Schlenker in langen Tönen). Am deutlichsten in der Ballade, im Kawaii
  Chiptune gar nicht.
- **Gesang im Groove** (`--ohne-gesang-im-groove`): je Stil singt die Stimme ein paar Millisekunden hinter dem Schlag
  (Ballade, City Pop, Lo-Fi) oder davor (Rock, Drum and Bass).
- **Gruppe** (Auswahl Gruppe, `--gruppe 3` oder `4`): drei oder vier deiner NEUTRINO-Stimmen singen den Refrain
  zusammen, im Panorama verteilt; jede Strophe und die Bridge singt reihum eine von ihnen allein.
- **Partikel erkennen** (Tab Text, `--ohne-partikel`): は, へ und を werden auch in reinen Kana richtig gesungen,
  Zahlwörter wie 一回 als „いっかい“; eigene Lesungen in `Lesungen.txt` im Datenordner („Wort=Lesung“).
- **Sektion „Sprechen“** (`[Sprechen]` im Text): eine Zeile wird frei gesprochen, nicht im Takt, mit Hall, wie am
  Telefon oder trocken (Auswahl „Sprechen klingt“, `--sprechen-klang`). Braucht VOICEVOX.
- **DiffSinger-Ausdruck** (`--ohne-diffsinger-ausdruck`): hauchiger in der Strophe, mehr Spannung im Refrain und auf
  hohen Tönen, lange Töne werden zum Ende hin hauchiger.

**Melodie** (Tab Song)

- **Beste Melodie suchen** (`--ohne-beste-melodie`): jede Sektion wird 30-mal geschrieben, es singt die Fassung mit
  den meisten Punkten (klarer Höhepunkt, Schritte und Sprünge gemischt, wiederkehrende Motive).
- **Auftakte und Synkopen** (`--ohne-auftakte`): Phrasen beginnen vor dem Takt, betonte Töne kommen eine Achtel früher.
- **Spannungstöne** (`--ohne-spannungstoene`): Vorhalte, die sich auflösen, und lange Refrain-Töne auf None und Sexte.
- **Höhepunkt im letzten Refrain** (`--ohne-hoehepunkt`): der letzte Refrain endet auf dem höchsten Ton des Songs.
- **Triolen** (`--ohne-triolen`): Achteltriolen und punktierte Achtel, als echte Triolen für NEUTRINO.
- **Akkord-Würze** (Regler, `--ohne-akkord-wuerze`): Zwischendominanten, Leihakkorde, verminderte Durchgänge, sus4 und
  die Marusa-Folge im Refrain.
- **KI-Melodie (Versuch, ab Werk aus)** (Tab Pfade, `--ki-melodie`): das Modell der KI-Begleitung schlägt vier
  Refrain-Melodien vor; singt eine besser als die komponierte, singen alle Refrains sie. Braucht die eingerichtete
  KI-Begleitung.

**Band** (Tab Band)

- **Eigenes Intro-Riff** (Tab Song, `--ohne-intro-riff`): Intro, Zwischenspiel nach dem ersten Refrain und Outro
  bekommen ein eigenes Riff statt der Refrain-Melodie.
- **Kime, Stopps und Fills** (`--ohne-kime`): die ganze Band spielt dieselben Akzente, setzt kurz aus und spielt am
  Ende der Phrasen kleine Läufe.
- **Band im Groove** (`--ohne-band-groove`): Bass, Gitarre und Klavier spielen im Timing des Schlagzeugers.
- **Bass-Läufe** (`--ohne-bass-laeufe`): Läufe zum nächsten Akkord, Fills, Oktaven im Refrain, im City Pop Funk mit
  abgedämpften Tönen.
- **Läufe** (`--ohne-laeufe`): Klavierläufe, ein Glissando vor dem Refrain, Streicher, die in den Refrain laufen, die
  Hook vom Klavier in Oktaven.
- **Anison-Grooves** (`--ohne-anison-grooves`): in schnellen Songs 2-Beat im Refrain, Disco-Hi-Hats, Tom-Groove,
  Snare-Wirbel und Becken-Stopps.
- **Aufbau in der Sektion** (`--ohne-aufbau`): die erste Strophe beginnt nur mit Klavier oder Gitarre, jeder Refrain
  bekommt in der zweiten Hälfte eine Schicht mehr.
- **Surge-Klänge** (Einrichten › Surge XT, etwa 50 MB; `--ohne-surge-klaenge`): Supersaw, Pluck, Chip-Lead,
  Future-Bass-Akkorde und Reese-Bass spielen Werks-Klänge des kostenlosen Synthesizers Surge XT.
- **Verstärker** (Einrichten › Gitarren-Verstärker, etwa 1 MB; `--ohne-verstaerker-modelle`): verzerrte E-Gitarren
  spielen über Modelle echter Verstärker (Neural Amp Modeler): Marshall JCM2000 für Overdrive, Peavey 6505+ für
  Distortion. Das Rendern dauert damit etwas länger.

**Mix** (Tab Mix)

- **Druck** (`--ohne-druck`): Parallelkompression auf dem Schlagzeug, ein Bus-Kompressor, der die Band zusammenhält,
  und ein Mehrband-Kompressor im Master.

**Behoben**

- Ein unter „Klänge aus dem VST-Instrument“ gespeicherter Klang verlor die Töne ganz am Anfang der Spur.

## 1.2.2

Fehler aus dem Test von 1.2.1 behoben.

- **Automatische Bewertung lief immer noch nicht** („[Errno 22] Invalid argument“ bei `config.json`): Das Modell lag
  als Verknüpfungen im Ordner, und manche Windows-PCs öffnen solche Verknüpfungen nicht (wie damals bei uv). Jetzt
  liegen echte Dateien dort; was schon geladen war, wird beim nächsten Bewerten umgestellt, ohne es neu zu laden.
  Dasselbe gilt für die KI-Begleitung und den Klang-Veredler.

## 1.2.1

Fehler aus dem ersten Test von 1.2.0 behoben.

- **Automatische Bewertung lief nicht** („No module named 'requests'“): Audiobox braucht das Paket requests, bringt
  es aber nicht mit. Die Setup.exe lädt es jetzt in eine schon eingerichtete Bewertung nach, du musst nichts tun.
  Fehlt der Bewertung einmal ein Paket, sagt System prüfen welches, und Hilfe › Einrichten bietet sie wieder an
  (lädt nur das Fehlende).
- **System prüfen lief doppelt:** „Prüfen“ in einem zweiten Fenster „System prüfen“ startete eine zweite Prüfung
  daneben. Beide sangen den Probesong in denselben Ordner und löschten sich gegenseitig die Gesangsdateien, daher die
  Fehler bei Chor, Flächen und „Ganzer Song“. Jetzt läuft immer nur eine; jedes Fenster zeigt sie an.
- Das eigene Fenster hat wieder sein Symbol, und die SyntaxWarnings von pydub im schwarzen Fenster sind weg.

## 1.2.0

Diese Version bringt neue Arten von Songs, mehr Ausgaben und mehr Hilfe beim Schreiben. Jede Neuerung hat einen
Schalter und eine Option auf der Kommandozeile; ausgeschaltet klingt alles wie in 1.1.

**Neue Songs**

- **3/4- und 6/8-Takt** (Tab Song › Takt, `--takt`): Walzer mit Bum-Tschak-Tschak oder wiegender 6/8-Takt. Im
  6/8-Takt zählt das Tempo die punktierten Viertel.
- **Rap-Teil** (Sektion „Rap“, `[Rap]` im Text): ein dichter Rhythmus fast auf einem Ton, gesprochen von einer
  VOICEVOX-Sprechstimme (Tab Gesang › Rap-Teil). Ohne VOICEVOX singt die Gesangsstimme ihn.
- **Eigener Text für Wiederholungen:** `[Verse 2]` oder `[Chorus 3]` geben diesem Vorkommen seinen eigenen Text auf
  dieselbe Melodie.
- **Idol-Rufe:** „はい！はい！“ (bei Rock „おい！“) in den Pausen der Hauptstimme und „ふっふー“ vor dem Refrain,
  von mehreren Stimmen gerufen.
- **Vocal Chops:** Schnipsel der Hauptstimme spielen im Drop einen Riff (Future Bass auch im Intro).
- **Ritardando:** Eine Ballade mit Outro wird zum Schluss langsamer, der letzte Akkord klingt aus.
- **Remix** (Knopf am fertigen Song, `--remix STIL`): derselbe Song mit Band, Tempo und Klang eines anderen Stils.
- **Song-Rezepte** (Tab Song, `--rezept`): neun fertige Ausgangspunkte mit eigenem Beispieltext, z. B. „Hologram
  Star (wie Idol)“ mit Rap-Teil und Rufen oder „Walzer im Mondlicht (3/4)“.

**Besserer Klang**

- **Flügel, E-Bass und E-Gitarre aus echten Aufnahmen** (Einrichten › „Flügel, Bass und Gitarre aus Aufnahmen“,
  etwa 550 MB).
- **Echte Grooves** spielen auch beim leichten Grund-Swing (bis 0,2).
- **Off-Vocal und A-cappella** als eigene MP3, so laut wie im Song.
- **True Peak:** Der Limiter hält auch die Spitzen zwischen den Samples unter -1 dBTP.

**Ausgaben**

- **MP3-Tags:** Titel, Stimme, Stil, Tempo, Tonart, Liedtext und ein Titelbild in jeder MP3.
- **Lyric-Video in 1080p** im Farbverlauf des Stils, Text und Wellenform in seinen Farben; oder ein eigenes
  Hintergrundbild (Tab Pfade, `--video-hintergrund`).
- **Projekte:** Der Gesang jedes Songs bleibt im Verlauf liegen. „Wieder öffnen“ baut Band und Mix neu, ohne dass
  NEUTRINO noch einmal singt.

**Bedienung**

- **Text-Helfer** im Tab Text: pro Zeile die Silben gegen den Platz in ihrer Phrase (rot = zu viele), der Endvokal
  als Reimbuchstabe und wie Kanji gelesen werden.
- **Restzeit** aus früheren Läufen derselben Art und eine **Windows-Meldung**, wenn ein längerer Lauf fertig ist.
- **Tastenkürzel:** Leertaste spielt, Strg+Enter erzeugt, Strg+Z nimmt die letzte Änderung an den Noten zurück.
- **Speicherplatz** im Einrichten-Assistenten: wie viel jeder Baustein, die Songs und die Projekte belegen, mit
  „Entfernen“, „Projekte löschen (Songs bleiben)“ und „Aufräumen“.

**Unter der Haube**

- Ein Test prüft für jeden Schalter, dass er wirklich etwas ändert. Gefunden: Hauchigkeit und Schimmer der
  Vorschau-Stimme sangen nicht neu.
- pipeline.py ist in Gesang, Spuren und Mix aufgeteilt.

## 1.1.0

Diese Version macht den Gesang besser. Jede Neuerung hat einen Schalter im Tab Gesang (oder bei den Vorbildern) und
auf der Kommandozeile.

**Noten, die NEUTRINO gut singen kann**

- Lange Vokale und Melismen schreibt die App als Haltezeichen ー statt als neue Silbe (タワー statt たわあ).
- **Atemzeichen:** Nach spätestens zwei Takten Gesang wird in einer kurzen Pause geatmet; eine Zeile ganz ohne Pause
  bekommt nach vier Takten ein Atemzeichen. NEUTRINO trennt dort die Phrasen.
- **Schnelle Stellen:** Zwei sehr kurze Töne mit Doppelvokal (か + い) singt NEUTRINO auf einem Ton.
- **Englisch als Katakana:** love → ラブ, I love you → アイ ラブ ユー (eigene Liste, dann alkana, dann e2k).
- **Singbare Melodie:** keine Sprünge über eine Quinte auf kurzen Silben, kein Spitzenton nur eine Sechzehntel lang,
  spätestens nach 8 Sekunden eine Atempause. Eingebaute Melodien ändert das selten, eigene Motive öfter.
- **Gesang swingt mit:** Swingt die Band (Lo-Fi oder Swing ab 0,2), setzen die Töne auf der zweiten Sechzehntel
  genauso später ein.

**NEUTRINO**

- **StyleShift pro Sektion:** Strophen tiefer und ruhiger, Refrains heller und kräftiger. NEUTRINO singt dafür
  zweimal, geschnitten wird in den Pausen. Die Ausgabe mit Tuning-Tool (.ex) kennt keinen StyleShift; dann singt
  NEUTRINO alles gleich, mit einem Hinweis im Protokoll.
- **Fassungen ohne Farbsprung:** Alle Fassungen haben denselben StyleShift und werden nur nach groben Fehlern
  gewertet, damit die Farbe nicht von Phrase zu Phrase springt.
- **Stimmen-Casting** (Knopf über den Noten): Jede installierte Stimme singt den Refrain, du hörst sie nebeneinander
  und merkst dir eine Lieblingsstimme je Stil.
- **Support-Stimme (Versuch):** Eine zweite NEUTRINO-Stimme gibt der Hauptstimme eine andere Nuance, z. B. MERROW
  mit SOMA. Braucht eine NEUTRINO-Ausgabe mit `Run_support_model.bat`, ab Werk aus.
- **Gesangs-Check** unter dem Player: „Gesungen von NEUTRINO 3.2.2, MERROW, Grafikkarte“, oder eine rote Warnung,
  wenn die Vorschau-Stimme gesungen hat. Einrichten rät bei NEUTRINO älter als 3.2.2 zum Update.
- **Vibrato und Übergänge mit Praat-PSOLA** statt WORLD: Die Stimme behält ihren Klang, statt rau zu werden.

**Begleitstimmen**

- Die zweite Stimme wechselt von Refrain zu Refrain: nur auf Phrasenenden, Terz darunter, darüber und Oktave.
- Jede Harmonie ist gedoppelt, links und rechts.
- **Gesungene Flächen** („Uuh“, „Aah“) im Refrain statt des Keyboard-Chors.
- **Ad-libs** im letzten Refrain: kurze Rufe und Echo-Antworten in den Lücken.

**Klang und Mix**

- **Die Band macht dem Gesang Platz:** Wie das Plugin Trackspacer senkt die App in der Band genau die Frequenzen ab,
  in denen gerade gesungen wird (bis 3 dB).
- **Der Gesang reitet auf der Band:** Er steht immer gleich weit über der Band (bis 4 dB).
- **Gesangsklang wie im Vorbild:** die Klangkurve des Vorbild-Gesangs in Terzbändern, höchstens 4 dB (braucht Demucs).
- **Platte aus Impulsantwort** statt des einfachen Halls; eigene Räume als WAV im Ordner `Hall`. Das Delay wird
  leiser, solange gesungen wird.
- **Lautstärke pro Silbe:** Betonte Silben etwas lauter, weicher Einsatz am Phrasenanfang.
- **Echte Atmer:** Liegen Atem-Aufnahmen im Ordner `Atmer`, nimmt die App sie statt des Rauschens.
- **Kette pro Stimme und Stil:** eigene Klangeinstellungen für helle und tiefe Stimmen, Ballade weicher, Rock mit mehr
  Sättigung.
- **Airwindows-Effekte** (Einrichten, etwa 15 MB): Bandsättigung ToTape9 auf dem Gesang und ein analoges Mischpult
  (Console7) über alle Spuren.
- **Stil-Effekte:** Telefon in der ersten Zeile, Stottern vor dem Refrain, harter Tune im Refrain, verschobene
  Formanten. Jeder Stil nimmt, was zu ihm passt.

**Selbst Hand anlegen**

- **Eigene Gesangsspur:** Eine WAV, die du woanders gesungen oder bearbeitet hast, ersetzt die Hauptstimme und wird an
  den Noten ausgerichtet. Die Begleitstimmen singt weiter die Engine.
- **Noten für Tuning-Tools** (Knopf über den Noten): MusicXML, UST und MIDI mit einer kurzen Anleitung als ZIP.
- **Eine Phrase neu singen:** Doppelklick auf einen Ton in der Piano-Roll, dann mit anderem StyleShift oder anderer
  Stimme. NEUTRINO singt nur diese Phrase, der Rest bleibt.

**Weitere Engines**

- **VOICEVOX singt laut und leise selbst:** Lautstärke pro Silbe und Ausdruck pro Phrase gehen direkt in den Gesang.
- **DiffSinger (Versuch):** singt mit Stimmen für OpenUtau (Ordner mit `dsconfig.yaml`). Die App findet sie in
  OpenUtau oder im Ordner `DiffSinger`. Läuft auf dem Prozessor, etwa doppelt so lang wie der Song. Jede Stimme hat
  ihre eigene Lizenz.

## 1.0.2

- Beim Installieren zeigt ein schwarzes Fenster, welche Bibliotheken gerade laden. Geht etwas schief, bleibt es mit
  der Meldung offen. Vorher stand die Setup.exe ohne Hinweis bei „Lade die Bibliotheken“.
- uv lädt ein Paket nach dem anderen. Mehrere große gleichzeitig blieben auf manchen PCs mitten im Download stehen
  (scipy und llvmlite bei 1,19 MB). Das gilt auch für Einrichten, z. B. für PyTorch.

## 1.0.1

- Die Setup.exe bringt ihr eigenes Python mit. Vorher brach der Start auf manchen PCs ab mit „Failed to inspect Python
  interpreter … os error 448“, weil Windows die Python-Verknüpfungen von uv in AppData gesperrt hat.
- Die Setup.exe lädt beim Installieren kein Python mehr herunter, nur noch die Bibliotheken.

## 1.0.0

**Installieren und Einrichten**

- **Setup.exe** ohne Adminrechte, mit Eintrag im Startmenü. Updates findet die App selbst („Update da“ oben) und
  installiert sie mit einem Klick; deine Daten bleiben.
- Einstellungen, Songs, Vorlagen, Vorbilder und Motive liegen jetzt in **Dokumente\Vloid Songs**. Beim ersten Start
  zieht die App alles aus dem Programmordner dorthin um.
- **Einrichten** lädt Klänge und Modelle aus der App heraus, mit Platzbedarf, Fortschritt und Abbrechen. Die
  einzelnen setup_….py-Skripte braucht es dafür nicht mehr.
- **Hilfe-Menü** (Fragezeichen oben rechts): Erste Schritte, Fehlerbehebung, Einrichten, System prüfen,
  Fehlerbericht speichern, Updates, Was ist neu, Credits.
- **System prüfen** probiert jeden Baustein kurz echt aus und zeigt, was läuft und was fehlt.

**Stabil**

- **Abbrechen** beendet einen Song sofort, auch mitten in NEUTRINO oder ACE-Step.
- Stürzt die App mitten in einem Song ab, bietet sie beim nächsten Start an, **weiterzumachen**.
- Hat sich am Gesang nichts geändert, singt NEUTRINO nicht neu (z. B. wenn du nur den Mix änderst).
- Ein **Protokoll** liegt unter Protokolle\vloid_songs.log; **Fehlerbericht speichern** packt es mit Einstellungen und
  Systeminfo in ein ZIP.

**Gesang**

- **Comping:** Bei mehreren Fassungen kommt jede Phrase aus der saubersten.
- **Studio-Kette:** leichte Bandsättigung, Hall und Delay je Sektion und eine echte Doppelung im Refrain.
- **Ausdruck pro Phrase:** Jede Zeile wird zu ihrem höchsten Ton hin lauter und heller.
- **Romaji:** `kimi no koe` wird japanisch gesungen, auch gemischt mit Kana und Kanji.

**Band**

- **Echtes Schlagzeug** aus dem DRS Kit, im Studio aufgenommen, mit mehreren Anschlag-Schichten.
- **Grooves und Fills echter Schlagzeuger** aus dem Groove MIDI Dataset.
- Der Bass spielt Ghost-Notes und Slides, die Gitarre schlägt je nach Teil anders an.
- **Mix pro Instrument wie die Vorbilder:** Demucs zerlegt deine Vorbild-Songs in Gesang, Schlagzeug, Bass und Rest,
  und der Mix bringt diese Gruppen deines Songs auf dieselben Abstände und dieselbe Helligkeit.
- **KI-Begleitung (Versuch):** Der Anticipatory Music Transformer schreibt Klavier, Gitarre, Streicher, Synths und
  Bläser zu Melodie, Bass und Schlagzeug. Ab Werk aus, einschalten unter Pfade.

**Alltag**

- **Entwurf:** ein Song in etwa einer Minute ohne NEUTRINO; „Richtig machen“ macht ihn dann mit Gesang.
- **Song-Bibliothek:** Suche, Favoriten, Sortieren nach Note oder Name, eigene Namen und Notizen. Favoriten und Songs
  mit Namen bleiben immer.
- **Album über Nacht:** bis zu 30 Songs am Stück, morgens nach Note sortiert, mit Wiedergabeliste.
- **Fertig für YouTube:** MP3, Video, Titelbild und Beschreibung in einem eigenen Ordner.
- Das Mischen ist schneller.

Jede neue Funktion hat einen Schalter; welcher wo steht, zeigt Hilfe › Erste Schritte.
