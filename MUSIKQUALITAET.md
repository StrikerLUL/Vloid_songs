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

Die Kernregressionen laufen auch ohne Audio-Modelle:

```powershell
python vocaloid_generator/tests/test_musical_coherence.py
```

Für den Hörvergleich denselben Text, Stil und Seed verwenden. Erst die Melodie mit schlichter Begleitung,
anschließend Stimme und vollständige Band prüfen. Das Hör-Duell vergleicht einzelne Funktionen bei gleicher
Lautheit. Unterschiede bei SoundFonts, Samples und Gesangsengines bei der Beurteilung festhalten.

Kommandozeile: `--ohne-zusammenhang` verwendet die bisherige Komposition;
`--ohne-natuerliche-stimme` verwendet die bisherige Gesangsnachbearbeitung. Beide Schalter werden gespeichert.
