# Fehlerbehebung

Erst **Hilfe › System prüfen** drücken: Die Liste zeigt, welcher Baustein nicht läuft, und meist steht der Grund
gleich dabei. Hilft nichts von unten, **Hilfe › Fehlerbericht speichern**: Das ZIP enthält Protokoll, Einstellungen
und Systeminfo (keine Songs) und landet in `Dokumente\Vloid Songs\Fehlerberichte`. Schick es mit, wenn du fragst.

## Die App startet nicht

- **Das Fenster geht nicht auf.** Es braucht die Microsoft-Edge-WebView2-Laufzeit, die auf Windows 10 und 11 meist
  schon da ist. Sonst die App im Browser öffnen: im Programmordner in der Adresszeile des Explorers `cmd` eingeben
  und `"Vloid Songs starten.bat" --browser` ausführen. Die Oberfläche ist dann unter http://127.0.0.1:8090.
- **„Failed to inspect Python interpreter“ mit „os error 448“ oder „nicht vertrauenswürdiger Bereitstellungspunkt“.**
  Windows sperrt die Python-Verknüpfungen, die uv in `AppData\Roaming\uv\python` anlegt. Die Setup.exe ab 1.0.1
  bringt ihr eigenes Python mit und braucht diesen Ordner nicht; einfach die neueste Setup.exe installieren.
- **Das Laden der Bibliotheken bleibt stehen** (die Zahlen hinter scipy, llvmlite oder torch ändern sich nicht mehr).
  Ab 1.0.2 lädt uv ein Paket nach dem anderen, das hilft meist. Sonst das Fenster schließen und die Setup.exe noch
  einmal starten; was schon geladen ist, lädt sie nicht neu.
- **Ein schwarzes Fenster bleibt mit einer Meldung stehen.** Die letzte Zeile sagt, was fehlt. „uv fehlt“: die
  Setup.exe noch einmal ausführen (sie bringt uv mit). Steht dort ein Python-Fehler, einen Fehlerbericht schicken.
- **Nach einem Absturz** bietet die App beim nächsten Start an, den Song fertig zu machen („Weitermachen“). Wer das
  nicht will, drückt „Verwerfen“.

## Gesang

- **Es singt die Roboter-Vorschaustimme statt NEUTRINO.** NEUTRINO ist nicht gefunden. In Einrichten den Ordner
  wählen, in dem `bin` und `model` liegen (nicht den Ordner darüber). System prüfen zeigt danach die Version.
- **NEUTRINO singt falsche Silben.** Im Tab Text steht rechts, was gesungen wird. Liest es ein Kanji falsch, die
  Lesung in eckigen Klammern dahinter schreiben: `君[きみ]`. Wird eine Romaji-Zeile nicht japanisch gesungen, ist
  wohl ein englisches Wort darin; dann die Zeile in Kana schreiben.
- **Der Gesang ist zu leise oder zu laut.** Tab Band, Kanal Gesang. Mit Vorbild-Songs bestimmen die Vorbilder die
  Gesangslautstärke; im Tab Song unter den Vorbildern „Gesangslautstärke“ und „Mix pro Instrument“ ausschalten.
- **Ein Song dauert lange.** NEUTRINO braucht pro Fassung so lange wie für eine. Weniger Fassungen (Tab Gesang),
  zum Ausprobieren „Entwurf“ nehmen. Klang-Veredler und KI-Begleitung brauchen ohne NVIDIA-Grafikkarte sehr lange;
  unter Pfade ausschalten.
- **Die Stimme klingt rau, verwaschen oder blechern.** Zuerst die NEUTRINO-Ausgabe ansehen (Hilfe › Einrichten):
  Vor 3.2.2 singt NEUTRINO mit dem alten Vocoder, der deutlich rauer klingt. Die neue Ausgabe gibt es kostenlos auf
  studio-neutrino.com; entpacken, die Stimmen in `model` legen und in Einrichten den neuen Ordner wählen. Dann ins
  Protokoll sehen: Steht dort „singt laut NEUTRINO am schönsten bei …“, ist das Tempo für die Stimme zu schnell oder
  zu langsam (MERROW etwa 80 bis 140 BPM); das Tempo ändern oder eine der genannten Stimmen nehmen. Tab Gesang
  „Sanfte Nachbearbeitung“ und „Weichere Gesangskette“ sollten an sein.
