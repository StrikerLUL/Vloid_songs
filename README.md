# Vocaloid Song Generator

Erzeugt komplette Vocaloid-Songs auf Knopfdruck: Akkorde, Bass, Schlagzeug, Melodie und Begleitung, Gesang mit NEUTRINO (oder einer lokalen Vorschau-Stimme), Mix mit Kompressor und Limiter und am Ende eine fertige MP3.

Läuft unter Windows.

## Installation

Empfohlen mit [uv](https://docs.astral.sh/uv/), das Python und alle Bibliotheken passend installiert:

```powershell
winget install astral-sh.uv
uv sync
```

Ohne uv geht es auch mit pip (Python 3.10 bis 3.12):

```powershell
pip install -r vocaloid_generator\requirements.txt
```

### Gesang mit NEUTRINO

1. NEUTRINO (`NEUTRINO-windows-v3.1`) und die Stimme MERROW (`めろう（NEUTRINO-Library）-v3.1`) herunterladen und beide Ordner in den Projektordner legen.
2. `python setup_neutrino.py` kopiert die Stimme an die richtige Stelle.

Ohne NEUTRINO nutzt die App automatisch die lokale Vorschau-Stimme (Windows-Sprachausgabe plus Tonhöhen-Korrektur).

### Klang der Instrumente

Die Instrumente werden mit dem SoundFont `soundfont.sf2` gerendert. Dafür braucht `pyfluidsynth` die FluidSynth-Bibliothek. Fehlt sie, steht im Protokoll der App „Fallback auf basic synthesis“ und die Instrumente klingen nach einfachen Sinustönen. FluidSynth gibt es unter <https://github.com/FluidSynth/fluidsynth/releases>; den `bin`-Ordner aus dem Download in den `PATH` aufnehmen.

## Starten

Oberfläche:

```powershell
uv run vocaloid_generator\gui_mvc.py
```

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
| `-v` | alle Details ausgeben |

Die fertigen Dateien landen in `vocaloid_generator\output\` (oder im Ordner aus den Einstellungen): `final_song.mp3`, `final_mix.wav`, die einzelnen Spuren als WAV und MIDI und `vocals.xml` für NEUTRINO.

## Einstellungen

Die App speichert alles in `vocaloid_generator\user_settings.json`. Die alte `settings.json` wird noch gelesen, solange es keine `user_settings.json` gibt. Ungültige Werte (zum Beispiel ein Pfad, den es auf diesem Rechner nicht gibt) werden beim Laden durch Standardwerte ersetzt und im Protokoll gemeldet.

Jeder erzeugte Song meldet im Protokoll seinen Seed. Mit diesem Seed lässt sich derselbe Song später noch einmal erzeugen.

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
| `orchestrator.py` | setzt die Spuren der einzelnen Generatoren zu einem Song zusammen |
| `*_generator.py` | Akkorde, Bass, Schlagzeug, Melodie und die übrigen Instrumente |
| `humanizer.py` | Timing- und Lautstärke-Schwankungen wie bei echten Musikern |
| `vocal_synthesizer.py` | MusicXML, NEUTRINO und die lokale Vorschau-Stimme |
| `mixer.py`, `exporter.py` | Rendern, Mischen, Mastern und MP3-Export |
| `gui_mvc.py`, `model.py`, `view/`, `controller.py` | die Oberfläche |
| `main.py` | die Kommandozeile |
