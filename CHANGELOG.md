# Was ist neu

Jede Version hat hier einen Abschnitt. Die App zeigt ihn einmal nach einem Update (Hilfe › Was ist neu).

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
