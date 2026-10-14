# Was ist neu

Jede Version hat hier einen Abschnitt. Die App zeigt ihn einmal nach einem Update (Hilfe › Was ist neu).

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
