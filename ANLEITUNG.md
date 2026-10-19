# Erste Schritte

In fünf Schritten zum ersten Song. Alles Weitere steht darunter; wenn etwas nicht klappt, hilft
**Hilfe › Fehlerbehebung**.

## 1. Installieren

`VloidSongs-Setup-1.2.0.exe` starten. Sie braucht keine Adminrechte, legt „Vloid Songs“ ins Startmenü (auf Wunsch
auch auf den Desktop) und lädt beim ersten Mal alle Bibliotheken; das dauert ein paar Minuten. Danach
startet die App über das Startmenü.

Deine Songs, Einstellungen, Vorlagen und Vorbilder liegen in **Dokumente\Vloid Songs**. Ein Update fasst sie nie an.

## 2. Einrichten

Beim ersten Start öffnet sich **Einrichten** (später: Fragezeichen oben rechts › Einrichten).

- **NEUTRINO** darf die App nicht selbst laden. Lade es von studio-neutrino.com, entpack es und wähl den Ordner, in
  dem `bin` und `model` liegen. Weitere Stimmen kommen als Ordner nach `model`.
- **Klänge und Modelle**: Die empfohlenen sind schon angehakt. „Ausgewählte einrichten“ lädt sie, mit Fortschritt
  und Abbrechen; ein abgebrochener Download macht beim nächsten Mal dort weiter.
- Hattest du Vloid Songs schon als entpackten Ordner, holt **Übernehmen** Songs, Einstellungen und geladene Klänge
  von dort, damit nichts doppelt geladen wird.

## 3. System prüfen

Fragezeichen › **System prüfen** › „Prüfen“. Jeder Baustein macht etwas Kleines echt: ✓ läuft, – ist nicht
eingerichtet, ✗ hat ein Problem (Fehlerbehebung). Zum Schluss entsteht ein kurzer Song mit deinen Einstellungen.
„Gründlich“ probiert auch den Klang-Veredler und die KI-Begleitung aus; das dauert länger.

## 4. Der erste Song

- Tab **Song**: Stil, Tempo und Tonart wählen, oder unter „Song-Rezepte“ ein fertiges Rezept mit Beispieltext
  laden.
- Tab **Text**: den Liedtext eintragen, pro Abschnitt eine Überschrift wie `[Verse]` oder `[Chorus]`. Japanisch mit
  Kanji und Kana geht, Romaji auch (`kimi no koe`), sogar gemischt. Rechts zeigt der Text-Helfer pro Zeile, ob die
  Silben in die Melodie passen.
- Oben **Entwurf**: in etwa einer Minute ein schneller Song ohne NEUTRINO, die Melodie spielt ein Synth. Gut zum
  Ausprobieren von Stil, Tempo und Akkorden.
- Gefällt der Entwurf: **Richtig machen** macht genau diesen Song mit Gesang. Oder gleich **Song erzeugen**.

## 5. Anhören und weitermachen

- Der **Player** spielt den Song mit Wellenform, darunter läuft der Text mit. Unter „Anhören“ hörst du jede Spur
  einzeln.
- **Neu würfeln** macht nur einen Teil neu (Melodie, Akkorde, Schlagzeug, ein Instrument), auf Wunsch nur in einer
  Sektion. **Seed festhalten** behält den Song, während du Mix, Gesang oder Text änderst.
- Der Tab **Verlauf** ist deine Song-Bibliothek, siehe unten.
- **Fertig für YouTube** legt MP3, Video, Titelbild und Beschreibung in einen eigenen Ordner.

---

# Was die App sonst kann

**Entwurf und Richtig machen.** Ein Entwurf überspringt alles, was lange dauert: kein NEUTRINO, keine
Vorbild-Analyse, keine MP3, kein Eintrag im Verlauf. Er landet in `Songs\Entwurf`. „Richtig machen“ nimmt denselben
Seed und macht den ganzen Song.

**Song-Bibliothek (Tab Verlauf).** Jeder Song mit Note, Name und Notiz. Oben suchen (Name, Notiz, Stil, Seed,
Album, Tonart, Tempo, Datum), mit ★ nur Favoriten zeigen, sortieren nach neu, Note oder Name. Der Stift gibt einem Song einen Namen und eine
Notiz. Favoriten, Songs mit Namen und Album-Songs bleiben immer; von den anderen behält der Verlauf die neuesten 30
(einstellbar unter Pfade › App). ↺ holt Einstellungen und Seed eines Songs zurück.

**Album über Nacht.** Oben „Album“: wie viele Songs (bis 30), welche Stile (reihum), ein Name und auf Wunsch ein
Ordner mit Liedtexten (jede `.txt` ein Song). Jeder Song bekommt einen neuen Seed und, wenn der Schalter an ist, eine
eigene Tonart und ein leicht anderes Tempo. Morgens liegen die Songs nummeriert in `Songs\Alben\<Datum> <Name>`, mit
Wiedergabeliste und Titelliste; ist die Bewertung eingerichtet, steht der beste vorn. Ein Fehler kostet nur diesen
Song, Abbrechen behält die fertigen.

**Fertig für YouTube.** Unter dem Player. In `Songs\YouTube\<Datum> <Titel>` liegen danach die MP3, ein Video
(Lyric-Video in 1920×1080 vor dem Farbverlauf des Stils, ohne Text das Titelbild), `Titelbild.png` in 1280×720 und `Beschreibung.txt` mit Stil,
Tempo, Tonart und dem, was die Stimme verlangt (bei NEUTRINO den Namen der Stimme). Der Titel ist der Name aus dem
Verlauf, sonst Stil und Seed. Ohne ffmpeg gibt es Bild und Beschreibung trotzdem.

**Liedtext in Romaji.** Eine Zeile ganz in Romaji wird japanisch gesungen (`kimi no koe` → きみ の こえ). Ist ein
englisches Wort darin (`love`, `baby`), bleibt die Zeile, wie sie ist. Neben Kana und Kanji wird jedes Romaji-Wort
umgewandelt. Rechts im Tab Text siehst du sofort, welche Silben gesungen werden. Schalter: Tab Text.

**Gesang.** NEUTRINO singt mehrere Fassungen (Tab Gesang, „Fassungen“), und die App setzt jede Phrase aus der
saubersten zusammen (Comping). Die Studio-Kette gibt der Stimme leichte Bandsättigung, Hall und Delay je Sektion
(Strophe trockener, Refrain weiter) und im Refrain eine echte Doppelung aus der zweiten Fassung. Mit „Ausdruck pro
Phrase“ wird jede Zeile zu ihrem höchsten Ton hin lauter und heller, Strophen bleiben leiser als Refrains.

**Gesang ab 1.1.** Die App schreibt die Noten so, wie NEUTRINO sie gut singen kann: ー für lange Vokale, Atemzeichen
in langen Zeilen, schnelle Stellen auf einem Ton und englische Wörter als Katakana (love → ラブ). Strophen singt
NEUTRINO ruhiger, Refrains heller und kräftiger (StyleShift pro Sektion). Die zweite Stimme wechselt von Refrain zu
Refrain und ist gedoppelt, dazu kommen gesungene Flächen und Ad-libs im letzten Refrain. Im Mix macht die Band dem
Gesang Platz, statt dass er nur lauter wird. Unter dem Player steht, wer gesungen hat (Gesangs-Check).

**Stimmen-Casting.** Der Knopf über den Noten lässt jede installierte Stimme den Refrain singen. Mit dem Herz merkst
du dir eine Lieblingsstimme für den Stil; mit „Lieblingsstimme je Stil“ wählt die App sie beim Wechsel des Stils.

**Selbst nachbessern.** Doppelklick auf einen Ton in den Noten singt nur seine Phrase neu, mit anderem StyleShift oder
anderer Stimme. „Noten für Tuning-Tools“ über den Noten packt MusicXML, UST und MIDI in ein ZIP, z. B. für das
NEUTRINO-Tuning-Tool oder OpenUtau. Was du dort gesungen oder bearbeitet hast, setzt du im Tab Gesang unter „Eigene
Gesangsspur“ als WAV wieder ein; die App richtet sie an den Noten aus und mischt sie wie ihren eigenen Gesang.

**DiffSinger (Versuch).** Eine dritte Engine für DiffSinger-Stimmen aus OpenUtau. Die App findet sie in OpenUtau oder
in `Dokumente\Vloid Songs\DiffSinger`; im Tab Gesang „Gesang mit“ DiffSinger wählen. Sie singt auf dem Prozessor,
etwa doppelt so lang wie der Song. Jede Stimme hat eigene Lizenzbedingungen, sie stehen in ihrem Ordner.

**Eigene Atmer und Räume.** Legst du Atem-Aufnahmen (WAV, FLAC, z. B. CC0 von Freesound) in
`Dokumente\Vloid Songs\Atmer`, nimmt die App sie statt des Rauschens. Eine Impulsantwort als WAV in
`Dokumente\Vloid Songs\Hall` wird der Raum für den Gesang.

**Echtes Schlagzeug und Grooves.** Mit dem DRS Kit spielen akustische Stile ein im Studio aufgenommenes Schlagzeug;
mit den Grooves spielen Pop, Rock, Ballade, City Pop und Idol-Pop Phrasen und Fills echter Schlagzeuger. Der Bass
hat Ghost-Notes und Slides, die Gitarre schlägt je nach Teil anders an.

**Vorbild-Songs.** Im Tab Song einen oder mehrere Lieblingssongs angeben. Sie bestimmen, was du einschaltest:
Mastering, Lautstärke-Verlauf, Gesangslautstärke, Vorschläge für Tempo, Tonart und Stil. Mit Demucs (Einrichten,
„Mix wie die Vorbilder“) kommt **Mix pro Instrument** dazu: Demucs zerlegt jedes Vorbild einmal in Gesang,
Schlagzeug, Bass und Rest, und der Mix bringt diese vier Gruppen deines Songs auf denselben Abstand und dieselbe
Helligkeit, höchstens ein paar dB. Aus den Vorbildern landet nichts im Song, sie werden nur gemessen.

**KI-Begleitung (Versuch).** Nach dem Einrichten unter Pfade einschalten. Der Anticipatory Music Transformer hört
Melodie, Bass und Schlagzeug und schreibt dazu Klavier, Gitarre, Streicher, Synths und Bläser; diese ersetzen die
komponierte Begleitung. Ob das besser klingt, ist offen: Mach denselben Song (Seed festhalten) einmal mit und einmal
ohne und vergleich im Verlauf mit A und B. Mit NVIDIA-Grafikkarte geht es deutlich schneller als ohne.

**Klang-Veredler (Versuch).** ACE-Step spielt die Band neu ein und legt eine zweite Fassung neben den Song
(„Veredelt“ im Player). Braucht eine NVIDIA-Grafikkarte.

**Abbrechen und Weitermachen.** „Abbrechen“ beendet einen Song sofort, auch mitten in NEUTRINO. Stürzt die App ab,
bietet sie beim nächsten Start an, den Song fertig zu machen; fertiger Gesang wird übernommen. Hat sich am Gesang
nichts geändert (z. B. nur der Mix), singt NEUTRINO nicht noch einmal.

