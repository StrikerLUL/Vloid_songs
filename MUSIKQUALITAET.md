# Musikalischer Zusammenhang

Neue Songs verwenden standardmäßig `musical_coherence` (Profi › Melodie) und `selective_vocals`
(Profi › Stimme). Alte Verlaufseinträge ohne diese Felder verwenden beim Wiederöffnen die bisherigen Verfahren.

## Die zwölf Verbesserungen

1. Die Melodiebewertung berücksichtigt die Akkorde über die gesamte Notendauer, Reibungen zum Bassgrundton und
   die Auflösung von Spannungstönen. Statistische Melodiemerkmale zählen weiter.
2. Bei Akkordwechseln werden ungewollte lange Reibungen korrigiert. Muss die Tonhöhe wechseln, wird der Vokal
   gebunden. Kurze diatonische Durchgänge, absichtliche Vorhalte und Klangfarben bleiben möglich.
3. Kandidaten werden vor der Auswahl auf Harmonie und Singbarkeit geprüft. Die Gewinner werden danach nicht
   global umgeschrieben. Ein höherer langer Zielton im letzten Refrain muss seine lokale Bewertung verbessern;
   der letzte Ton muss nicht der höchste des Songs sein.
4. Die Tonwahl sucht mehrere mögliche Verläufe einer ganzen Phrase mit Blick auf den Schlussakkord.
   Vorhandene Motive und Refrainwiederholungen bleiben erhalten.
5. Zeilen- und Wortgrenzen beeinflussen die Phrasenaufteilung. Kurze Texte werden nicht automatisch vervielfacht,
   nur um die ganze Sektion mit Gesang zu füllen.
6. Hauptbegleitung, Hintergrund und Antworten erhalten unterschiedliche Rollen. Läufe, Glocken und Gegenstimmen
   machen während gesungener Phrasen Platz und können in den Pausen antworten.
7. Bassfiguren entstehen aus den tatsächlich verwendeten Kicks und Akkordanfängen, einschließlich des Timings
   echter Grooves. Stiltypische Läufe und Feinheiten kommen anschließend hinzu.
8. Programme und Synth-Stimmen werden als zusammenpassendes Klangset gewählt. Alle vorhandenen Stile haben
   mindestens ein Set. Einfache Ersatzklänge werden unter dem Player angezeigt, auch bei wiederverwendeten WAVs.
9. Gute gesungene Tonverläufe bleiben erhalten. Stabile Abweichungen ab 35 Cent werden gezielt korrigiert;
   automatische Verzierungen sind auf seltene lange Phrasenschlüsse begrenzt. Bewusst eingestellte Vibrato- und
   Übergangsänderungen bleiben wirksam. Kleine Formantverschiebungen, Telefon und Stutter entfallen im natürlichen
   Modus außerhalb von Hyperpop. Stilprägender harter Tune bleibt über seinen Schalter verfügbar.
10. Die automatische Audiobewertung hört Anfang, mittlere Teile, Schluss und einen Energieübergang getrennt.
    Die Gesamtnote gewichtet zusätzlich den schwächsten Abschnitt. Fehlende Abschnittsurteile ergeben keine
    vollständige Bewertung. Das vorhandene blinde Hör-Duell bleibt für persönliche A/B-Vergleiche verfügbar.
11. Melodie-Daumen speichern auch Dichte, Umfang, Schritt- und Wiederholungsanteil, Anfangsrhythmus,
    Anfangsintervalle und Kontur. Diese transpositionsunabhängigen Merkmale beeinflussen die Kandidatenauswahl.
    Der Geschmack wird für reproduzierbare Songs mitgespeichert.
12. In der einfachen Ansicht steht „1. Refrain auswählen“. Drei kurze Vorschauen verwenden eine schlichte
    Begleitung. „nehmen“ erzeugt den vollständigen Song mit diesem Seed, Variantenstand und Geschmack.

Die Klangsets sind musikalische Vorgaben. Ihre technische Prüfung ersetzt keine Hörabnahme mit den installierten
Instrumenten. J-Pop Energy, Ballade, City Pop und Rock dienen zunächst als feste Vergleichsstile;
neue Stile wurden für diese Änderung nicht hinzugefügt.