- **Strophe und Refrain klingen gleich**, im Protokoll steht ein Hinweis zu StyleShift. NEUTRINO bis 3.2.1 und die
  Ausgabe mit Tuning-Tool (.ex) kennen keinen StyleShift; dann singt die App den Song am Stück. Für StyleShift pro
  Sektion NEUTRINO 3.2.2 oder neuer installieren.
- **Alle Songs klingen ähnlich.** Seit 1.4 hat jeder Stil eigene Akkorde, Melodie, Besetzung und Klang, und jeder Song
  würfelt eigene Klänge, Grooves, Intro und Schluss. Sind die Schalter dafür an (Tab Song, Band, Mix)? Mit festem
  Seed klingt jeder Song gleich; im Tab Song das Seed-Feld leeren.
- **Ein Effekt stört** (Telefon, Stottern, harter Tune, Flächen, Ad-libs …). Jeder hat einen Schalter im Tab Gesang.
- **DiffSinger singt nicht, es singt NEUTRINO.** Im Protokoll steht warum. Meist fehlt der Vocoder (z. B. nsf_hifigan):
  die `.oudep`-Datei, die bei der Stimme verlinkt ist, in OpenUtau ziehen; sie landet in `Dependencies`. Oder im Tab
  Gesang den Ordner der Stimme wählen, in dem `dsconfig.yaml` liegt.
- **Die Support-Stimme ändert nichts.** Sie braucht eine NEUTRINO-Ausgabe mit `Run_support_model.bat`; ohne singt die
  Hauptstimme allein, und das Protokoll sagt es.
- **Die Gruppe singt allein.** Tab Gesang › Gruppe braucht so viele Stimmen in NEUTRINO, wie du gewählt hast (drei
  oder vier); fehlen welche, singt die Hauptstimme, und das Protokoll nennt die gefundenen Stimmen.
- **Die Sektion „Sprechen“ bleibt stumm.** Sie spricht mit VOICEVOX; läuft es nicht, fällt die Zeile weg. VOICEVOX
  starten und System prüfen ansehen. Über der Zeile im Text muss `[Sprechen]` stehen.

## Klang, MP3 und Video

- **Keine MP3, kein Video.** Dafür braucht es ffmpeg. In PowerShell `winget install Gyan.FFmpeg`, dann die App neu
  starten. Bis dahin entsteht der Song als `final_mix.wav`, und „Fertig für YouTube“ macht Bild und Beschreibung.
- **Die Instrumente klingen dünn.** In Einrichten „FluidSynth“ und „Bessere Klänge“ laden; unter Pfade müssen die
  Schalter dafür an sein, und das Feld SoundFont muss leer sein (ein eigener SoundFont schaltet sie ab).
- **Das echte Schlagzeug spielt nicht.** Es gilt für akustische Kits; 808 und 909 (z. B. bei Future Bass) bleiben
  Drum-Machines. Sonst unter Pfade den Schalter prüfen und System prüfen ansehen.
- **Surge-Klänge oder Verstärker klingen wie vorher.** Sie brauchen Surge XT und die Verstärker-Modelle aus
  Einrichten. Fehlen sie oder lädt ein Modell nicht, spielt die App ihre eigenen Synths und Verzerrer, und das
  Protokoll sagt warum. Einrichten noch einmal starten lädt nach, was fehlt.
- **Ein Song mit E-Gitarren rendert länger.** Die Verstärker-Modelle rechnen jede verzerrte Gitarre einzeln durch.
  Zum Ausprobieren „Entwurf“ nehmen (dort sind sie aus) oder im Tab Band „Verstärker“ ausschalten.