**Updates.** Einmal am Tag sieht die App nach, ob es eine neue Version gibt; dann steht oben „Update da“. „Update
holen“ lädt die neue Setup.exe und startet sie, deine Daten bleiben. Danach zeigt „Was ist neu“, was sich geändert hat.

## Neu in 1.3

1.3 macht Gesang, Melodie und Band besser. Alles ist ab Werk an (außer der KI-Melodie) und hat einen eigenen
Schalter; ausgeschaltet klingt es wie in 1.2.

**Gesang** (Tab Gesang). „Tonhöhe glätten“ zieht schiefe Töne sanft zur Note, „Härte zähmen“ nimmt schrille Stellen
auf hohen, lauten Tönen heraus, „Verzierungen“ singt dezent Shakuri (von unten in den Ton), Fall am Phrasenende und
Kobushi. „Gesang im Groove“ legt die Stimme je Stil etwas hinter den Schlag (Ballade, City Pop, Lo-Fi) oder davor
(Rock, Drum and Bass). Mit DiffSinger singt die Stimme in der Strophe hauchiger und im Refrain mit mehr Spannung.

**Gruppe.** Tab Gesang › Gruppe: drei oder vier deiner NEUTRINO-Stimmen singen den Refrain zusammen, links, Mitte und
rechts verteilt; jede Strophe und die Bridge singt reihum eine von ihnen allein. Dafür müssen so viele Stimmen in
NEUTRINO installiert sein.

**Sprechen.** Im Ablauf die Sektion „Sprechen“ anhängen und im Text `[Sprechen]` über die Zeile schreiben. VOICEVOX
spricht sie frei, wie man einen Satz sagt, mit Hall, wie am Telefon oder trocken (Tab Gesang › Sprechen klingt); die
Band spielt darunter leise, das Schlagzeug schweigt. Ohne VOICEVOX fällt die Zeile weg.

**Richtig lesen.** Tab Text › Partikel erkennen: は, へ und を werden auch in reinen Kana richtig gesungen (きみは →
きみわ), Zahlwörter wie 一回 als „いっかい“. Eigene Lesungen schreibst du in `Lesungen.txt` im Datenordner, eine pro
Zeile als `Wort=Lesung`.

**Melodie** (Tab Song). Jede Sektion wird 30-mal geschrieben, und die eingängigste singt („Beste Melodie suchen“).
Phrasen beginnen auch vor dem Takt, lange Töne dürfen Spannungstöne sein, der letzte Refrain endet auf dem höchsten
Ton des Songs, und es gibt Triolen. „Akkord-Würze“ (Regler) bringt Zwischendominanten, Leihakkorde und die
Marusa-Folge in die Akkorde. „Eigenes Intro-Riff“ gibt Intro, Zwischenspiel und Outro ein eigenes Riff.

**KI-Melodie (Versuch).** Tab Pfade, unter der KI-Begleitung: das Modell schlägt vier Refrain-Melodien vor; singt eine
besser als die komponierte (nach denselben Punkten wie „Beste Melodie suchen“), singen alle Refrains sie. Ab Werk aus,
braucht die eingerichtete KI-Begleitung.

**Band** (Tab Band). Die Band spielt gemeinsame Akzente und Stopps (Kime), kleine Fills am Phrasenende und im Timing
des Schlagzeugers. Der Bass läuft zum nächsten Akkord und spielt im City Pop Funk, das Klavier spielt Läufe und vor dem
Refrain ein Glissando, schnelle Songs bekommen 2-Beat und Snare-Wirbel, und die erste Strophe beginnt klein.

**Surge-Klänge.** Hilfe › Einrichten › Surge XT (etwa 50 MB) lädt den kostenlosen Synthesizer Surge XT und fünf seiner
Klänge. Dann spielen Supersaw, Pluck, Chip-Lead, Future-Bass-Akkorde und Reese-Bass daraus statt aus den eigenen
Synths, gleich laut (Schalter Tab Band › Surge-Klänge).

**Verstärker.** Hilfe › Einrichten › Gitarren-Verstärker (etwa 1 MB) lädt zwei Modelle echter Verstärker für den
Neural Amp Modeler: einen Marshall JCM2000 für Overdrive- und einen Peavey 6505+ für Distortion-Gitarren. Verzerrte
Gitarren klingen damit wie über einen echten Verstärker; das Rendern dauert dann etwas länger (Schalter Tab Band ›
Verstärker, nur mit „Verzerrte E-Gitarren über Verstärker und Box“).

**Druck im Mix** (Tab Mix › Druck): Parallelkompression auf dem Schlagzeug, ein Bus-Kompressor für die Band und ein
Mehrband-Kompressor im Master.

## Neu in 1.2

**3/4- und 6/8-Takt.** Tab Song › Takt. Im 3/4-Takt spielt die Band Bum-Tschak-Tschak wie ein Walzer, im 6/8-Takt
wiegt der Song in Dreiergruppen. Im 6/8-Takt zählt das Tempo die punktierten Viertel: Eine Ballade hat dann etwa 50
bis 70.

**Rap-Teil.** Im Ablauf die Sektion „Rap“ anhängen und im Text `[Rap]` schreiben. Die Melodie ist dort ein dichter
Rhythmus fast auf einem Ton, und eine VOICEVOX-Sprechstimme spricht ihn genau im Takt (Tab Gesang › Rap-Teil, dort
auch die Stimme). Ohne VOICEVOX oder mit dem Schalter aus singt die Gesangsstimme den Rap.

**Eigener Text für Wiederholungen.** `[Verse 2]` oder `[Chorus 3]` gibt diesem Vorkommen seinen eigenen Text auf
dieselbe Melodie; der Rhythmus passt sich den Silben an.

**Text-Helfer.** Rechts im Tab Text steht unter jeder Zeile, wie viele Silben sie hat und wie viele bequem in ihre
Phrase passen. Rot heißt: zu viele, die Zeile wird gequetscht; orange: schnell gesungen. Der Buchstabe vor der Zeile
ist ihr Endvokal (gleicher Buchstabe = Reim), und Kanji ohne Lesung werden rot markiert. Über jedem Abschnitt steht,
wie viele Takte und Phrasen er hat und ob der Text wiederholt wird oder die Sektion länger macht.

**Song-Rezepte.** Tab Song › Song-Rezepte: neun fertige Ausgangspunkte mit eigenem Beispieltext, z. B. „Hologram Star
(wie Idol)“ (schnell, Rap-Teil, Idol-Rufe), „Letzter Sommerregen (Ballade)“ oder „Walzer im Mondlicht (3/4)“. Ein
Rezept ersetzt Stil, Tempo, Tonart, Takt, Ablauf und Text; Stimme, Pfade und Mix bleiben.

**Idol-Rufe und Vocal Chops.** Im Idol-Pop und Kawaii ruft das Publikum „はい！はい！“ in die Pausen des Refrains (bei
Rock „おい！“) und „ふっふー“ davor. Im Drop spielen Schnipsel der Hauptstimme einen Riff (Future Bass auch im Intro).

**Ritardando.** Eine Ballade mit Outro wird in den letzten Takten langsamer, der Schlussakkord klingt aus.

**Remix.** Der Knopf „Remix“ unter dem Player macht denselben Song (Melodie, Text, Akkorde, Stimme) mit Band, Tempo
und Klang eines anderen Stils. Den ursprünglichen Stil wählen bringt den Song zurück.

**Wieder öffnen.** Der Gesang jedes Songs bleibt im Verlauf liegen (etwa 20 bis 60 MB pro Song). „Wieder öffnen“ im
Verlauf legt ihn zurück: Band und Mix entstehen neu, NEUTRINO singt nicht noch einmal, und du kannst weiter Töne
ändern oder neu würfeln.

**Mehr in jeder MP3.** Neben dem Song liegen `final_song_offvocal.mp3` (ohne Gesang, zum Selbersingen) und
`final_song_acappella.mp3` (nur Gesang), beide so laut wie im Song. Jede MP3 trägt Titel, Stimme, Stil, Tempo,
Tonart, Liedtext und ein Titelbild, das Handy und Musik-Apps anzeigen.

**Lyric-Video in 1080p** im Farbverlauf des Stils, oder vor einem eigenen Bild (Tab Pfade).

**Restzeit und Meldung.** Während ein Song entsteht, steht da, wie lange es nach früheren Läufen derselben Art noch
dauert. Ist ein längerer Lauf fertig, meldet Windows das unten rechts; so kannst du solange etwas anderes machen.

**Tastenkürzel.** Leertaste spielt oder hält an, Strg+Enter erzeugt den Song, Strg+Z nimmt die letzte Änderung an
den Noten zurück. Nicht, während du in ein Feld schreibst.

**Speicherplatz.** Im Einrichten-Assistenten steht neben jedem eingerichteten Baustein, wie viel er belegt; „Entfernen“
löscht ihn (neu einrichten geht jederzeit). Darunter: wie groß Songs und aufgehobene Projekte sind, „Projekte löschen
(Songs bleiben)“ und „Aufräumen“ für Zwischenspeicher und alte Protokolle.

## Jede neue Funktion lässt sich abschalten

| Funktion | Wo |
| --- | --- |
| Romaji japanisch singen | Tab Text |
| Comping, Studio-Kette, Ausdruck pro Phrase | Tab Gesang |
| Alles vom Gesang 1.1: Noten für NEUTRINO, StyleShift pro Sektion, Begleitstimmen, Stil-Effekte, Platz in der Band, Airwindows, PSOLA | Tab Gesang |
| Gesangsklang wie im Vorbild | Tab Song, unter den Vorbildern |
| Bass mit Ghost-Notes, Gitarren-Anschlag | Tab Band |
| Echtes Schlagzeug, echte Grooves, Bewertung, Veredler, KI-Begleitung | Tab Pfade |
| Mix pro Instrument (Demucs) und alles andere von den Vorbildern | Tab Song, unter den Vorbildern |
| Verschiedene Tonarten im Album | im Album-Fenster |
| Takt, Rap-Teil (Sektion im Ablauf) | Tab Song |
| Eigener Text für Wiederholungen, Text-Helfer | Tab Text |
| Rap von VOICEVOX, Idol-Rufe | Tab Gesang |
| Vocal Chops, Ritardando | Tab Band, „Lebendige Band“ |
| Off-Vocal und A-cappella, True Peak, MP3-Tags | Tab Mix |
| Flügel, Bass und Gitarre aus Aufnahmen, Lyric-Video in den Farben des Stils | Tab Pfade |
| Wiederverwenden, Protokoll, Update-Suche, Assistent beim Start, Meldung wenn fertig, Tastenkürzel, Projekte aufheben, Größe des Verlaufs, Datenordner | Pfade › App |
| Tonhöhe glätten, Härte zähmen, Verzierungen, Gesang im Groove, DiffSinger-Ausdruck, Gruppe, Klang von „Sprechen“ (1.3) | Tab Gesang |
| Partikel erkennen (1.3) | Tab Text |
| Beste Melodie, Auftakte, Spannungstöne, Höhepunkt, Triolen, Akkord-Würze, Intro-Riff (1.3) | Tab Song |
| Kime, Band im Groove, Bass-Läufe, Läufe, Anison-Grooves, Aufbau, Surge-Klänge, Verstärker (1.3) | Tab Band |
| Druck (1.3) | Tab Mix |
| KI-Melodie (1.3, Versuch) | Tab Pfade |