## Prüfen und vergleichen

```powershell
uv run pytest
uv run ruff check .
uv run python scripts/benchmark_music.py --seeds 5 --output vergleich.json
```

Der Vergleich verwendet vier Stile und fünf Seeds, jeweils mit bisheriger und gemeinsamer Komposition. Er misst
nachträglich veränderte Gewinner, überlappende Gesangsnoten und die Harmoniewertung über vollständige Notendauern.
Die Messwerte sind technische Regressionen und ersetzen keinen Hörvergleich.

Für hörbare, reproduzierbare Melodie-Vorschauen und einen Vergleich gegen einen gespeicherten Bericht:

```powershell
uv run python scripts/benchmark_music.py --seeds 2 --audio-dir output/vergleich-a --output output/vergleich-a.json
uv run python scripts/benchmark_music.py --seeds 2 --audio-dir output/vergleich-b --baseline output/vergleich-a.json --output output/vergleich-b.json
```

Die WAV-Dateien verwenden einen festen Synth-Klang und vergleichen die Melodie, nicht die fertige Produktion.
Der Bericht enthält RMS, Peak, Clipping-Anteil, spektralen Schwerpunkt und Audio-Prüfsummen sowie numerische
Abweichungen zur Vergleichsfassung. Stile, Seeds und Audio-Optionen müssen übereinstimmen. Gleiche Umgebung und
Abhängigkeiten verwenden; deren Versionen stehen im Bericht. Die endgültige Stimme und Band weiter separat hören.

Die Kernregressionen laufen auch ohne Audio-Modelle:

```powershell
python vocaloid_generator/tests/test_musical_coherence.py
```

Für den Hörvergleich denselben Text, Stil und Seed verwenden. Erst die Melodie mit schlichter Begleitung,
anschließend Stimme und vollständige Band prüfen. Das Hör-Duell vergleicht einzelne Funktionen bei gleicher
Lautheit. Unterschiede bei SoundFonts, Samples und Gesangsengines bei der Beurteilung festhalten.

Bei NEUTRINO-Atemzeichen bleibt ein direkt anschließender gehaltener Vokal mit seiner Silbe verbunden:
Ein fälliges Atemzeichen wird bis zu einer geeigneten späteren Stelle zurückgestellt. Das verändert weder
die Gesamtdauer der Noten noch die Ausgabe bei ausgeschalteten Atemzeichen. Eine Hörabnahme mit mehreren
Stimmen und Tempi steht noch aus.
Sind mehrere Wortanfänge im Text bekannt, wird ein fälliger Atmer außerdem bis zur nächsten geeigneten
Wortgrenze zurückgestellt. Fehlen ausreichende Wortgrenzen, bleibt das frühere Verhalten erhalten.
Für NEUTRINO lässt sich der Abstand der Atemzeichen mit `--atem-abstand` zwischen 0.5 und 2 einstellen;
1 ist die bisherige Vorgabe. Die Option verändert nicht die Notendauer und ist bei ausgeschalteten Atemzeichen
wirkungslos. Längere Phrasen können mehr Speicher benötigen.
Die Lautstärke hörbarer Atemgeräusche lässt sich mit `--atmer-lautstaerke` von 0 bis 2 skalieren; 1 entspricht
der bisherigen Lautstärke. Diese Einstellung betrifft aufgenommene und künstliche Atmer, nicht die Atemzeichen
der Partitur. Gegenphasige Stereostimmen werden bei der Pegelmessung nicht als Stille behandelt.

Die Melodiebewertung im gemeinsamen Kompositionsmodus zählt Tonwiederholungen und die Fortsetzung von
Sprüngen nur innerhalb derselben Phrase. Gehaltene Vokale werden beim Erkennen von Pausen mitgezählt.
Einzelne lange oder betonte Phrasenhöhepunkte erhalten eine schwache Bewertung ihrer Vorbereitung; die
neue Wahl darf die Harmoniewertung gegenüber der bisherigen Kandidatenauswahl nicht verschlechtern.
Beim Hör-Duell wird das gemeinsame Lautheitsziel für beide Fassungen abgesenkt, wenn eine Spitze sonst
übersteuern würde. Auch diese Änderungen brauchen einen persönlichen Hörvergleich.

