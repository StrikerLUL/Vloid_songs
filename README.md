# Vocaloid Song Generator

Erzeugt komplette Vocaloid-Songs auf Knopfdruck: Akkorde, Bass, Schlagzeug, Melodie und Begleitung, Gesang mit NEUTRINO (oder einer lokalen Vorschau-Stimme), Mix mit Kompressor und Limiter und am Ende eine fertige MP3.

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

Schlägt NEUTRINO fehl, steht die Meldung im Protokoll, und die App nutzt die lokale Vorschau-Stimme (Windows-Sprachausgabe plus Tonhöhen-Korrektur). Ohne NEUTRINO nimmt sie diese Stimme sofort.

### Klang der Instrumente

Die Instrumente werden mit dem SoundFont `soundfont.sf2` (GeneralUser GS) in Stereo gerendert. Am besten klingt das mit FluidSynth, das alle Feinheiten des SoundFonts umsetzt. Einmal ausführen:

```powershell
uv run setup_fluidsynth.py
```

Das lädt FluidSynth 2.6 nach `tools\fluidsynth\bin`. Ohne FluidSynth rendert `tinysoundfont`, das mit `uv sync` installiert wird. Im Protokoll steht, welcher der beiden spielt. Wer einen anderen SoundFont nutzen möchte, trägt ihn in den Einstellungen ein.

Supersaw, Pluck, Pad, Lead und Chiptune-Klänge erzeugt die App selbst (`synth_engine.py`), ebenso Riser, Becken-Swells, Impacts und Downlifter vor den Refrains (`fx.py`). Wer ein eigenes VST3-Instrument wie Surge XT nutzen möchte, trägt es in den Einstellungen ein; es spielt dann Synth und Lead.

### Vorbild-Song