- **Mix pro Instrument tut nichts.** Es braucht Demucs (Einrichten, „Mix wie die Vorbilder“) und mindestens ein
  angehaktes Vorbild. Das erste Mal zerlegt Demucs jedes Vorbild, danach geht es schnell. Im Protokoll steht eine Zeile
  „Mix wie die Vorbilder“ mit dem, was es geändert hat.
- **Das Musikvideo dauert lange.** Jedes Bild wird einzeln gezeichnet, bei einem Song von vier Minuten sind das
  einige Tausend. Zum Anschauen reicht die „Video-Vorschau (10 s)“ unter dem Player; im Tab Video lassen sich
  einzelne Teile abschalten, mit „Musikvideo“ aus ist es das schnelle Lyric-Video wie bis 1.4.
- **Im Video passt etwas nicht zum Song.** Unter „Szene“ eine andere für den Stil wählen oder die Bilder aus dem
  Text ausschalten. Ein Song von vor 1.5 hat keine `songkarte.json`; dann kennt das Video keine Sektionen und
  Akkorde, und das Bild folgt nur dem Klang des Mixes.
  Ihn einmal neu erzeugen (gleicher Seed) schreibt sie.
- **Keine KI-Bilder im Video.** Sie brauchen „KI-Bilder fürs Video“ aus Einrichten. Ohne NVIDIA-Grafikkarte malt
  der Prozessor, das dauert einige Minuten pro Song. Läuft das Bildmodell nicht, nimmt das Video die gezeichnete
  Szene; die Ausgabe steht in `tools\bilder\letzter_lauf.log` im Programmordner.
- **Kein Hör-Check unter dem Player.** Er braucht „Hör-Check für den Text“ aus Einrichten und einen Song mit
  Gesang und Text. Die Ausgabe der Spracherkennung steht in `tools\hoercheck\letzter_lauf.log`. Meldet er
  undeutliche Zeilen, steht in `hoer_check.txt` im Songordner, was er gehört hat, und welche Wörter du in
  Lesungen.txt prüfen solltest.

## Einrichten und Updates

- **Ein Download bricht ab.** Einfach noch einmal „Ausgewählte einrichten“; was schon da ist, wird übersprungen.
  Oben steht, wie viel Platz frei ist; Klang-Veredler und KI-Begleitung brauchen viele GB.
- **Ein Modell (Bewertung, Demucs, KI-Begleitung, Veredler, KI-Bilder, Hör-Check) startet nicht.** Beim ersten Mal lädt es noch Dateien
  nach; ein zweiter Versuch hilft oft. Die ganze Ausgabe steht bei der KI-Begleitung in
  `tools\begleitung\letzter_lauf.log` und beim Veredler in `tools\ace-step\letzter_lauf.log` im Programmordner.
- **Im Protokoll steht „[Errno 22] Invalid argument“ bei einer Datei in `tools\…\huggingface`.** Bis 1.2.1 lagen
  die Modelle als Verknüpfungen dort, und manche Windows-PCs öffnen sie nicht. Ab 1.2.2 stellt die App sie beim
  nächsten Start des Modells auf echte Dateien um; einfach die neueste Setup.exe installieren.
- **System prüfen: „In der Umgebung der Bewertung fehlt das Paket …“.** Unter Hilfe › Einrichten ist die
  automatische Bewertung dann wieder angehakt; „Ausgewählte einrichten“ lädt nur das fehlende Paket nach.
- **Das Update geht nicht.** Die App braucht dafür Internet. Sonst die neue Setup.exe von
  https://github.com/StrikerLUL/Vloid_songs/releases laden und starten; deine Daten bleiben.
- **Meine alten Songs fehlen.** Sie liegen noch im alten Ordner. In Einrichten den alten Ordner wählen und
  „Übernehmen“ drücken. Hilfe › Datenordner öffnen zeigt, wo die App jetzt speichert.

## Alles zurück auf Anfang

Die App schließen und `Einstellungen.json` in `Dokumente\Vloid Songs` umbenennen. Beim nächsten Start sind alle
Einstellungen wie nach der Installation; Songs, Vorlagen und Vorbilder bleiben.
