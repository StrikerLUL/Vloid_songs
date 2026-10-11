# Vocaloid Song Generator

Erzeugt komplette Vocaloid-Songs auf Knopfdruck: Akkorde, Bass, Schlagzeug, Melodie und Begleitung, Gesang mit NEUTRINO oder VOICEVOX (oder einer lokalen Vorschau-Stimme), Mix mit Kompressor und Limiter und am Ende eine fertige MP3.

Läuft unter Windows.

## Installation

Empfohlen mit [uv](https://docs.astral.sh/uv/). Im Projektordner (dort, wo `pyproject.toml` liegt) ausführen:

```powershell
winget install astral-sh.uv
uv sync
```

`uv sync` legt im Projektordner einen eigenen Ordner `.venv` mit allen Bibliotheken an. Die Python-Installation auf dem Rechner und andere Projekte bleiben unberührt.

Ohne uv geht es auch mit pip (Python 3.10 bis 3.12). Auch dann in einer eigenen Umgebung installieren, damit pip keine Versionen anderer Projekte ändert:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r vocaloid_generator\requirements.txt
python vocaloid_generator\app.py
```

### Gesang mit NEUTRINO

1. NEUTRINO (`NEUTRINO-windows-v3.1`) und die Stimme MERROW (`めろう（NEUTRINO-Library）-v3.1`) herunterladen und beide Ordner in den Projektordner legen.
2. `python setup_neutrino.py` kopiert die Stimme an die richtige Stelle.

Die App ruft NEUTRINO so auf, wie es die `Run.bat` der installierten Version vorgibt, und erkennt dabei v2 (mit `NSF.exe`) und v3 (schreibt die WAV selbst). Neuere Versionen von [studio-neutrino.com](https://studio-neutrino.com/) klingen besser (ab v3.2.2 mit neuem Vocoder) und funktionieren genauso.

Damit der Gesang natürlich klingt, bereitet die App die Noten für NEUTRINO vor: ein Takt Vorlauf, kurze Pausen innerhalb einer Phrase werden an die Note davor gebunden, und die Melodie bleibt im Tonumfang der gewählten Stimme. Männliche Stimmen (NAKUMO, SOMA, RUNO) singen eine Oktave tiefer. Im Refrain singt NEUTRINO eine zweite Stimme dazu, der Hauptgesang wird gedoppelt, und ein De-Esser nimmt scharfe S-Laute zurück.

Im Tab „Gesang“ wählst du die Stimme, ob im Refrain eine zweite Stimme mitsingt, und die Klangfarbe (StyleShift): plus klingt heller, minus dunkler. StyleShift braucht eine NEUTRINO-Version, die die Option `-k` kennt; sonst singt NEUTRINO ohne. Zu Beginn jedes Songs steht im Protokoll, welche NEUTRINO-Version und welche Stimmen gefunden wurden.

Schlägt NEUTRINO fehl, steht die Meldung im Protokoll, und die App versucht es mit VOICEVOX; läuft das auch nicht, nimmt sie die lokale Vorschau-Stimme (Windows-Sprachausgabe plus Tonhöhen-Korrektur).

**Fassungen:** Unter „Fassungen“ 2 oder 3 wählen (oder `--fassungen 3`). NEUTRINO singt den Song dann mehrmals, mit StyleShift eine Stufe heller und eine dunkler, und die App nimmt die Fassung, die die Töne am besten trifft und keine Aussetzer hat. Im Protokoll steht für jede Fassung, wie viele Cent sie neben den Noten liegt. Jede Fassung dauert so lange wie die erste.

**Duett:** Im Tab „Gesang“ unter „Duett mit“ eine zweite Stimme wählen (oder `--duett NAME` auf der Kommandozeile). Die beiden Stimmen wechseln sich in den Strophen ab, die Bridge singt die zweite, im Refrain singt die erste die Melodie und die zweite die zweite Stimme. Jede singt mit ihrem eigenen Tonumfang und steht etwas links bzw. rechts im Mix.

**Melodie und Text:** Die Melodie folgt dem Tonhöhenakzent der Wörter (Tokio-Japanisch aus dem Wörterbuch): wo ein Wort im Sprechen steigt, steigt meist auch die Melodie, ん und っ springen nicht. Lange Töne am Phrasenende werden oft auf zwei Töne gesungen (Melisma), auf dem Vokal der letzten Silbe; Balladen machen das öfter, Chiptune selten.

**Weiter bearbeiten in OpenUtau:** Neben `vocals.xml` für NEUTRINO schreibt die App die Gesangsnoten als UTAU-Projekt: `vocals.ust` (Melodie), `vocals_harmony.ust` (zweite Stimme) und beim Duett `vocals_duett_1.ust` und `vocals_duett_2.ust`. [OpenUtau](https://www.openutau.com/) öffnet sie mit Text, Tonhöhe und Tempo; dort lässt sich jede Note von Hand nachbessern oder mit einer anderen Stimme singen.

### Gesang mit VOICEVOX

[VOICEVOX](https://voicevox.hiroshiba.jp/) ist kostenlos und singt ab Version 0.16. VOICEVOX installieren und starten (die App reicht, sie läuft im Hintergrund), dann im Tab „Gesang“ bei „Gesang mit“ VOICEVOX wählen. Die Liste „VOICEVOX-Stimme“ zeigt alle Singstimmen, die VOICEVOX mitbringt; der Knopf daneben lädt sie neu. Läuft VOICEVOX auf einem anderen Rechner oder Port, die Adresse im Tab „Pfade“ eintragen (Standard `http://127.0.0.1:50021`).

VOICEVOX singt die Hauptstimme, die zweite Stimme im Refrain und mit zwei anderen Figuren den Chor im letzten Refrain. Silben, die VOICEVOX nicht kennt (zum Beispiel lateinische Buchstaben), singt es als „ら“, ein kleines „っ“ wird eine kurze Pause. Ist NEUTRINO gewählt, aber nicht da, springt VOICEVOX automatisch ein.

### Lebendiger Gesang

Unter „Lebendiger Gesang“ im Tab „Gesang“, jedes einzeln abschaltbar:

| Schalter | Was passiert |
| --- | --- |
| Atmer vor den Phrasen | vor jeder Zeile ein leises Einatmen; vor langen Zeilen ein tieferes |
| Echo auf dem letzten Wort | das letzte Wort am Ende jeder Sektion und jeder zweiten Refrain-Zeile hallt in punktierten Achteln links und rechts nach |
| Chor im letzten Refrain | zwei weitere Stimmen singen die Melodie mit: mit NEUTRINO die anderen installierten Stimmen (sonst dieselbe heller und dunkler), mit VOICEVOX zwei andere Figuren, mit der Vorschau-Stimme vier verstimmte Kopien der eigenen Stimme |
| Vibrato | 1 = wie die Stimme singt, 0 = gerade Töne, 2 = doppelt so viel; lange Töne ohne eigenes Vibrato bekommen eines |
| Übergänge | 1 = wie gesungen, 0 = die Töne springen (wie hartes Autotune), 2 = die Stimme gleitet doppelt so lange |

Vibrato und Übergänge ändert die App bei VOICEVOX direkt in der Tonhöhenkurve, bevor gesungen wird. Bei NEUTRINO rechnet sie die fertige Aufnahme Phrase für Phrase mit dem WORLD-Vocoder neu; das klingt eine Spur rauer, deshalb bleibt die Aufnahme bei 1 und 1 unberührt.

### Klang der Instrumente

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

Alles andere spielt weiter GeneralUser GS. Im Tab „Pfade“ steht, wie viele der zusätzlichen SoundFonts da sind, und ein Schalter stellt sie zum Vergleichen ab. Mit einem eigenen SoundFont in den Einstellungen bleiben sie aus.

Supersaw, Pluck, Pad, Lead, Chiptune-Klänge, Reese- und Sub-Bass und die breiten Future-Bass-Akkorde erzeugt die App selbst (`synth_engine.py`), ebenso Riser, Becken-Swells, Impacts und Downlifter vor den Refrains (`fx.py`).

**Schlagzeug aus der Drum-Machine:** Im Tab „Band“ steht beim Schlagzeug statt einer Spielweise der Klang: „wie der Stil“, das SoundFont-Schlagzeug oder die Drum-Machine 808 oder 909. Die App baut jeden Schlag wie die Roland-Maschinen aus Sinus, Rauschen und Rechteck-Schwingungen (`drum_machine.py`): die 808 mit langer, tiefer Bassdrum und metallischen Hi-Hats, die 909 kurz und druckvoll mit hellerer Snare. Ein offenes Hi-Hat verstummt, sobald ein geschlossenes kommt. Future Bass spielt von sich aus mit der 808.

**Gitarren über Verstärker und Box:** Verzerrte E-Gitarren (Overdrive und Distortion) spielt der SoundFont sauber, verzerrt wird erst danach wie mit einem echten Verstärker, und eine Box nimmt das Kratzen weg (`guitar_amp.py`). Das klingt rockiger, besonders bei Akkorden. Wer eine echte Box hören möchte, wählt im Tab „Pfade“ eine Impulsantwort (WAV); kostenlose gibt es viele im Netz. Ein Schalter im Tab „Band“ stellt das ab.

**Surge XT und andere VST3-Instrumente:** [Surge XT](https://surge-synthesizer.github.io) ist kostenlos und hat echte Supersaws, Reese-Bässe und Flächen, wie Future Bass und Drum and Bass sie brauchen. Ist es installiert, bietet der Tab „Pfade“ es an („Surge XT gefunden – übernehmen“), sonst trägt man den Pfad zur `.vst3`-Datei dort ein. Im Tab „Band“ öffnet „Klang wählen“ pro Spur (Synth, Lead, Bass, Gegenstimme) das Fenster des Instruments: einen Klang aussuchen, das Fenster schließen, und die Spur spielt ihn. „zurück“ gibt die Spur wieder dem Stil. Ohne gewählte Klänge spielt das Instrument wie bisher Synth und Lead mit seinem Standardklang. Getestet ist das mit einem nachgebauten Instrument, nicht mit Surge XT selbst; klappt etwas nicht, steht es im Protokoll, und die Spur spielt wie sonst.

**Schneller rendern:** Die Spuren rendern gleichzeitig auf bis zu sechs Prozessorkernen. Mit vier Kernen ist das Rendern etwa zweieinhalbmal so schnell (die Instrumente eines ganzen Songs in 21 statt 50 Sekunden); VST-Instrumente spielen nacheinander.

### Vorbild-Songs

Im Tab „Song“ gibst du jedem Song einen oder mehrere Vorbild-Songs (WAV, MP3, FLAC, OGG oder M4A), jeden mit einem Gewicht, wie stark er zählt. Lieblingssongs, die du öfter nimmst, legst du in den Ordner `vocaloid_generator\vorbilder\` (oder einen eigenen, Tab „Pfade“); dort hakst du sie nur noch an.

Was die Vorbilder bestimmen, schaltest du einzeln an und aus:

| Schalter | Was passiert |
| --- | --- |
| Mastering | Klang und Stereobreite des Masters wie die Vorbilder ([matchering](https://github.com/sergree/matchering)); bei mehreren Vorbildern nach ihrem Mittel |
| Lautstärke-Verlauf | ruhige und laute Teile liegen so weit auseinander wie in den Vorbildern |
| Gesangslautstärke | der Gesang steht so laut gegen die Band wie in den Vorbildern (eine Schätzung; Vorbilder ohne Gesang ändern nichts) |
| Tempo und Tonart vorschlagen | ein Klick übernimmt das gemessene Tempo und die Tonart |
| Stil vorschlagen | ein Klick übernimmt den Stil, der am besten zu den Vorbildern passt |

Gemessen wird mit librosa, jede Datei nur einmal (`vorbild_messungen.json`). Aus den Vorbildern landet nichts im Song, sie werden nur gemessen.

### Lautheit des Masters

Im Tab „Mix“ wählst du, wie laut der fertige Song wird: Standard -12 LUFS, -14 für YouTube und Spotify (die lautere Songs ohnehin herunterregeln), -16 für Apple Music oder -9 für den Club. Das gilt auch beim Mastering nach Vorbild-Songs.

### Liedtext

Im Tab „Text“ steht der Text pro Sektion; rechts daneben zeigt die App, welche Silben gesungen werden. Japanisch darf ganz normal geschrieben werden, mit Kanji und ohne Leerzeichen: `夜の街を歩いてた` wird zu よ る の ま ち お あ る い て た. Die Lesung der Kanji kommt aus dem Wörterbuch von fugashi (UniDic). Liest es ein Wort falsch, steht die richtige Lesung in eckigen Klammern dahinter: `君[きみ]`. Partikel singt die App so, wie man sie spricht (は als わ), und ー wird als langer Vokal gesungen.

### Eigene Akkorde und eigene Melodie

Im Tab „Song“ stehen unter „Eigene Akkorde“ Felder für Strophe, Pre-Chorus, Refrain und Bridge. Dort gehen Akkordnamen (`F G Em Am`, `C/E`, `Bbmaj7`) oder Stufen (`IV V iii vi`); ohne `|` ist jeder Akkord ein Takt, mit `|` trennst du Takte (`F | G | Em Am`). Die Folge wiederholt sich, bis die Sektion voll ist, und klingt genau so, ohne die Schlusswendung des Stils. Intro, Outro und Solo spielen die Akkorde des Refrains. Steigt der letzte Refrain, steigen Akkordnamen mit. Leere Felder nehmen die Akkorde des Stils, Tippfehler zeigt das Feld sofort an.

Unter „Eigene Melodie“ wählst du eine MIDI-Datei, zum Beispiel aus einer DAW oder von einem Keyboard eingespielt, und die Sektion, in der sie gesungen wird (Standard: Refrain). Die Spur mit den meisten Tönen zählt, auf Sechzehntel gerundet; bei Akkorden singt der höchste Ton. Die Melodie wiederholt sich, bis die Sektion voll ist (eine längere Melodie macht die Sektion länger, höchstens 16 Takte), und rückt in ganzen Oktaven in die Stimmlage. Sie wird nicht in die Tonart umgerechnet: Schreib sie in der Tonart des Songs. Der Text wird Silbe für Silbe auf die Töne gelegt. Feld leeren, dann wird wieder komponiert.

### MP3-Export

Für die MP3 braucht `pydub` das Programm ffmpeg (`winget install Gyan.FFmpeg`). Ohne ffmpeg entsteht der Song nur als `final_mix.wav`, und im Protokoll steht „MP3-Export übersprungen“.

## Starten

Oberfläche:

```powershell
uv run vocaloid_generator\app.py
```

Oder einfach `Vloid Songs starten.bat` im Projektordner doppelklicken. Die App öffnet sich in einem eigenen Fenster. Geht das Fenster nicht auf (es braucht die Microsoft-Edge-WebView2-Laufzeit, die auf Windows 10 und 11 meist schon da ist), startet `uv run vocaloid_generator\app.py --browser` dieselbe Oberfläche im Browser unter http://127.0.0.1:8090.

- **Song erzeugen** (oben rechts) macht einen neuen Song. Daneben wählst du, wie viele Fassungen am Stück entstehen; alle landen im Verlauf.
- **Player:** Der fertige Song spielt mit Wellenform; ein Klick in die Wellenform springt an diese Stelle. Unter „Anhören“ hörst du jede Spur einzeln, an derselben Stelle im Song.
- **Noten:** die Piano-Roll aller Spuren mit Tonhöhe, sie läuft beim Abspielen mit. Ein Klick auf eine Spur in der Legende blendet sie aus, ein Klick in die Noten springt im Player dorthin.
- **Neu würfeln:** Ein Knopf pro Teil (Melodie, Akkorde, Schlagzeug, jedes Instrument). Nur dieser Teil wird neu, der Rest des Songs bleibt. Rechts darüber wählst du, wo: im ganzen Song oder nur in einer Sektion, etwa nur die Melodie im Refrain oder nur das Schlagzeug in der Strophe.
- **3 Refrain-Melodien zur Auswahl:** drei neue Melodien für den Refrain als kurze Vorschau (Melodie als Synth über den Akkorden, in Sekunden fertig). Anhören, „nehmen“ drücken, und der ganze Song entsteht mit dieser Melodie.
- **Seed festhalten:** Danach macht „Song erzeugen“ wieder diesen Song, mit allem, was du inzwischen geändert hast (Mix, Gesang, Text). Das Seed-Feld im Tab „Song“ leeren, dann gibt es wieder jedes Mal einen neuen Song.
- **Als ZIP für die DAW:** alle Spuren als WAV und MIDI, siehe unten.
- **Tabs rechts:** Song (Stil, Tempo, Tonart, Ablauf, Vorbild-Songs, eigene Vorlagen), Text (mit Vorschau, wie gesungen wird), Band (Spielweise, Lautstärke, Panorama, Mute/Solo pro Spur, Klang von Schlagzeug, Gitarren und VST-Instrument), Gesang, Mix, Verlauf und Pfade.

Alle Einstellungen speichert die App sofort. Eigene Vorlagen (Tab „Song“) merken sich Stil, Tempo, Tonart, Ablauf, Band, Gesang und Mix, aber nicht den Text; sie liegen in `vocaloid_generator\vorlagen\`.

Kommandozeile, nutzt dieselben Einstellungen wie die Oberfläche:

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
| `--varianten N` | N Songs am Stück erzeugen; mit `--neu` N Fassungen der gewählten Teile |
| `--verlauf` | die letzten Songs auflisten |
| `--aus-verlauf NR` | Einstellungen und Seed eines Songs aus dem Verlauf nehmen (1 = der neueste) |
| `--zip DATEI` | den Song mit allen Spuren als ZIP für eine DAW exportieren |
| `--stimme NAME`, `--duett NAME` | NEUTRINO-Stimme und zweite Stimme fürs Duett für diesen Lauf |
| `--engine NAME` | wer singt: `NEUTRINO`, `VOICEVOX` oder `Vorschau` |
| `--voicevox-stimme ID` | VOICEVOX-Singstimme (die Nummer steht in der App neben dem Namen) |
| `--fassungen N` | NEUTRINO singt N-mal (1 bis 3), die sauberste Fassung zählt |
| `--vibrato X`, `--uebergaenge X` | Vibrato und Übergänge zwischen den Tönen, 0 bis 2 (1 = wie gesungen) |
| `--ohne-atmer`, `--ohne-echo`, `--ohne-chor` | Atmer, Echo auf dem letzten Wort oder Chor im letzten Refrain abschalten |
| `--schlagzeug KLANG` | Schlagzeug aus `soundfont`, `808` oder `909` statt wie der Stil |
| `--ohne-verstaerker`, `--box WAV` | verzerrte Gitarren wie früher aus dem SoundFont, oder über die Box aus dieser Impulsantwort |
| `--ohne-lofi-klang` | Lo-Fi ohne Knistern und Bandmaschine |
| `--vorbild DATEI` | Vorbild-Song für diesen Lauf, mehrfach möglich |
| `--vom-vorbild` | Tempo, Tonart und Stil der Vorbilder übernehmen |
| `--lautheit LUFS` | Lautheit des Masters, z. B. `-14` für YouTube |
| `-v` | alle Details ausgeben |

Die fertigen Dateien landen in `vocaloid_generator\output\` (oder im Ordner aus den Einstellungen): `final_song.mp3`, `final_mix.wav`, die einzelnen Spuren als WAV und MIDI, `vocals.xml` für NEUTRINO und die `.ust`-Dateien für OpenUtau.

### Verlauf, Neu würfeln und Varianten

Jeder fertige Song landet zusätzlich im Unterordner `verlauf\`: die MP3 und daneben eine JSON-Datei mit allen Einstellungen und dem Seed. Die 30 neuesten Songs bleiben dort, als Favorit markierte immer.

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
4. **Klang und Mix:** SoundFont-Rendering in Stereo (FluidSynth oder tinysoundfont, bessere Instrumente aus den zusätzlichen SoundFonts) auf mehreren Kernen, eigene Synths, Drum-Machine und Übergangs-Effekte, verzerrte Gitarren über Verstärker und Box, Klänge aus Surge XT, jede Spur auf ihre Ziel-Lautheit, EQ und Kompressor pro Spur, gemeinsamer Hall, De-Esser, Doppelung und Delay auf der Stimme, Echo auf dem letzten Wort, Atmer und Chor im letzten Refrain, Master auf die gewählte Lautheit (Standard -12 LUFS) mit Limiter.

Ohne Gesang (kein NEUTRINO, kein VOICEVOX, keine Vorschau-Stimme oder Gesang ausgeschaltet) spielt die Lead-Stimme die Gesangsmelodie.

## Einstellungen

Die App speichert alles in `vocaloid_generator\user_settings.json`. Die alte `settings.json` wird noch gelesen, solange es keine `user_settings.json` gibt. Ungültige Werte (zum Beispiel ein Pfad, den es auf diesem Rechner nicht gibt) werden beim Laden durch Standardwerte ersetzt und im Protokoll gemeldet.

Jeder erzeugte Song meldet im Protokoll seinen Seed. Mit diesem Seed lässt sich derselbe Song später noch einmal erzeugen. Seit dem Neu-Würfeln pro Teil und pro Sektion hat jeder Teil in jeder Sektion seinen eigenen Zufall; ein Seed aus einer älteren Version ergibt deshalb einen anderen Song als damals.

## Tests

```powershell
uv run pytest                 # alles
uv run pytest -m "not slow"   # ohne den Test, der echtes Audio rendert
```

## Aufbau

| Datei | Aufgabe |
| --- | --- |
| `settings.py` | alle Einstellungen eines Songs, mit Prüfung der Werte |
| `pipeline.py` | der komplette Ablauf: komponieren, Gesang, rendern, mischen, exportieren |
| `theory.py` | Tonarten, Akkorde, Stufen wie „IVmaj7“, Griffe mit Stimmführung |
| `styles.py` | die Stile: Instrumente, Spielweisen pro Sektion, Akkordfolgen, Mix |
| `song_plan.py` | Bauplan: Sektionen, Tonarten, Akkorde und Energie |
| `melody_writer.py` | Gesangsmelodie mit Motiven, Refrain-Hook, Wortakzent, Melisma und Duett-Aufteilung |
| `melody_import.py` | eigene Melodie aus einer MIDI-Datei lesen und in eine Sektion legen |
| `parts.py`, `drums.py` | Begleitung, Gegenstimme, Solo, Percussion und Schlagzeug |
| `orchestrator.py` | setzt alles zusammen und schreibt die MIDI-Spuren |
| `renderer.py` | rendert MIDI mit dem SoundFont (FluidSynth oder tinysoundfont) |
| `sound_library.py`, `setup_soundfonts.py` | welches Instrument aus welchem zusätzlichen SoundFont spielt, und deren Download |
| `synth_engine.py` | eigene Synths: Supersaw, Pluck, Pad, Lead, Chiptune, Reese- und Sub-Bass, Future-Bass-Akkorde |
| `drum_machine.py` | Schlagzeug wie aus der TR-808 und TR-909, ohne Samples |
| `guitar_amp.py` | verzerrte E-Gitarren über Verstärker und Box (eingebaut oder Impulsantwort) |
| `vst_sounds.py` | Surge XT finden, pro Spur einen Klang im Fenster des Instruments wählen und speichern |
| `fx.py` | Riser, Becken-Swell, Impact und Downlifter |
| `vocal_synthesizer.py` | MusicXML, NEUTRINO und die lokale Vorschau-Stimme |
| `voicevox.py` | Singen über die Schnittstelle von VOICEVOX |
| `voice_fx.py` | Atmer, Echo auf dem letzten Wort, Vibrato und Übergänge, beste Fassung, Chor im letzten Refrain |
| `ust_export.py` | Gesangsnoten als UTAU-Projekt (.ust) für OpenUtau |
| `mixer.py`, `exporter.py` | Mischen, Mastern, MP3- und ZIP-Export |
| `reference.py` | Vorbild-Songs messen: Tempo, Tonart, Stil, Lautstärke-Verlauf, Gesangsanteil |
| `history.py` | der Verlauf: jeder Song mit Seed und Einstellungen |
| `app.py`, `gui/` | die Oberfläche (NiceGUI): Seite, Einstellungen, Player mit wavesurfer.js, Piano-Roll |
| `vorlagen.py` | eigene Vorlagen speichern und laden |
| `main.py` | die Kommandozeile |