## Wo was liegt

| Ordner in Dokumente\Vloid Songs | Inhalt |
| --- | --- |
| `Songs` | der letzte Song mit allen Spuren; darin `verlauf`, `Entwurf`, `Alben` und `YouTube` |
| `Vorlagen`, `Vorbilder`, `Motive` | deine Vorlagen, Lieblingssongs zum Anhaken und MIDI-Dateien für die Melodie |
| `Protokolle` | was die App getan hat; gehört in jeden Fehlerbericht |
| `Fehlerberichte` | ZIPs von „Fehlerbericht speichern“ |
| `Atmer`, `Hall`, `DiffSinger` | wenn du sie anlegst: eigene Atem-Aufnahmen, Räume für den Gesang und DiffSinger-Stimmen |
| `Einstellungen.json` | alle Einstellungen |

Klänge und Modelle liegen im Programmordner unter `tools`, weil sie groß sind und zur App gehören.

---

# Im Detail

Hier steht genauer, was jeder Teil tut, mit den Optionen der Kommandozeile.

## Gesang mit NEUTRINO

NEUTRINO darf die App nicht selbst laden. Von [studio-neutrino.com](https://studio-neutrino.com/) laden, entpacken und unter Hilfe › Einrichten den Ordner wählen, in dem `bin` und `model` liegen. Alternativ wie früher:

1. NEUTRINO (`NEUTRINO-windows-v3.1`) und die Stimme MERROW (`めろう（NEUTRINO-Library）-v3.1`) herunterladen und beide Ordner in den Projektordner legen.
2. `python setup_neutrino.py` kopiert die Stimme an die richtige Stelle.

Die App ruft NEUTRINO so auf, wie es die `Run.bat` der installierten Version vorgibt, und erkennt dabei v2 (mit `NSF.exe`) und v3 (schreibt die WAV selbst). Neuere Versionen von [studio-neutrino.com](https://studio-neutrino.com/) klingen besser (ab v3.2.2 mit neuem Vocoder) und funktionieren genauso.

Damit der Gesang natürlich klingt, bereitet die App die Noten für NEUTRINO vor: ein Takt Vorlauf, kurze Pausen innerhalb einer Phrase werden an die Note davor gebunden, und die Melodie bleibt im Tonumfang der gewählten Stimme. Männliche Stimmen (NAKUMO, SOMA, RUNO) singen eine Oktave tiefer. Im Refrain singt NEUTRINO eine zweite Stimme dazu, der Hauptgesang wird gedoppelt, und ein De-Esser nimmt scharfe S-Laute zurück.

Im Tab „Gesang“ wählst du die Stimme, ob im Refrain eine zweite Stimme mitsingt, und die Klangfarbe (StyleShift): plus klingt heller, minus dunkler. StyleShift braucht eine NEUTRINO-Version, die die Option `-k` kennt; sonst singt NEUTRINO ohne. Zu Beginn jedes Songs steht im Protokoll, welche NEUTRINO-Version und welche Stimmen gefunden wurden.

Schlägt NEUTRINO fehl, steht die Meldung im Protokoll, und die App versucht es mit VOICEVOX; läuft das auch nicht, nimmt sie die lokale Vorschau-Stimme (Windows-Sprachausgabe plus Tonhöhen-Korrektur).

**Strophe ruhig, Refrain kräftig:** Mit „StyleShift pro Sektion“ singt NEUTRINO die Strophen eine Stufe tiefer und ruhiger und die Refrains eine Stufe heller und kräftiger (Regler daneben, `--strophe-stil`, `--refrain-stil`, aus mit `--ohne-sektions-stil`). Dafür singt NEUTRINO zweimal, geschnitten wird in den Pausen; zweite Stimme und Chor singen wie der Refrain. Die NEUTRINO-Ausgabe mit Tuning-Tool (.ex) kennt keinen StyleShift; dann singt sie alles gleich, und im Protokoll steht ein Hinweis.

**Fassungen:** Unter „Fassungen“ 2 oder 3 wählen (oder `--fassungen 3`). NEUTRINO singt den Song dann mehrmals, und die App nimmt jede Phrase aus der Fassung ohne grobe Fehler (falscher Ton, Kiekser, Aussetzer; Comping, ausgeschaltet die beste ganze Fassung, `--ohne-comping`). Alle Fassungen haben denselben StyleShift, damit die Farbe nicht von Phrase zu Phrase springt; singt NEUTRINO jedes Mal genau dasselbe, singt die App eine Stufe heller und dunkler. Mit `--ohne-gleiche-fassungen` geht es wie bis 1.0: eine Fassung heller, eine dunkler, gewertet nach jeder Abweichung von den Noten. Jede Fassung dauert so lange wie die erste.

**Stimmen-Casting:** Der Knopf über den Noten (oder `--casting`) lässt jede installierte Stimme den Refrain des letzten Songs singen. Du hörst sie nebeneinander und merkst dir mit dem Herz eine Lieblingsstimme für diesen Stil; mit „Lieblingsstimme je Stil“ wählt die App sie beim Wechsel des Stils.

**Support-Stimme (Versuch):** Eine zweite NEUTRINO-Stimme gibt der Hauptstimme eine andere Nuance, z. B. MERROW mit SOMA (`--support-stimme SOMA`). Das braucht eine NEUTRINO-Ausgabe mit `Run_support_model.bat`; fehlt die, singt die Hauptstimme allein und das Protokoll sagt warum. Ab Werk aus.

**Gesangs-Check:** Unter dem Player steht, wer gesungen hat, z. B. „Gesungen von NEUTRINO 3.2.2, MERROW, Grafikkarte“. Hat nur die Vorschau-Stimme gesungen, steht dort eine rote Warnung. Hilfe › Einrichten zeigt die NEUTRINO-Version und rät bei älteren als 3.2.2 zum Update.

**Noten für NEUTRINO:** Unter „Noten für NEUTRINO“ im Tab Gesang, jedes einzeln abschaltbar:

| Schalter | Was passiert |
| --- | --- |
| Haltezeichen ー für lange Vokale | lange Vokale (タワー) und Melismen stehen als ー statt als neue Silbe in den Noten (`--ohne-haltezeichen`) |
| Atemzeichen in langen Zeilen | nach spätestens zwei Takten Gesang wird in einer kurzen Pause geatmet, eine Zeile ohne Pause bekommt nach vier Takten ein Atemzeichen (`--ohne-atemzeichen`) |
| Schnelle Stellen flüssig | zwei Töne unter 100 ms mit Doppelvokal (か + い) singt NEUTRINO auf einem Ton (`--ohne-doppelvokale`) |
| Englisch als Katakana | love → ラブ, zuerst typische Song-Wörter, dann das Wörterbuch alkana, dann das Modell e2k (`--ohne-englisch`) |
| Singbare Melodie | keine Sprünge über eine Quinte auf kurzen Silben, kein Spitzenton nur eine Sechzehntel lang, spätestens nach 8 Sekunden eine Atempause (`--ohne-singbarkeit`) |

**Begleitstimmen:** Die zweite Stimme wechselt von Refrain zu Refrain (nur Phrasenenden, Terz darunter, darüber, Oktave) und ist links und rechts gedoppelt. Im Refrain singt NEUTRINO Flächen auf „Uuh“ und „Aah“ statt des Keyboard-Chors, im letzten Refrain kommen Ad-libs in die Lücken (`--ohne-harmonie-wechsel`, `--ohne-doppel-harmonie`, `--ohne-flaechen`, `--ohne-adlibs`).

**Duett:** Im Tab „Gesang“ unter „Duett mit“ eine zweite Stimme wählen (oder `--duett NAME` auf der Kommandozeile). Die beiden Stimmen wechseln sich in den Strophen ab, die Bridge singt die zweite, im Refrain singt die erste die Melodie und die zweite die zweite Stimme. Jede singt mit ihrem eigenen Tonumfang und steht etwas links bzw. rechts im Mix.

**Melodie und Text:** Die Melodie folgt dem Tonhöhenakzent der Wörter (Tokio-Japanisch aus dem Wörterbuch): wo ein Wort im Sprechen steigt, steigt meist auch die Melodie, ん und っ springen nicht. Lange Töne am Phrasenende werden oft auf zwei Töne gesungen (Melisma), auf dem Vokal der letzten Silbe; Balladen machen das öfter, Chiptune selten.

**Weiter bearbeiten in OpenUtau:** Neben `vocals.xml` für NEUTRINO schreibt die App die Gesangsnoten als UTAU-Projekt: `vocals.ust` (Melodie), `vocals_harmony.ust` (zweite Stimme) und beim Duett `vocals_duett_1.ust` und `vocals_duett_2.ust`. [OpenUtau](https://www.openutau.com/) öffnet sie mit Text, Tonhöhe und Tempo; dort lässt sich jede Note von Hand nachbessern oder mit einer anderen Stimme singen.

## Gesang mit VOICEVOX

[VOICEVOX](https://voicevox.hiroshiba.jp/) ist kostenlos und singt ab Version 0.16. VOICEVOX installieren und starten (die App reicht, sie läuft im Hintergrund), dann im Tab „Gesang“ bei „Gesang mit“ VOICEVOX wählen. Die Liste „VOICEVOX-Stimme“ zeigt alle Singstimmen, die VOICEVOX mitbringt; der Knopf daneben lädt sie neu. Läuft VOICEVOX auf einem anderen Rechner oder Port, die Adresse im Tab „Pfade“ eintragen (Standard `http://127.0.0.1:50021`).

VOICEVOX singt die Hauptstimme, die zweite Stimme im Refrain und mit zwei anderen Figuren den Chor im letzten Refrain. Silben, die VOICEVOX nicht kennt (zum Beispiel lateinische Buchstaben), singt es als „ら“, ein kleines „っ“ wird eine kurze Pause. Ist NEUTRINO gewählt, aber nicht da, springt VOICEVOX automatisch ein. Lautstärke pro Silbe und Ausdruck pro Phrase gibt die App VOICEVOX direkt mit, es singt also selbst laut und leise (`--ohne-voicevox-dynamik`: erst danach).

## Gesang mit DiffSinger (Versuch)

[DiffSinger](https://github.com/openvpi/DiffSinger) ist eine freie Gesangs-KI; viele Stimmen dafür gibt es für [OpenUtau](https://www.openutau.com/). Eine Stimme ist ein Ordner mit `dsconfig.yaml`. Die App findet Stimmen in OpenUtau (`Singers`) und im Ordner `DiffSinger` im Datenordner; im Tab Gesang unter „DiffSinger (Versuch)“ lässt sich auch ein Ordner wählen. Dann bei „Gesang mit“ DiffSinger wählen (`--engine DiffSinger --diffsinger-stimme ORDNER`).

Die App singt mit dem Modell der Stimme selbst (onnxruntime, nach der Logik von OpenUtau): Phoneme aus dem Wörterbuch der Stimme, Tonhöhe aus den Noten mit Vibrato und Übergängen, Energie und Hauch aus dem Varianz-Modell, wenn die Stimme eines hat, und den Vocoder aus der Stimme oder aus OpenUtaus `Dependencies`. Das läuft auf dem Prozessor und braucht etwa doppelt so lang wie der Song. Klappt es nicht, singt NEUTRINO, dann VOICEVOX. Jede Stimme hat ihre eigene Lizenz, sie steht in ihrem Ordner; viele erlauben keine kommerzielle Nutzung.

## Eigene Gesangsspur und Tuning-Tools

**Noten für Tuning-Tools:** Der Knopf über den Noten (oder `--noten-zip DATEI`) packt MusicXML (für NEUTRINO und sein Tuning-Tool), UST (OpenUtau), MIDI und eine kurze Anleitung in ein ZIP.

**Eigene Gesangsspur:** Im Tab Gesang unter „Eigene Gesangsspur“ eine WAV wählen (`--eigener-gesang WAV`), die du woanders gesungen oder bearbeitet hast. Sie ersetzt die Hauptstimme, wird an den Noten ausgerichtet (`--ohne-ausrichten`: sie beginnt mit dem Song) und läuft durch dieselbe Kette. Zweite Stimme und Chor singt weiter die Engine.

**Eine Phrase neu singen:** Doppelklick auf einen Ton in der Piano-Roll, dann einen anderen StyleShift oder eine andere Stimme wählen. NEUTRINO singt nur diese Phrase neu, der Rest kommt aus dem Gedächtnis (`_gesungen` im Song-Ordner).

## Lebendiger Gesang

Unter „Lebendiger Gesang“ im Tab „Gesang“, jedes einzeln abschaltbar:

| Schalter | Was passiert |
| --- | --- |
| Atmer vor den Phrasen | vor jeder Zeile ein leises Einatmen; vor langen Zeilen ein tieferes |
| Echo auf dem letzten Wort | das letzte Wort am Ende jeder Sektion und jeder zweiten Refrain-Zeile hallt in punktierten Achteln links und rechts nach |
| Chor im letzten Refrain | zwei weitere Stimmen singen die Melodie mit: mit NEUTRINO die anderen installierten Stimmen (sonst dieselbe heller und dunkler), mit VOICEVOX zwei andere Figuren, mit der Vorschau-Stimme vier verstimmte Kopien der eigenen Stimme |
| Vibrato | 1 = wie die Stimme singt, 0 = gerade Töne, 2 = doppelt so viel; lange Töne ohne eigenes Vibrato bekommen eines |
| Übergänge | 1 = wie gesungen, 0 = die Töne springen (wie hartes Autotune), 2 = die Stimme gleitet doppelt so lange |
| Ausdruck pro Phrase | jede Zeile wird zu ihrem höchsten Ton hin lauter und heller und klingt weich aus; Strophen leiser als Refrains (`--ohne-ausdruck`) |
| Studio-Gesangskette | leichte Bandsättigung, Hall und Delay je Sektion und im Refrain eine echte Doppelung aus der zweiten Fassung (`--ohne-gesangskette`) |
| Echte Atmer | liegen Atem-Aufnahmen (WAV, FLAC) im Ordner `Atmer` im Datenordner, nimmt die App sie nach Phrasenlänge statt des Rauschens (`--ohne-echte-atmer`) |
| Lautstärke pro Silbe | betonte Silben (Wortakzent, starke Zählzeit) etwas lauter, weicher Einsatz am Phrasenanfang (`--ohne-silben-lautstaerke`) |
| Band macht dem Gesang Platz | wie das Plugin Trackspacer: die Band wird in den Frequenzen leiser, in denen gerade gesungen wird, bis 3 dB (`--ohne-platz`) |
| Gesang reitet auf der Band | der Gesang steht immer gleich weit über der Band, bis 4 dB (`--ohne-nachfuehren`) |
| Platte aus Impulsantwort | Faltungshall statt Algorithmus; eigene Räume als WAV im Ordner `Hall` im Datenordner (`--ohne-platte`) |
| Delay weicht dem Gesang | das Delay wird leiser, solange gesungen wird (`--ohne-delay-ducking`) |
| Kette pro Stimme und Stil | eigene Klangeinstellungen für helle und tiefe Stimmen, Ballade weicher, Rock mit mehr Sättigung (`--ohne-stimmkette`) |
| Airwindows-Effekte | mit Airwindows Consolidated (Hilfe › Einrichten oder `setup_airwindows.py`): Bandsättigung ToTape9 auf dem Gesang, Console7 auf jeder Spur und der Summe (`--ohne-airwindows`) |

**Stil-Effekte** (eigene Gruppe im Tab Gesang): Telefon in der ersten Zeile, Stottern vor dem Refrain, harter Tune im Refrain und verschobene Formanten. Jeder Stil nimmt, was zu ihm passt, z. B. Future Bass die ersten drei, Lo-Fi nur das Telefon (`--ohne-telefon`, `--ohne-stutter`, `--ohne-hardtune`, `--ohne-formant`). **Gesang swingt mit:** Swingt die Band (Lo-Fi oder Swing ab 0,2), setzen die Töne auf der zweiten Sechzehntel genauso später ein (`--ohne-gesangsswing`).

Vibrato und Übergänge ändert die App bei VOICEVOX direkt in der Tonhöhenkurve, bevor gesungen wird. Bei NEUTRINO rechnet sie die fertige Aufnahme Phrase für Phrase mit Praat-PSOLA (parselmouth) um; die Stimme behält dabei ihren Klang. Mit `--ohne-psola` nimmt sie wie bis 1.0 den WORLD-Vocoder, der eine Spur rauer klingt. Bei 1 und 1 bleibt die Aufnahme unberührt.

## Klang der Instrumente

Die Instrumente werden mit dem SoundFont `soundfont.sf2` (GeneralUser GS) in Stereo gerendert. Am besten klingt das mit FluidSynth, das alle Feinheiten des SoundFonts umsetzt. Einmal ausführen:

```powershell
uv run setup_fluidsynth.py
```

Das lädt FluidSynth 2.6 nach `tools\fluidsynth\bin`. Ohne FluidSynth rendert `tinysoundfont`, das mit `uv sync` installiert wird. Im Protokoll steht, welcher der beiden spielt. Wer einen anderen SoundFont nutzen möchte, trägt ihn in den Einstellungen ein.

Noch besser klingen einzelne Instrumente mit zusätzlichen SoundFonts. Einmal ausführen:

```powershell
uv run setup_soundfonts.py
```

Das lädt etwa 250 MB nach `tools\soundfonts` (mit `--ohne-verzerrt` 130 MB weniger, dann ohne die verzerrte Gitarre). Danach spielen diese Instrumente von selbst aus den neuen Dateien:

| Instrument | SoundFont | Lizenz |
| --- | --- | --- |
| Flügel, Tine-E-Piano, Streicher, Pizzicato, Harfe, Pauken, Bläser, Hörner, Flöte, Oboe, Klarinette | MS Basic von MuseScore 4 (nur mit FluidSynth) | MIT |
| FM-E-Piano (City Pop) | FreePats FM Piano 1 | CC0 |
| cleane und verzerrte E-Gitarre | FreePats Electric Guitar FSBS | CC0 |
| Schlagzeug (Rock: Red Zeppelin, sonst Black Pearl) | AVL Drumkits von Glen MacArthur | CC-BY-SA 3.0 |

Alles andere spielt weiter GeneralUser GS. Im Tab „Pfade“ steht, wie viele der zusätzlichen SoundFonts da sind, und ein Schalter stellt sie zum Vergleichen ab. Mit einem eigenen SoundFont in den Einstellungen bleiben sie aus (zeigt die Einstellung auf den mitgelieferten `soundfont.sf2`, zählt das nicht als eigener).

**Orchester aus echten Aufnahmen:** Am echtesten klingen Streicher, Bläser, Harfe, Pauken und Stabspiele aus den Aufnahmen von [VSCO 2 Community Edition](https://github.com/sgossner/VSCO-2-CE) (Versilian Studios, CC0). Einmal ausführen:

```powershell
uv run setup_samples.py
```

Das lädt etwa 1,2 GB nach `tools\samples` (mit `--nur Violin Harp` nur einzelne Instrumente). Bricht es ab, macht der nächste Start dort weiter. Danach spielen Streicher, Solo-Geige, Bratsche, Cello, Kontrabass, Tremolo, Pizzicato, Harfe, Pauken, Trompete, Posaune, Tuba, Horn, Bläsersatz, Flöte, Piccolo, Oboe, Klarinette, Fagott, Glockenspiel, Marimba, Xylophon und Röhrenglocken aus den Aufnahmen. Ein eingebauter Sampler spielt sie (`sfz.py`, liest das SFZ-Format): kurze Töne nehmen die kurz gespielten Aufnahmen (Spiccato, Staccato), Streicher- und Bläsersätze verteilen ihre Töne nach der Tonhöhe auf Geigen, Bratschen, Celli und Kontrabässe bzw. Trompeten, Posaunen und Tuba, und jedes Instrument wird auf dieselbe Lautstärke gebracht. Langsam anschwellende Streicher setzen etwas später in der Aufnahme ein, damit sie auf dem Schlag kommen. Der Schalter „Orchester aus echten Aufnahmen“ im Tab „Pfade“ (oder `--ohne-samples`) stellt das ab; wie bei den SoundFonts bleibt es mit einem eigenen SoundFont aus.

**Flügel, E-Bass und E-Gitarre aus Aufnahmen:** `setup_band.py` lädt den Salamander-Flügel (Yamaha C5 von Alexander Holm, CC BY 3.0, 8 von 16 Anschlag-Schichten), den Growlybass und die Emily-Gitarre (Karoryfer Samples, CC0), zusammen etwa 550 MB nach `tools\samples\Band` (mit `--nur bass` nur eines). Flügel, Finger- und Plektrum-Bass sowie Jazz- und saubere E-Gitarre spielen dann daraus, Slides im Bass inklusive; verzerrte Gitarren schicken die direkt eingespielte Emily-Gitarre in den Verstärker (`band_library.py`). Der Schalter „Flügel, E-Bass und E-Gitarre aus echten Aufnahmen“ im Tab „Pfade“ (oder `--ohne-band-samples`) stellt das ab.

**Echtes Schlagzeug und Grooves:** `setup_drums.py` lädt das DRS Kit (DrumGizmo, CC BY 4.0, etwa 130 MB), ein im Studio aufgenommenes Schlagzeug mit mehreren Anschlag-Schichten; akustische Schlagzeuge spielen dann daraus (`drum_kit.py`, `--ohne-echtes-schlagzeug`). `setup_grooves.py` lädt das Groove MIDI Dataset (Google Magenta, CC BY 4.0, etwa 3 MB): Pop, Rock, Ballade, City Pop und Idol-Pop spielen Phrasen und Fills echter Schlagzeuger mit ihrem Timing (`grooves.py`, `--ohne-echte-grooves`). Der Bass spielt Ghost-Notes und Slides (`--ohne-bass-leben`), die Gitarre schlägt je nach Teil anders an (`--ohne-anschlagmuster`).

Supersaw, Pluck, Pad, Lead, Chiptune-Klänge, Reese- und Sub-Bass und die breiten Future-Bass-Akkorde erzeugt die App selbst (`synth_engine.py`), ebenso Riser, Becken-Swells, Impacts und Downlifter vor den Refrains (`fx.py`).

**Schlagzeug aus der Drum-Machine:** Im Tab „Band“ steht beim Schlagzeug statt einer Spielweise der Klang: „wie der Stil“, das SoundFont-Schlagzeug oder die Drum-Machine 808 oder 909. Die App baut jeden Schlag wie die Roland-Maschinen aus Sinus, Rauschen und Rechteck-Schwingungen (`drum_machine.py`): die 808 mit langer, tiefer Bassdrum und metallischen Hi-Hats, die 909 kurz und druckvoll mit hellerer Snare. Ein offenes Hi-Hat verstummt, sobald ein geschlossenes kommt. Future Bass spielt von sich aus mit der 808.

**Gitarren über Verstärker und Box:** Verzerrte E-Gitarren (Overdrive und Distortion) spielt der SoundFont sauber, verzerrt wird erst danach wie mit einem echten Verstärker, und eine Box nimmt das Kratzen weg (`guitar_amp.py`). Das klingt rockiger, besonders bei Akkorden. Wer eine echte Box hören möchte, wählt im Tab „Pfade“ eine Impulsantwort (WAV); kostenlose gibt es viele im Netz. Ein Schalter im Tab „Band“ stellt das ab.

**Surge XT und andere VST3-Instrumente:** [Surge XT](https://surge-synthesizer.github.io) ist kostenlos und hat echte Supersaws, Reese-Bässe und Flächen, wie Future Bass und Drum and Bass sie brauchen. Ist es installiert, bietet der Tab „Pfade“ es an („Surge XT gefunden – übernehmen“), sonst trägt man den Pfad zur `.vst3`-Datei dort ein. Im Tab „Band“ öffnet „Klang wählen“ pro Spur (Synth, Lead, Bass, Gegenstimme) das Fenster des Instruments: einen Klang aussuchen, das Fenster schließen, und die Spur spielt ihn. „zurück“ gibt die Spur wieder dem Stil. Ohne gewählte Klänge spielt das Instrument wie bisher Synth und Lead mit seinem Standardklang. Getestet ist das mit einem nachgebauten Instrument, nicht mit Surge XT selbst; klappt etwas nicht, steht es im Protokoll, und die Spur spielt wie sonst.

**Schneller rendern:** Die Spuren rendern gleichzeitig auf bis zu sechs Prozessorkernen. Mit vier Kernen ist das Rendern etwa zweieinhalbmal so schnell (die Instrumente eines ganzen Songs in 21 statt 50 Sekunden); VST-Instrumente spielen nacheinander.

## Vorbild-Songs

Im Tab „Song“ gibst du jedem Song einen oder mehrere Vorbild-Songs (WAV, MP3, FLAC, OGG oder M4A), jeden mit einem Gewicht, wie stark er zählt. Lieblingssongs, die du öfter nimmst, legst du in den Ordner `Vorbilder` im Datenordner (oder einen eigenen, Tab „Pfade“); dort hakst du sie nur noch an.

Was die Vorbilder bestimmen, schaltest du einzeln an und aus:

| Schalter | Was passiert |
| --- | --- |
| Mastering | Klang und Stereobreite des Masters wie die Vorbilder ([matchering](https://github.com/sergree/matchering)); bei mehreren Vorbildern nach ihrem Mittel |
| Lautstärke-Verlauf | ruhige und laute Teile liegen so weit auseinander wie in den Vorbildern |
| Gesangslautstärke | der Gesang steht so laut gegen die Band wie in den Vorbildern (eine Schätzung; Vorbilder ohne Gesang ändern nichts) |
| Mix pro Instrument | mit Demucs (`setup_demucs.py`): Gesang, Schlagzeug, Bass und Rest einzeln so laut gegen den ganzen Song und so hell wie in den Vorbildern, höchstens 6 dB lauter oder leiser und 4 dB mehr oder weniger Höhen; ersetzt dann die Schätzung der Gesangslautstärke (`--ohne-vorbild-gruppen`) |
| Gesangsklang wie im Vorbild | mit Demucs: die Klangkurve des Gesangs in Terzbändern wie beim Gesang der Vorbilder, höchstens 4 dB je Band (`--ohne-vorbild-gesangsklang`) |
| Tempo und Tonart vorschlagen | ein Klick übernimmt das gemessene Tempo und die Tonart |
| Stil vorschlagen | ein Klick übernimmt den Stil, der am besten zu den Vorbildern passt |

Gemessen wird mit librosa, jede Datei nur einmal (`vorbild_messungen.json` im Datenordner). Demucs zerlegt den lautesten Abschnitt jedes Vorbilds einmal in vier Gruppen und merkt sich die Messung (`vorbild_gruppen.json`); es läuft in einer eigenen Umgebung in `tools\demucs` (`uv run setup_demucs.py`, mit `--cpu` ohne Grafikkarte). Aus den Vorbildern landet nichts im Song, sie werden nur gemessen.

## Lautheit des Masters

Im Tab „Mix“ wählst du, wie laut der fertige Song wird: Standard -12 LUFS, -14 für YouTube und Spotify (die lautere Songs ohnehin herunterregeln), -16 für Apple Music oder -9 für den Club. Das gilt auch beim Mastering nach Vorbild-Songs.

**Bewegung im Mix:** Der Mix klingt nicht von vorn bis hinten gleich. Im letzten Takt vor jedem Refrain verliert die Band nach und nach ihre Bässe (Filter) und wird etwas leiser; mit dem Refrain ist alles auf einmal wieder da. Strophen haben weniger Hall und klingen näher, Bridge, Intro und Outro mehr. Im Refrain ist die Band breiter. Der Schalter „Bewegung im Mix“ im Tab „Mix“ (oder `--ohne-bewegung`) stellt das ab (`mix_movement.py`).

## Klang-Veredler (ACE-Step, Versuch)

[ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) ist ein KI-Modell für Musik. Die App gibt ihm die fertige Band (ohne Gesang und Effekte) als Vorlage: Takt, Akkorde und Melodie bleiben, den Klang spielt ACE-Step neu ein. Danach liegt die neue Band genau unter dem Gesang, und die App mischt beides zu einer zweiten Fassung, `final_mix_veredelt.wav` (und `final_song_veredelt.mp3`). Der normale Song bleibt, wie er ist; im Player heißt die zweite Fassung „Veredelt (ACE-Step)“. Der Gesang geht nie durch ACE-Step, denn die Lizenz von NEUTRINO verbietet, seine Stimme umzuwandeln.

Im Tab „Mix“ stellst du ein, wie stark ACE-Step den Klang verändert (wenig: fast wie vorher, viel: freier, aber die Melodie kann sich verbiegen), und kannst den Klang auf Englisch beschreiben, z. B. `dreamy shoegaze, washed out guitars`. Leer nimmt die App eine Beschreibung passend zum Stil. Einmal einrichten:

```powershell
uv run setup_ace_step.py           # etwa 20 GB: Modelle etwa 10 GB, PyTorch mit CUDA etwa 6 GB
```

Das lädt ACE-Step in einer festen Fassung nach `tools\ace-step`, legt dort seine eigene Umgebung an (die App bleibt unberührt), lädt die Modelle und prüft, ob die Grafikkarte erkannt wird. Es braucht eine NVIDIA-Grafikkarte; mit 4 GB lagert ACE-Step Teile in den Arbeitsspeicher aus und rechnet mit kleineren Zahlen (INT8), das dauert pro Song ein paar Minuten. Ausschalten: Schalter im Tab „Pfade“ oder `--ohne-veredler`. Es ist ein Versuch: Getestet ist der Ablauf mit einem nachgebauten Modell, nicht mit ACE-Step selbst. Klappt etwas nicht, steht es im Protokoll (die ganze Ausgabe von ACE-Step in `tools\ace-step\letzter_lauf.log`), und es gibt nur den normalen Song.

## KI-Begleitung (Versuch)

Der [Anticipatory Music Transformer](https://github.com/jthickstun/anticipation) (Stanford CRFM, Apache 2.0) bekommt Gesangsmelodie, Bass sowie Bassdrum und Snare des Songs als feste Vorgabe und schreibt dazu Klavier, Gitarre, Streicher, Synths und Bläser. Diese Töne ersetzen die komponierten Begleitstimmen; Melodie, Bass, Schlagzeug und Gesang bleiben. Das Modell kennt nur 100 Sekunden, deshalb schreibt es in Stücken von 30 Sekunden, jedes mit den letzten 5 als Anfang. Mit Grafikkarte nimmt es das mittlere Modell, sonst das kleine; gleiche Vorgabe und gleicher Seed werden nicht noch einmal geschrieben (`begleitung.json` im Ausgabeordner).

```powershell
uv run setup_begleitung.py          # eigene Umgebung in tools\begleitung, mit Grafikkarte etwa 4 GB
```

Ab Werk aus: einschalten unter „Pfade“ oder mit `--ki-begleitung`. Ob es besser klingt als die eingebaute Begleitung, ist offen; vergleichen lässt es sich mit festem Seed und A/B im Verlauf. Getestet ist der Ablauf mit einem nachgebauten Modell; die Ausgabe des echten steht in `tools\begleitung\letzter_lauf.log`.

## Liedtext

Im Tab „Text“ steht der Text pro Sektion; rechts daneben zeigt die App, welche Silben gesungen werden. Japanisch darf ganz normal geschrieben werden, mit Kanji und ohne Leerzeichen: `夜の街を歩いてた` wird zu よ る の ま ち お あ る い て た. Die Lesung der Kanji kommt aus dem Wörterbuch von fugashi (UniDic). Liest es ein Wort falsch, steht die richtige Lesung in eckigen Klammern dahinter: `君[きみ]`. Partikel singt die App so, wie man sie spricht (は als わ), und ー wird als langer Vokal gesungen. Romaji geht auch (mit [jaconv](https://github.com/ikegami-yukino/jaconv)): Eine Zeile ganz in Romaji (`kimi no koe`) wird japanisch gesungen, außer es steht ein englisches Wort darin; neben Kana und Kanji wird jedes Romaji-Wort umgewandelt. Schalter im Tab „Text“, `--ohne-romaji`.

## Eigene Akkorde und eigene Melodie

Im Tab „Song“ stehen unter „Eigene Akkorde“ Felder für Strophe, Pre-Chorus, Refrain und Bridge. Dort gehen Akkordnamen (`F G Em Am`, `C/E`, `Bbmaj7`) oder Stufen (`IV V iii vi`); ohne `|` ist jeder Akkord ein Takt, mit `|` trennst du Takte (`F | G | Em Am`). Die Folge wiederholt sich, bis die Sektion voll ist, und klingt genau so, ohne die Schlusswendung des Stils. Intro, Outro und Solo spielen die Akkorde des Refrains. Steigt der letzte Refrain, steigen Akkordnamen mit. Leere Felder nehmen die Akkorde des Stils, Tippfehler zeigt das Feld sofort an.

Unter „Eigene Melodie“ wählst du eine MIDI-Datei, zum Beispiel aus einer DAW oder von einem Keyboard eingespielt, und die Sektion, in der sie gesungen wird (Standard: Refrain). Die Spur mit den meisten Tönen zählt, auf Sechzehntel gerundet; bei Akkorden singt der höchste Ton. Die Melodie wiederholt sich, bis die Sektion voll ist (eine längere Melodie macht die Sektion länger, höchstens 16 Takte), und rückt in ganzen Oktaven in die Stimmlage. Sie wird nicht in die Tonart umgerechnet: Schreib sie in der Tonart des Songs. Der Text wird Silbe für Silbe auf die Töne gelegt. Feld leeren, dann wird wieder komponiert.

**Melodie summen:** Statt einer MIDI-Datei geht auch eine Aufnahme (WAV, MP3, FLAC, OGG, M4A), zum Beispiel vom Handy: Summ oder sing die Melodie im Tempo des Songs, Ton für Ton („da-da-da“). Darunter im Tab „Song“ lädst du sie hoch (im Fenster: „Melodie summen“); die App erkennt die Töne (librosa pYIN), rundet sie auf Sechzehntel, legt den ersten Ton auf die Eins und trägt die fertige MIDI-Datei (`summen\<Name>.mid` im Ausgabeordner) oben als eigene Melodie ein. Wer etwas schief summt, macht nichts: Es zählt der Abstand zwischen den Tönen. Ist keine Melodie zu hören (Stille, nur Rauschen), sagt die App das und lässt das Feld, wie es war.

**Motive der Melodie:** Die komponierte Melodie baut jeden Takt aus einem Rhythmus und einer Bewegung (steigen, fallen, Bogen). Dazu kommen mehr eingebaute (Synkopen wie im J-Pop, Schlüsse mit Vorhalt, Zickzack, Umspielungen) und gelernte: Leg MIDI-Dateien mit Melodien, die dir gefallen, in den Ordner `Motive` im Datenordner (oder einen eigenen, Tab „Song“ unter „Motive der Melodie“). Aus jeder Datei zählen die einstimmigen Spuren in Gesangslage; jeder 4/4-Takt liefert seinen Rhythmus und seine Bewegung, häufige kommen öfter dran, und etwa die Hälfte der Takte singt dann gelernte. Beides hat einen Schalter (`--ohne-motive` schaltet beides ab, `--motive ORDNER` nimmt einen anderen Ordner). Neue Dateien im Ordner ändern auch Songs mit festem Seed; mit beiden Schaltern aus singt ein Seed dieselbe Melodie wie vor v5.

## MP3-Export

Für die MP3 braucht `pydub` das Programm ffmpeg (`winget install Gyan.FFmpeg`). Ohne ffmpeg entsteht der Song nur als `final_mix.wav`, und im Protokoll steht „MP3-Export übersprungen“.

## Lyric-Video

„Lyric-Video (MP4)“ unter dem Player (oder `--lyric-video`) macht aus dem Song ein Video in 1920×1080, zum Beispiel für YouTube: der Farbverlauf des Stils (wie beim Titelbild), unten die Wellenform des Songs und in der Mitte der Text, Silbe für Silbe in der Farbe des Stils eingefärbt, darunter schon die nächste Zeile. Ein eigenes Bild als Hintergrund wählst du im Tab „Pfade“ („Hintergrundbild des Lyric-Videos“, `--video-hintergrund BILD`); es wird auf 16:9 zugeschnitten. Mit dem Schalter „Lyric-Video in den Farben des Stils“ aus (`--ohne-stilfarben`) ist es dunkel mit pinkem Text wie bis 1.1. Die Zeiten kommen aus der Gesangsmelodie, der Text steht also genau dann da, wenn er gesungen wird; die Zeilen sind die Zeilen aus dem Tab „Text“. Das Video baut ffmpeg (dasselbe wie für die MP3, die Version von Gyan hat alles dabei) und landet als `lyric_video.mp4` im Ausgabeordner. Ein Song ohne Gesang hat keinen Text zum Mitlesen und damit auch kein Lyric-Video.

## Die Oberfläche

- **Song erzeugen** (oben rechts) macht einen neuen Song. Daneben wählst du, wie viele Fassungen am Stück entstehen; alle landen im Verlauf.
- **Player:** Der fertige Song spielt mit Wellenform; ein Klick in die Wellenform springt an diese Stelle. Unter „Anhören“ hörst du jede Spur einzeln, an derselben Stelle im Song. Darunter läuft der Text zum Mitlesen wie beim Karaoke mit, die gesungenen Silben in Pink und klein darunter die nächste Zeile; der Schalter „Mitlesen“ blendet ihn aus.
- **Noten:** die Piano-Roll aller Spuren mit Tonhöhe, sie läuft beim Abspielen mit. Ein Klick auf eine Spur in der Legende blendet sie aus, ein Klick in die Noten springt im Player dorthin.
- **Gesang bearbeiten:** Mit diesem Schalter über den Noten lassen sich die Töne der Gesangsmelodie nach oben oder unten ziehen, oder anklicken und mit den Pfeiltasten verschieben (mit Umschalt eine Oktave). „Neu singen“ macht denselben Song mit den geänderten Tönen; Zweitstimme, Chor und die Hook im Intro und Outro gehen mit. „Änderungen verwerfen“ stellt die Töne wieder her. Würfelst du Melodie oder Akkorde neu, fallen die Änderungen weg, weil die Töne dann andere sind.
- **Tonlängen:** Am rechten Rand eines Tons ändert sich der Mauszeiger; dort gezogen (oder angeklickt und mit Pfeil links/rechts) wird der Ton in Sechzehnteln kürzer oder länger, höchstens bis zum nächsten Ton.
- **Vorschau:** „Vorschau“ spielt die geänderten Stellen sofort, mit einem Synth statt Gesang über der Band, ein Takt davor und danach. Das dauert Sekunden; gefällt es, singt „Neu singen“ die Änderungen richtig.
- **Neu würfeln:** Ein Knopf pro Teil (Melodie, Akkorde, Schlagzeug, jedes Instrument). Nur dieser Teil wird neu, der Rest des Songs bleibt. Rechts darüber wählst du, wo: im ganzen Song oder nur in einer Sektion, etwa nur die Melodie im Refrain oder nur das Schlagzeug in der Strophe.
- **3 Refrain-Melodien zur Auswahl:** drei neue Melodien für den Refrain als kurze Vorschau (Melodie als Synth über den Akkorden, in Sekunden fertig). Anhören, „nehmen“ drücken, und der ganze Song entsteht mit dieser Melodie.
- **Seed festhalten:** Danach macht „Song erzeugen“ wieder diesen Song, mit allem, was du inzwischen geändert hast (Mix, Gesang, Text). Das Seed-Feld im Tab „Song“ leeren, dann gibt es wieder jedes Mal einen neuen Song.
- **Als ZIP für die DAW:** alle Spuren als WAV und MIDI, siehe unten. **Lyric-Video (MP4):** siehe oben.
- **Vergleichen:** Im Verlauf hat jeder Song die Knöpfe A und B. Wähl zwei Songs, dann stehen unter dem Player A und B; ein Klick wechselt an derselben Stelle im Song, so hörst du direkt, welcher Refrain oder welcher Mix besser ist.
- **Ablauf:** Im Tab „Song“ ziehst du die Sektionen in eine andere Reihenfolge, ein Klick auf eine Sektion wählt ihre Länge in Takten (gilt für alle Sektionen dieser Art, zum Beispiel ein kurzer Refrain mit 8 Takten).
- **Entwurf** (oben): ein Song in etwa einer Minute ohne NEUTRINO, die Lead-Stimme spielt die Melodie; er landet in `Songs\Entwurf` und nicht im Verlauf. **Richtig machen** macht danach genau diesen Song mit Gesang (`--entwurf`).
- **Album** (oben): bis zu 30 Songs am Stück, Stile reihum, auf Wunsch je eine `.txt` mit Liedtext pro Song; morgens nummeriert in `Songs\Alben\<Datum> <Name>` mit Wiedergabeliste und Titelliste, nach Note sortiert, wenn die Bewertung eingerichtet ist (`album.py`, `--album 10 --album-stile "Rock,Ballade"`).
- **Fertig für YouTube** (unter dem Player): MP3, Video, Titelbild (1280×720, mit Pillow gemalt) und Beschreibung in `Songs\YouTube\<Datum> <Titel>` (`youtube.py`, `--youtube [TITEL]`).
- **Abbrechen** (oben) beendet einen Song sofort; nach einem Absturz bietet die App beim nächsten Start „Weitermachen“ an.
- **Tabs rechts:** Song (Stil, Tempo, Tonart, Ablauf, Vorbild-Songs, eigene Vorlagen), Text (mit Vorschau, wie gesungen wird), Band (Spielweise, Lautstärke, Panorama, Mute/Solo pro Spur, Klang von Schlagzeug, Gitarren und VST-Instrument), Gesang, Mix, Verlauf und Pfade.

Alle Einstellungen speichert die App sofort. Eigene Vorlagen (Tab „Song“) merken sich Stil, Tempo, Tonart, Ablauf, Band, Gesang und Mix, aber nicht den Text; sie liegen in `Vorlagen` im Datenordner.

## Verlauf, Neu würfeln und Varianten

Jeder fertige Song landet zusätzlich im Unterordner `verlauf\`: die MP3 und daneben eine JSON-Datei mit allen Einstellungen und dem Seed. Im Tab „Verlauf“ ist das eine Song-Bibliothek: Suche, nur Favoriten, Sortieren nach Note oder Name, eigener Name und Notiz pro Song. Die 30 neuesten Songs bleiben (einstellbar unter Pfade › App, 0 = alle), Favoriten, Songs mit Namen und Album-Songs immer.

Gefällt dir alles außer einem Teil, wird nur dieser neu gewürfelt. Teile sind `chords` (Akkorde und Ablauf), `melody` (Gesangsmelodie, im Solo das Solo) und jedes Instrument: `piano`, `bass`, `guitar`, `strings`, `synth`, `brass`, `bells`, `choir`, `counter`, `perc`, `drums`. Mit einer Sektion dahinter (`melody:Chorus`, `drums:Verse`, `chords:Bridge`) wird der Teil nur dort neu; Sektionen sind `Intro`, `Build-up`, `Verse`, `PreChorus`, `Chorus`, `Bridge`, `Drop`, `Solo` und `Outro`.

```powershell
uv run vocaloid_generator\main.py --neu melody                  # der letzte Song mit neuer Melodie
uv run vocaloid_generator\main.py --neu drums --varianten 3     # drei Schlagzeug-Fassungen zur Auswahl
uv run vocaloid_generator\main.py --neu melody:Chorus          # nur die Refrain-Melodie neu
uv run vocaloid_generator\main.py --seed 42 --refrains 3       # drei Refrain-Melodien zum Anhören
uv run vocaloid_generator\main.py --seed 42 --refrain 2        # der ganze Song mit der zweiten
uv run vocaloid_generator\main.py --varianten 3                 # drei ganz neue Songs
uv run vocaloid_generator\main.py --aus-verlauf 2 --zip song.zip
```

Neue Akkorde ändern auch alles, was auf den Akkorden spielt; eine neue Melodie ändert die Gegenstimme mit, weil sie der Melodie antwortet. Die Refrain-Melodie spielt auch im Intro, Outro und Solo, also werden sie mit ihr neu.

**Die beste Fassung von selbst finden:** Bei mehreren Fassungen kann die App jede anhören und benoten, mit [Audiobox Aesthetics](https://github.com/facebookresearch/audiobox-aesthetics) von Meta. Das Modell hört die lautesten 30 Sekunden (meist den Refrain) und schätzt von 1 bis 10, wie gern man zuhört und wie sauber der Song klingt; die Note ist der Mittelwert. Geladen wird danach die Fassung mit der besten Note, im Verlauf steht bei jeder ihre Note. Einmal einrichten:

```powershell
uv run setup_bewertung.py          # mit NVIDIA-Grafikkarte etwa 3 GB
uv run setup_bewertung.py --cpu    # ohne Grafikkarte, kleiner und langsamer
```

Das legt in `tools\bewertung` eine eigene Umgebung mit PyTorch an (die App selbst bleibt unberührt) und lädt das Modell. Ausschalten: Schalter im Tab „Pfade“ oder `--ohne-bewertung`. Die Note ist eine Schätzung, kein Urteil: anhören lohnt sich trotzdem.

Die ZIP-Datei enthält den Mix, jede Spur als WAV (`Spuren\`) und MIDI (`MIDI\`), die Gesangsnoten als MusicXML und UST (`Gesang\`), `einstellungen.json` und `song.txt` mit Tempo und Tonart. Alle Spuren starten bei 0:00 und lassen sich so in jede DAW ziehen.

## Stile

Jeder Stil bringt eigene Instrumente, Spielweisen, Schlagzeug-Grooves und Akkordfarben mit:

| Stil | Klang |
| --- | --- |
| J-Pop Energy | Klavier, Overdrive-Gitarre, Streicher, Pluck und Supersaw, Glockenspiel, Chor, Gegenstimme, Shaker und Claps, Riser und Impacts |
| Dark Vocaloid | schnelles Sechzehntel-Klavier, verzerrte Gitarre, Chor, Celesta, Cello-Gegenstimme, Double-Bass-Drum im Refrain |
| Kawaii Chiptune | eigene Chiptune-Synths, Synth-Bass, Glockenspiel in Sechzehnteln, Four-on-the-Floor, Bass duckt unter der Kick |
| Rock | Gitarren doppelt links und rechts, Bass, Schlagzeug, Gitarren-Antworten und -Solo |
| Ballade | Klavier-Arpeggien, Orchester (Streicher, Pizzicato, Harfe mit Glissando, Pauken-Wirbel, Hörner), Pad, Spieluhr, Chor, Cello-Linie unter dem Gesang |
| City Pop | FM-E-Piano mit Septakkorden, Funk-Gitarre, Oktav-Bass, Bläser, Congas, Saxofon-Antworten |
| Future Bass | breite Supersaw-Akkorde, synkopisch zerhackt und stark unter der Bassdrum pumpend, Sub-Bass, Drum-Machine 808 mit Snare und Clap auf der Drei, Glockenspiel |
| Drum and Bass | 174 BPM, Two-Step mit Ghost-Notes, rollender Reese-Bass, Rhodes-Arpeggien mit Septakkorden, Flächen, Flöten-Antworten |
| Lo-Fi | Rhodes mit Jazz-Akkorden, gemütlicher Boom-Bap mit Swing, Jazz-Gitarre, Vibraphon; die Band klingt wie von einer alten Bandmaschine, und eine Schallplatte knistert (Schalter im Tab „Band“) |
| Idol-Pop | 180 BPM in Dur, Funk-Gitarre, Bläser-Stabs, Oktav-Bass, Four-on-the-Floor im Refrain, Claps und Tamburin, der letzte Refrain steigt fast immer |

Keine Sektion klingt zweimal gleich: Die zweite Strophe bekommt eine Gegenstimme, der letzte Refrain Chor und Glockenspiel in der Oktave der Hook, und im Refrain spielen mehrere Synth-Schichten zusammen.

Auch der Ablauf ändert sich von Song zu Song. Je nach Stil und Zufall steigt der letzte Refrain einen oder zwei Halbtöne oder bleibt in der Tonart, beginnt leise nur mit Klavier und Streichern (wie das „Ochisabi“ im J-Pop), die Bridge wird zum Breakdown ohne Schlagzeug, oder die zweite Strophe beginnt im Halftime. Was ein Song davon hat, steht im Protokoll unter „Ablauf“. „Akkorde“ neu würfeln würfelt auch das neu.

Im Tab „Band“ lässt sich pro Instrument eine andere Spielweise wählen, beim Schlagzeug der Klang. „wie der Stil“ nimmt die des Stils.

Die Sektion „Solo“ (im Tab „Song“ unter „Ablauf“ anhängen) ist ein Instrumental-Solo über den Akkorden des Refrains: Die Band spielt wie im Refrain, die Lead-Stimme spielt in Frage und Antwort, die Fragen zitieren die Hook, die Antworten werden zum Ende dichter und höher, und am Schluss läuft sie hinauf zum Grundton. Je nach Stil spielt das Solo eine verzerrte Gitarre (J-Pop, Rock, Dark, Idol-Pop), ein Chip-Synth (Kawaii), eine Geige (Ballade), ein Saxofon (City Pop, Lo-Fi) oder ein Synth-Lead (Future Bass, Drum and Bass).

`--style Lo-Fi` war bisher ein anderer Name für City Pop und ist jetzt ein eigener Stil.

## So entsteht ein Song

1. **Bauplan:** Jede Sektion bekommt eine bewährte Akkordfolge (zum Beispiel die Royal-Road-Folge des J-Pop). Gleiche Sektionen klingen gleich, der Pre-Chorus endet auf der Dominante, der Refrain auf der Tonika, und der letzte Refrain steigt oft einen oder zwei Halbtöne.
2. **Melodie:** Phrasen aus wiederkehrenden Rhythmus-Motiven, betonte Töne sind Akkordtöne, die Tonhöhe folgt dem Wortakzent, lange Töne am Phrasenende bekommen manchmal ein Melisma. Der Refrain wiederholt seine erste Phrase als Hook, Intro und Outro spielen diese Hook. Kurze Liedtexte werden wiederholt, lange machen die Sektion länger.
3. **Begleitung und Schlagzeug:** Spielweisen pro Instrument mit Stimmführung, Grooves mit Fills, Crash auf jedem Refrain, Snare-Wirbel und kurzer Stopp vor dem Refrain.
4. **Klang und Mix:** SoundFont-Rendering in Stereo (FluidSynth oder tinysoundfont, bessere Instrumente aus den zusätzlichen SoundFonts) auf mehreren Kernen, eigene Synths, Drum-Machine und Übergangs-Effekte, verzerrte Gitarren über Verstärker und Box, Klänge aus Surge XT, jede Spur auf ihre Ziel-Lautheit, EQ und Kompressor pro Spur, gemeinsamer Hall, De-Esser, Doppelung und Delay auf der Stimme, Echo auf dem letzten Wort, Atmer und Chor im letzten Refrain, Master auf die gewählte Lautheit (Standard -12 LUFS) mit Limiter. Spuren, an denen sich nichts geändert hat (gleiche Noten, gleicher Klang), rendert die App nicht noch einmal: Wer nur das Schlagzeug neu würfelt oder Töne im Gesang ändert, spart so das Rendern der übrigen Spuren; Gesang und Mix entstehen trotzdem neu.

Ohne Gesang (kein NEUTRINO, kein VOICEVOX, keine Vorschau-Stimme oder Gesang ausgeschaltet) spielt die Lead-Stimme die Gesangsmelodie.

## Einstellungen

Die App speichert alles in `Einstellungen.json` im Datenordner. Gibt es die noch nicht, liest sie `vocaloid_generator\settings.json` (die Starteinstellungen). Ungültige Werte (zum Beispiel ein Pfad, den es auf diesem Rechner nicht gibt) werden beim Laden durch Standardwerte ersetzt und im Protokoll gemeldet.

Jeder erzeugte Song meldet im Protokoll seinen Seed. Mit diesem Seed lässt sich derselbe Song später noch einmal erzeugen. Seit dem Neu-Würfeln pro Teil und pro Sektion hat jeder Teil in jeder Sektion seinen eigenen Zufall; ein Seed aus einer älteren Version ergibt deshalb einen anderen Song als damals.

## Kommandozeile

Die Kommandozeile nutzt dieselben Einstellungen wie die Oberfläche; `uv run vocaloid_generator\main.py --help` zeigt alle Optionen.

```powershell
uv run vocaloid_generator\main.py --style Rock --bpm 140 --key E --scale minor --seed 42
```

| Option | Bedeutung |
| --- | --- |
| `--seed` | gleicher Seed und gleiche Einstellungen ergeben denselben Song |
| `--bpm`, `--style`, `--key`, `--scale` | überschreiben die gespeicherten Einstellungen für diesen Lauf |
| `--output` | Ausgabeordner |
| `--settings` | eine andere Einstellungsdatei verwenden |
| `--neu TEIL[:SEKTION]` | nur diesen Teil des letzten Songs neu würfeln, der Rest bleibt; mit `:Chorus` nur im Refrain; mehrfach möglich |
| `--refrains N`, `--refrain NR` | N Refrain-Melodien als kurze Vorschau schreiben; mit `--refrain` und demselben `--seed` entsteht der ganze Song mit einer davon |
| `--akkorde SEKTION=AKKORDE` | eigene Akkorde, z. B. `"Chorus=F G Em Am"`; mehrfach möglich, `"Chorus="` nimmt wieder die des Stils |
| `--melodie-midi DATEI`, `--melodie-sektion SEKTION` | eigene Melodie aus einer MIDI-Datei, gesungen im Refrain oder in der angegebenen Sektion |
| `--summen AUFNAHME` | eine gesummte Melodie (WAV, MP3 …) in Noten verwandeln und als eigene Melodie singen lassen |
| `--motive ORDNER`, `--ohne-motive` | Rhythmen und Bewegungen der Melodie aus den MIDI-Dateien dieses Ordners lernen, oder nur die alten eingebauten |
| `--varianten N` | N Songs am Stück erzeugen; mit `--neu` N Fassungen der gewählten Teile |
| `--ohne-bewertung` | mehrere Fassungen nicht automatisch benoten (sonst, wenn `setup_bewertung.py` gelaufen ist) |
| `--verlauf [SUCHE]`, `--sortieren neu\|bewertung\|name` | die Songs im Verlauf auflisten, mit SUCHE nur passende (Name, Notiz, Stil, Seed) |
| `--entwurf` | schneller Entwurf ohne Gesang-Synthese im Ordner `Entwurf` |
| `--album N` | Album über Nacht mit N Songs; dazu `--album-stile "Rock,Ballade"`, `--album-texte ORDNER`, `--album-name NAME`, `--album-gleich` (alle in Tonart und Tempo des Stils) |
| `--youtube [TITEL]` | danach MP3, Video, Titelbild und Beschreibung in einen Ordner unter `YouTube` |
| `--ohne-comping`, `--ohne-ausdruck`, `--ohne-gesangskette`, `--ohne-romaji` | Comping, Ausdruck pro Phrase, Studio-Gesangskette oder Romaji abschalten |
| `--ohne-echtes-schlagzeug`, `--ohne-echte-grooves`, `--ohne-bass-leben`, `--ohne-anschlagmuster` | Schlagzeug aus dem SoundFont, eingebaute Grooves, Bass ohne Ghost-Notes, Gitarre immer mit demselben Anschlag |
| `--ohne-vorbild-gruppen` | Gesang, Schlagzeug, Bass und Rest nicht einzeln an die Vorbilder angleichen |
| `--ki-begleitung`, `--ohne-ki-begleitung` | die Begleitung vom Anticipatory Music Transformer schreiben lassen, oder nicht |
| `--ohne-wiederverwenden` | alles neu berechnen, auch wenn Gesang und Spuren vom letzten Mal passen |
| `--system-pruefen [--gruendlich]`, `--fehlerbericht [DATEI]`, `--einrichten TEILE` | System prüfen, Fehlerbericht speichern, Klänge und Modelle laden (`alles` oder z. B. `drums,grooves`) |
| `--aus-verlauf NR` | Einstellungen und Seed eines Songs aus dem Verlauf nehmen (1 = der neueste) |
| `--zip DATEI` | den Song mit allen Spuren als ZIP für eine DAW exportieren |
| `--stimme NAME`, `--duett NAME` | NEUTRINO-Stimme und zweite Stimme fürs Duett für diesen Lauf |
| `--support-stimme NAME` | NEUTRINO-Stimme, die als Support-Modell die Hauptstimme färbt (Versuch, braucht `Run_support_model.bat`) |
| `--engine NAME` | wer singt: `NEUTRINO`, `VOICEVOX`, `DiffSinger` oder `Vorschau` |
| `--diffsinger-stimme ORDNER` | DiffSinger-Stimme: ihr Ordner oder Name (leer = die erste gefundene) |
| `--casting` | Stimmen-Casting: den Refrain mit jeder installierten NEUTRINO-Stimme singen |
| `--eigener-gesang WAV`, `--ohne-ausrichten` | eigene Gesangsspur statt der Hauptstimme, und ob sie an den Noten ausgerichtet wird |
| `--noten-zip DATEI` | die Gesangsnoten als ZIP für Tuning-Tools (MusicXML, UST, MIDI) |
| `--strophe-stil N`, `--refrain-stil N`, `--ohne-sektions-stil` | StyleShift der Strophen und Refrains (Standard −1 und +1), oder überall derselbe |
| `--ohne-haltezeichen`, `--ohne-atemzeichen`, `--ohne-doppelvokale`, `--ohne-englisch`, `--ohne-singbarkeit` | die Vorbereitung der Noten für NEUTRINO einzeln abschalten |
| `--ohne-harmonie-wechsel`, `--ohne-doppel-harmonie`, `--ohne-flaechen`, `--ohne-adlibs` | Begleitstimmen wie bis 1.0 |
| `--ohne-gleiche-fassungen` | Fassungen heller und dunkler singen und nach jeder Abweichung werten |
| `--ohne-echte-atmer`, `--ohne-silben-lautstaerke`, `--ohne-platz`, `--ohne-nachfuehren` | Atmer aus Rauschen, alle Silben gleich laut, Band ohne Platz für den Gesang, Gesang nicht nachgeführt |
| `--ohne-platte`, `--ohne-delay-ducking`, `--ohne-stimmkette`, `--ohne-airwindows` | Hall wie bis 1.0, Delay ohne Ausweichen, eine Kette für alle Stimmen, kein Airwindows |
| `--ohne-telefon`, `--ohne-stutter`, `--ohne-hardtune`, `--ohne-formant`, `--ohne-gesangsswing` | Stil-Effekte einzeln abschalten; der Gesang bleibt gerade, auch wenn die Band swingt |
| `--ohne-psola` | Vibrato und Übergänge mit WORLD statt mit Praat-PSOLA ändern |
| `--ohne-voicevox-dynamik` | VOICEVOX singt gleich laut, Silben und Phrasen werden erst danach lauter und leiser |
| `--ohne-vorbild-gesangsklang` | die Klangkurve des Gesangs nicht an den Gesang der Vorbilder angleichen |
| `--voicevox-stimme ID` | VOICEVOX-Singstimme (die Nummer steht in der App neben dem Namen) |
| `--fassungen N` | NEUTRINO singt N-mal (1 bis 3), die sauberste Fassung zählt |
| `--vibrato X`, `--uebergaenge X` | Vibrato und Übergänge zwischen den Tönen, 0 bis 2 (1 = wie gesungen) |
| `--ohne-atmer`, `--ohne-echo`, `--ohne-chor` | Atmer, Echo auf dem letzten Wort oder Chor im letzten Refrain abschalten |
| `--schlagzeug KLANG` | Schlagzeug aus `soundfont`, `808` oder `909` statt wie der Stil |
| `--ohne-verstaerker`, `--box WAV` | verzerrte Gitarren wie früher aus dem SoundFont, oder über die Box aus dieser Impulsantwort |
| `--ohne-samples` | Orchester aus dem SoundFont statt aus den echten Aufnahmen |
| `--ohne-lofi-klang` | Lo-Fi ohne Knistern und Bandmaschine |
| `--ohne-bewegung` | Mix ohne Anlauf vor dem Refrain, Hall pro Sektion und breitere Refrains |
| `--ohne-veredler` | keine zweite Fassung mit von ACE-Step veredelter Band (sonst, wenn `setup_ace_step.py` gelaufen ist) |
| `--veredler-staerke 0.6` | wie viel ACE-Step am Klang der Band ändert (0.1 bis 0.9, Standard 0.4) |
| `--veredler-klang "TEXT"` | eigene Klangbeschreibung für ACE-Step auf Englisch |
| `--vorbild DATEI` | Vorbild-Song für diesen Lauf, mehrfach möglich |
| `--vom-vorbild` | Tempo, Tonart und Stil der Vorbilder übernehmen |
| `--lautheit LUFS` | Lautheit des Masters, z. B. `-14` für YouTube |
| `--takte SEKTION=N` | Länge einer Sektion in Takten, z. B. `Chorus=8`; mehrfach möglich |
| `--lyric-video [DATEI]` | nach dem Song ein Lyric-Video als MP4 bauen (Standard: `lyric_video.mp4` im Ausgabeordner) |
| `--takt 4/4\|3/4\|6/8` | Takt; im 6/8-Takt zählt `--bpm` die punktierten Viertel |
| `--rezept NAME` | ein neuer Song nach einem Song-Rezept: Stil, Tempo, Tonart, Takt, Ablauf und Beispieltext |
| `--remix STIL` | derselbe Song (mit `--seed` oder `--aus-verlauf`) mit Band, Tempo und Klang eines anderen Stils |
| `--rap-stimme ID`, `--ohne-rap-stimme` | VOICEVOX-Sprechstimme für den Rap-Teil, oder die Gesangsstimme singt ihn |
| `--ohne-eigene-texte` | `[Verse 2]`, `[Chorus 3]` … singen wieder den Text des ersten Vorkommens |
| `--ohne-idol-rufe`, `--ohne-chops`, `--ohne-ritardando` | keine Rufe im Refrain, keine Vocal Chops im Drop, Ballade bis zum Schluss im Tempo |
| `--oeffnen NR`, `--ohne-projekt` | einen Song aus dem Verlauf wieder öffnen (sein Gesang bleibt), oder den Gesang neuer Songs nicht aufheben |
| `--ohne-true-peak`, `--ohne-offvocal`, `--ohne-tags` | Limiter nur auf die Samples, keine MP3s ohne Gesang und nur mit Gesang, MP3 ohne Tags |
| `--ohne-band-samples` | Flügel, Bass und Gitarre aus dem SoundFont statt aus den Aufnahmen |
| `--video-hintergrund BILD`, `--ohne-stilfarben` | eigenes Hintergrundbild fürs Lyric-Video, oder dunkel mit pinkem Text wie bis 1.1 |
| `--ohne-tonhoehe-glaetten`, `--ohne-haerte-zaehmen`, `--ohne-verzierungen`, `--ohne-gesang-im-groove`, `--ohne-diffsinger-ausdruck`, `--ohne-partikel` | Gesang 1.3 einzeln abschalten: schiefe Töne bleiben, keine Zähmung schriller Stellen, keine Verzierungen, Gesang genau auf dem Schlag, DiffSinger wie das Varianz-Modell, は/へ/を wie geschrieben |
| `--gruppe 3\|4`, `--sprechen-klang Hall\|Telefon\|trocken` | drei oder vier NEUTRINO-Stimmen singen als Gruppe (0 = aus); wie die Sektion „Sprechen“ klingt |
| `--ohne-beste-melodie`, `--ohne-auftakte`, `--ohne-spannungstoene`, `--ohne-hoehepunkt`, `--ohne-triolen`, `--ohne-akkord-wuerze`, `--ohne-intro-riff` | Melodie 1.3 einzeln abschalten |
| `--ki-melodie`, `--ohne-ki-melodie` | das Modell der KI-Begleitung schlägt Refrain-Melodien vor (Versuch), oder nicht |
| `--ohne-kime`, `--ohne-band-groove`, `--ohne-bass-laeufe`, `--ohne-laeufe`, `--ohne-anison-grooves`, `--ohne-aufbau` | Band 1.3 einzeln abschalten |
| `--ohne-surge-klaenge`, `--ohne-verstaerker-modelle`, `--ohne-druck` | eigene Synths statt Surge XT, eingebauter Verzerrer statt Verstärker-Modell, Mix ohne Parallel-, Bus- und Mehrband-Kompression |
| `-v` | alle Details ausgeben |

Die fertigen Dateien landen in `Songs` im Datenordner (oder im Ordner aus den Einstellungen): `final_song.mp3`, `final_mix.wav`, `final_song_offvocal.mp3` (ohne Gesang), `final_song_acappella.mp3` (nur Gesang), die einzelnen Spuren als WAV und MIDI, `vocals.xml` für NEUTRINO, die `.ust`-Dateien für OpenUtau und `liedtext.json` mit der Zeit jeder Silbe (für das Mitlesen und das Lyric-Video).