Im Tab „Song“ kannst du für jeden Song einen Vorbild-Song wählen (WAV, MP3 oder FLAC). Das Mastering gleicht dann Frequenzgang, Lautheit und Stereobreite an ihn an; das erledigt [matchering](https://github.com/sergree/matchering). Ohne Vorbild-Song mastert die App wie bisher auf -12 LUFS.

### Liedtext

Im Tab „Text“ steht der Text pro Sektion; rechts daneben zeigt die App, welche Silben gesungen werden. Japanisch darf ganz normal geschrieben werden, mit Kanji und ohne Leerzeichen: `夜の街を歩いてた` wird zu よ る の ま ち お あ る い て た. Die Lesung der Kanji kommt aus dem Wörterbuch von fugashi (UniDic). Liest es ein Wort falsch, steht die richtige Lesung in eckigen Klammern dahinter: `君[きみ]`. Partikel singt die App so, wie man sie spricht (は als わ), und ー wird als langer Vokal gesungen.

### MP3-Export

Für die MP3 braucht `pydub` das Programm ffmpeg (`winget install Gyan.FFmpeg`). Ohne ffmpeg entsteht der Song nur als `final_mix.wav`, und im Protokoll steht „MP3-Export übersprungen“.

## Starten

Oberfläche:

```powershell
uv run vocaloid_generator\app.py
```

Die App öffnet sich in einem eigenen Fenster. Geht das Fenster nicht auf (es braucht die Microsoft-Edge-WebView2-Laufzeit, die auf Windows 10 und 11 meist schon da ist), startet `uv run vocaloid_generator\app.py --browser` dieselbe Oberfläche im Browser unter http://127.0.0.1:8090.

- **Song erzeugen** (oben rechts) macht einen neuen Song. Daneben wählst du, wie viele Fassungen am Stück entstehen; alle landen im Verlauf.
- **Player:** Der fertige Song spielt mit Wellenform; ein Klick in die Wellenform springt an diese Stelle. Unter „Anhören“ hörst du jede Spur einzeln, an derselben Stelle im Song.
- **Noten:** die Piano-Roll aller Spuren mit Tonhöhe, sie läuft beim Abspielen mit. Ein Klick auf eine Spur in der Legende blendet sie aus, ein Klick in die Noten springt im Player dorthin.
- **Neu würfeln:** Ein Knopf pro Teil (Melodie, Akkorde, Schlagzeug, jedes Instrument). Nur dieser Teil wird neu, der Rest des Songs bleibt.
- **Seed festhalten:** Danach macht „Song erzeugen“ wieder diesen Song, mit allem, was du inzwischen geändert hast (Mix, Gesang, Text). Das Seed-Feld im Tab „Song“ leeren, dann gibt es wieder jedes Mal einen neuen Song.
- **Als ZIP für die DAW:** alle Spuren als WAV und MIDI, siehe unten.
- **Tabs rechts:** Song (Stil, Tempo, Tonart, Ablauf, Vorbild-Song, eigene Vorlagen), Text (mit Vorschau, wie gesungen wird), Band (Spielweise, Lautstärke, Panorama, Mute/Solo pro Spur), Gesang, Mix, Verlauf und Pfade.

Alle Einstellungen speichert die App sofort. Eigene Vorlagen (Tab „Song“) merken sich Stil, Tempo, Tonart, Ablauf, Band, Gesang und Mix, aber nicht den Text; sie liegen in `vocaloid_generator\vorlagen\`.

Die alte Oberfläche (`uv run vocaloid_generator\gui_mvc.py`) startet noch, kennt aber Verlauf, Neu-Würfeln und Player nicht und fällt bald weg.

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
| `--neu TEIL` | nur diesen Teil des letzten Songs neu würfeln, der Rest bleibt; mehrfach möglich |
| `--varianten N` | N Songs am Stück erzeugen; mit `--neu` N Fassungen der gewählten Teile |
| `--verlauf` | die letzten Songs auflisten |
| `--aus-verlauf NR` | Einstellungen und Seed eines Songs aus dem Verlauf nehmen (1 = der neueste) |
| `--zip DATEI` | den Song mit allen Spuren als ZIP für eine DAW exportieren |
| `-v` | alle Details ausgeben |

Die fertigen Dateien landen in `vocaloid_generator\output\` (oder im Ordner aus den Einstellungen): `final_song.mp3`, `final_mix.wav`, die einzelnen Spuren als WAV und MIDI und `vocals.xml` für NEUTRINO.

### Verlauf, Neu würfeln und Varianten

Jeder fertige Song landet zusätzlich im Unterordner `verlauf\`: die MP3 und daneben eine JSON-Datei mit allen Einstellungen und dem Seed. Die 30 neuesten Songs bleiben dort, als Favorit markierte immer.

Gefällt dir alles außer einem Teil, wird nur dieser neu gewürfelt. Teile sind `chords` (Akkorde und Ablauf), `melody` (Gesangsmelodie) und jedes Instrument: `piano`, `bass`, `guitar`, `strings`, `synth`, `brass`, `bells`, `choir`, `counter`, `perc`, `drums`.

```powershell
uv run vocaloid_generator\main.py --neu melody                  # der letzte Song mit neuer Melodie
uv run vocaloid_generator\main.py --neu drums --varianten 3     # drei Schlagzeug-Fassungen zur Auswahl
uv run vocaloid_generator\main.py --varianten 3                 # drei ganz neue Songs
uv run vocaloid_generator\main.py --aus-verlauf 2 --zip song.zip
```

Neue Akkorde ändern auch alles, was auf den Akkorden spielt; eine neue Melodie ändert die Gegenstimme mit, weil sie der Melodie antwortet.

Die ZIP-Datei enthält den Mix, jede Spur als WAV (`Spuren\`) und MIDI (`MIDI\`), die Gesangsnoten als MusicXML (`Gesang\`), `einstellungen.json` und `song.txt` mit Tempo und Tonart. Alle Spuren starten bei 0:00 und lassen sich so in jede DAW ziehen.

## Stile

Jeder Stil bringt eigene Instrumente, Spielweisen, Schlagzeug-Grooves und Akkordfarben mit:

| Stil | Klang |
| --- | --- |
| J-Pop Energy | Klavier, Overdrive-Gitarre, Streicher, Pluck und Supersaw, Glockenspiel, Chor, Gegenstimme, Shaker und Claps, Riser und Impacts |
| Dark Vocaloid | schnelles Sechzehntel-Klavier, verzerrte Gitarre, Chor, Celesta, Cello-Gegenstimme, Double-Bass-Drum im Refrain |
| Kawaii Chiptune | eigene Chiptune-Synths, Synth-Bass, Glockenspiel in Sechzehnteln, Four-on-the-Floor, Bass duckt unter der Kick |
| Rock | Gitarren doppelt links und rechts, Bass, Schlagzeug, Gitarren-Antworten und -Solo |
| Ballade | Klavier-Arpeggien, Streicher, Pad, Spieluhr, Chor, Cello-Linie unter dem Gesang |
| City Pop | E-Piano mit Septakkorden, Funk-Gitarre, Oktav-Bass, Bläser, Congas, Saxofon-Antworten |

Keine Sektion klingt zweimal gleich: Die zweite Strophe bekommt eine Gegenstimme, der letzte Refrain Chor und Glockenspiel in der Oktave der Hook, und im Refrain spielen mehrere Synth-Schichten zusammen.

Im Tab „Band“ lässt sich pro Instrument eine andere Spielweise wählen. „wie der Stil“ nimmt die des Stils.

## So entsteht ein Song

1. **Bauplan:** Jede Sektion bekommt eine bewährte Akkordfolge (zum Beispiel die Royal-Road-Folge des J-Pop). Gleiche Sektionen klingen gleich, der Pre-Chorus endet auf der Dominante, der Refrain auf der Tonika, und der letzte Refrain steigt einen Halbton.
2. **Melodie:** Phrasen aus wiederkehrenden Rhythmus-Motiven, betonte Töne sind Akkordtöne. Der Refrain wiederholt seine erste Phrase als Hook, Intro und Outro spielen diese Hook. Kurze Liedtexte werden wiederholt, lange machen die Sektion länger.
3. **Begleitung und Schlagzeug:** Spielweisen pro Instrument mit Stimmführung, Grooves mit Fills, Crash auf jedem Refrain, Snare-Wirbel und kurzer Stopp vor dem Refrain.
4. **Klang und Mix:** SoundFont-Rendering in Stereo (FluidSynth oder tinysoundfont), eigene Synths und Übergangs-Effekte, jede Spur auf ihre Ziel-Lautheit, EQ und Kompressor pro Spur, gemeinsamer Hall, De-Esser, Doppelung und Delay auf der Stimme, Master auf -12 LUFS mit Limiter.

Ohne Gesang (kein NEUTRINO, keine Vorschau-Stimme oder Gesang ausgeschaltet) spielt die Lead-Stimme die Gesangsmelodie.

## Einstellungen

Die App speichert alles in `vocaloid_generator\user_settings.json`. Die alte `settings.json` wird noch gelesen, solange es keine `user_settings.json` gibt. Ungültige Werte (zum Beispiel ein Pfad, den es auf diesem Rechner nicht gibt) werden beim Laden durch Standardwerte ersetzt und im Protokoll gemeldet.

Jeder erzeugte Song meldet im Protokoll seinen Seed. Mit diesem Seed lässt sich derselbe Song später noch einmal erzeugen. Seit dem Neu-Würfeln pro Teil hat jeder Teil seinen eigenen Zufall; ein Seed aus einer älteren Version ergibt deshalb einen anderen Song als damals.

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
| `melody_writer.py` | Gesangsmelodie mit Motiven und Refrain-Hook |
| `parts.py`, `drums.py` | Begleitung, Gegenstimme, Percussion und Schlagzeug |
| `orchestrator.py` | setzt alles zusammen und schreibt die MIDI-Spuren |
| `renderer.py` | rendert MIDI mit dem SoundFont (FluidSynth oder tinysoundfont) |
| `synth_engine.py` | eigene Synths: Supersaw, Pluck, Pad, Lead, Chiptune |
| `fx.py` | Riser, Becken-Swell, Impact und Downlifter |
| `vocal_synthesizer.py` | MusicXML, NEUTRINO und die lokale Vorschau-Stimme |
| `mixer.py`, `exporter.py` | Mischen, Mastern, MP3- und ZIP-Export |
| `history.py` | der Verlauf: jeder Song mit Seed und Einstellungen |
| `app.py`, `gui/` | die Oberfläche (NiceGUI): Seite, Einstellungen, Player mit wavesurfer.js, Piano-Roll |
| `vorlagen.py` | eigene Vorlagen speichern und laden |
| `gui_mvc.py`, `model.py`, `view/`, `controller.py` | die alte Oberfläche (CustomTkinter) |
| `main.py` | die Kommandozeile |