Bei langen Begleitstimmen über einem Akkordwechsel bevorzugt der gemeinsame Kompositionsmodus einen
passenden gemeinsamen Akkordton auf derselben Seite der Hauptstimme, sofern er in der Stimmlage liegt.
Ohne geeigneten Ton bleibt die bisherige Wahl erhalten. Bei schnellen NEUTRINO-Silben verhindern bekannte
Wortgrenzen außerdem, dass zwei unterschiedliche Wörter auf einem Ton zusammengezogen werden.
Große Sprünge langer Begleitnoten können durch einen passenden Akkordton verkleinert werden; nach einer
Phrasenpause ist ein neuer Einsatz möglich. Zwölf feste Fälle (vier Stile, drei Seeds) zeigten dabei keine
Änderung; ein hörbarer Vorteil für typische Songs ist noch nicht belegt.
Das Arrangement berücksichtigt bei einem Sektionswechsel auch Gesangstöne, die im vorherigen Abschnitt
begonnen haben und noch in den neuen hineinreichen. Ebenso können Instrumententöne, die vor dem Übergang
begannen, vor dem Einsatz einer neuen Gesangsphrase enden, ohne ihren Anfang abzuschneiden.
Die Mix-Automatik misst die Energie beider Stereokanäle getrennt, damit gegenphasige Anteile nicht
fälschlich als Stille gelten. Das betrifft Platz für die Stimme und das Nachführen der Gesangslautstärke.
Sehr kurze Gesangseinsätze nach langer Stille lassen die Band nicht mehr bereits während der Stille leiser
werden; stille Frequenzbänder zählen nicht als Gesang.
Das Gesangs-Delay bleibt bei Stille auch direkt am Anfang unverändert. Sehr kurze Einsätze in langen Pausen
werden für die zeitweilige Delay-Absenkung erkannt; nach dem Einsatz kehrt das Delay sanft zurück.
Im Stimmen-Casting zeigt der Hinweis am Wiedergabeknopf den Tonumfang der Vorschau und den hinterlegten
Bereich der Stimme; lange Töne nahe dessen oberem Rand werden genannt. Für unbekannte Stimmen wird keine
Lage behauptet. Bei Bedarf wird eine benachbarte Tonart als rechnerischer Ausgangspunkt vorgeschlagen;
beim Neuerzeugen kann sich die Melodie ändern. Die Angabe ersetzt keine persönliche Hörprobe.
Wenn der Aufbau die erste Strophe bewusst schlank beginnen lässt, enden gehaltene Töne der zunächst
schweigenden Bandinstrumente am Übergang aus dem Intro.
Beginnen Klavier und Gitarre gleichzeitig, setzt zunächst nur das ausgewählte Instrument die Strophe fort;
das andere pausiert bis zum Bandeinsatz. Auch dessen gehaltene Intro-Töne enden am Übergang.
Die Refrainauswahl gleicht ihre Vorschauen auf ein gemeinsames integriertes Lautheitsziel ab, ohne die
lauteste Variante weiter anzuheben. Text, Seed, Variationen und Geschmack werden weiterhin für die
Auswahl übernommen. Die Reihenfolge der Vorschaustücke wird für die Auswahl zufällig gemischt.
In der einfachen Ansicht gilt die gewählte Qualitätsstufe bereits für die Komposition der Vorschau. Werden
Einstellungen nach dem Erstellen verändert, verlangt die Auswahl neue Vorschauen, damit der gewählte Refrain
mit den gehörten Einstellungen erzeugt wird.
Beim gemeinsamen Bass-Groove zählt bei gleichzeitigen Kick-Schlägen der stärkste Anschlag; seine Stärke
beeinflusst die Bassbetonung. Das ist deterministisch und lässt Akkordankerpunkte bestehen.
Spannungstöne werden auch dann als aufgelöst erkannt, wenn der Auflösungston bereits zum nächsten Akkord
gehört. Bei Noten über mehrere Akkorde schützt diese Auflösung nur den unmittelbar vorangehenden Abschnitt;
frühere unpassende Abschnitte werden weiterhin geprüft. Bei chromatischen Akkorden bleiben alle tatsächlichen
Akkordtöne in der lokalen Tonskala enthalten.
Bei der Phrasensuche werden lange Töne bereits anhand aller überstrichenen Akkorde bewertet; die zusätzliche
Gewichtung ist begrenzt, gilt nur bei tatsächlichen Akkordwechseln und verbietet Spannungstöne nicht. Ein
synthetischer Hörvergleich lässt sich mit den beschriebenen Werkzeugen erstellen.

