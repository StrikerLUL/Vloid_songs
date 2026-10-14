# Erste Schritte

In fünf Schritten zum ersten Song. Alles Weitere steht darunter; wenn etwas nicht klappt, hilft
**Hilfe › Fehlerbehebung**.

## 1. Installieren

`VloidSongs-Setup-1.0.2.exe` starten. Sie braucht keine Adminrechte, legt „Vloid Songs“ ins Startmenü (auf Wunsch
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

- Tab **Song**: Stil, Tempo und Tonart wählen (oder eine eigene Vorlage laden).
- Tab **Text**: den Liedtext eintragen, pro Abschnitt eine Überschrift wie `[Verse]` oder `[Chorus]`. Japanisch mit
  Kanji und Kana geht, Romaji auch (`kimi no koe`), sogar gemischt.
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
(Lyric-Video vor dem Titelbild, ohne Text nur das Bild), `Titelbild.png` in 1280×720 und `Beschreibung.txt` mit Stil,
Tempo, Tonart und dem, was die Stimme verlangt (bei NEUTRINO den Namen der Stimme). Der Titel ist der Name aus dem
Verlauf, sonst Stil und Seed. Ohne ffmpeg gibt es Bild und Beschreibung trotzdem.

**Liedtext in Romaji.** Eine Zeile ganz in Romaji wird japanisch gesungen (`kimi no koe` → きみ の こえ). Ist ein
englisches Wort darin (`love`, `baby`), bleibt die Zeile, wie sie ist. Neben Kana und Kanji wird jedes Romaji-Wort
umgewandelt. Rechts im Tab Text siehst du sofort, welche Silben gesungen werden. Schalter: Tab Text.

**Gesang.** NEUTRINO singt mehrere Fassungen (Tab Gesang, „Fassungen“), und die App setzt jede Phrase aus der
saubersten zusammen (Comping). Die Studio-Kette gibt der Stimme leichte Bandsättigung, Hall und Delay je Sektion
(Strophe trockener, Refrain weiter) und im Refrain eine echte Doppelung aus der zweiten Fassung. Mit „Ausdruck pro
Phrase“ wird jede Zeile zu ihrem höchsten Ton hin lauter und heller, Strophen bleiben leiser als Refrains.

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

## Jede neue Funktion lässt sich abschalten

| Funktion | Wo |
| --- | --- |
| Romaji japanisch singen | Tab Text |
| Comping, Studio-Kette, Ausdruck pro Phrase | Tab Gesang |
| Bass mit Ghost-Notes, Gitarren-Anschlag | Tab Band |
| Echtes Schlagzeug, echte Grooves, Bewertung, Veredler, KI-Begleitung | Tab Pfade |
| Mix pro Instrument (Demucs) und alles andere von den Vorbildern | Tab Song, unter den Vorbildern |
| Verschiedene Tonarten im Album | im Album-Fenster |
| Wiederverwenden, Protokoll, Update-Suche, Assistent beim Start, Größe des Verlaufs, Datenordner | Pfade › App |

## Wo was liegt

| Ordner in Dokumente\Vloid Songs | Inhalt |
| --- | --- |
| `Songs` | der letzte Song mit allen Spuren; darin `verlauf`, `Entwurf`, `Alben` und `YouTube` |
| `Vorlagen`, `Vorbilder`, `Motive` | deine Vorlagen, Lieblingssongs zum Anhaken und MIDI-Dateien für die Melodie |
| `Protokolle` | was die App getan hat; gehört in jeden Fehlerbericht |
| `Fehlerberichte` | ZIPs von „Fehlerbericht speichern“ |
| `Einstellungen.json` | alle Einstellungen |

Klänge und Modelle liegen im Programmordner unter `tools`, weil sie groß sind und zur App gehören.