### Eigene Vorher-Nachher-Fassungen blind hören

Für Vergleiche zwischen Programmständen vier feste Fälle verwenden: J-Pop Energy (160 BPM), Ballade
(80 BPM), City Pop (110 BPM) und Rock (140 BPM), jeweils Seed 0, A-Moll und denselben Text. Für jeden
Fall beide Fassungen mit denselben vollständigen Einstellungen, derselben Stimme, denselben Modellen,
SoundFonts und Samples erzeugen; nur die untersuchte Änderung darf abweichen. Einstellungen und
Programmstand im Hörprotokoll festhalten. Falls sich eine Abhängigkeit ändert, den Vergleich kennzeichnen.

Für einen Fall die beiden fertigen WAV-Dateien mit gleicher Länge, Samplerate und Kanalzahl vorbereiten:

```powershell
.venv\Scripts\python.exe scripts\hoervergleich.py vorher.wav nachher.wav output\hoervergleich-jpop
```

Der Ausgabeordner darf noch nicht existieren. Das Werkzeug misst die integrierte Lautheit, gleicht die
Fassungen auf ein gemeinsames Ziel ab und reduziert bei Bedarf beide gemeinsam, um Übersteuerung zu vermeiden.
Es erstellt zufällig zugeordnete `A.wav` und `B.wav`, ein `hoerprotokoll.md` und eine `aufloesung.json`.
Erst blind hören und Gesang, Melodie, Harmonie, Arrangement und Mix getrennt notieren; danach die Auflösung
öffnen. Die Quelldateien bleiben erhalten. Integrierte Lautheit garantiert keine identische Lautheit jeder
einzelnen Passage. Unterschiedliche Länge oder Stille werden abgewiesen und müssen vorher geklärt werden.

Die Beispiele müssen mit der tatsächlich verwendeten Windows-Umgebung und den gewünschten Stimmen gerendert
werden. Ein ausgefülltes Protokoll dokumentiert persönliche Hörurteile; technische Messwerte oder das
Erstellen des Vergleichs allein beweisen noch keine hörbare Verbesserung.

Ein kurzer vollständiger Vergleichssong mit festem Seed, Standardtext und lokaler NEUTRINO-Stimme entsteht
mit `.venv\Scripts\python.exe scripts\vergleichssong.py Ballade output\mein-vergleich`. Der Ausgabeordner
muss neu sein. Der Lauf isoliert persönliche App-Daten und verwendet die Grund-SoundFont und vorhandene
eingebaute Klänge. Für eine zweite Fassung, bei der nur die zusätzliche Phrasenbogen-Bewertung deaktiviert
ist, einen anderen Ausgabeordner und zusätzlich `--ohne-bogen` verwenden. Die Programmeinstellungen,
die Prüfmethode und der tatsächlich verwendete Gesang werden im Ausgabeordner gespeichert. Audioengines
können auch bei gleichen Einstellungen variieren; der Vergleich belegt daher keine exakte Kausalität.

Kommandozeile: `--ohne-zusammenhang` verwendet die bisherige Komposition;
`--ohne-natuerliche-stimme` verwendet die bisherige Gesangsnachbearbeitung. Beide Schalter werden gespeichert.
