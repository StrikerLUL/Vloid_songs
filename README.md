# Vloid Songs

Erzeugt komplette Vocaloid-Songs auf Knopfdruck: Akkorde, Bass, Schlagzeug, Melodie und Begleitung, Gesang mit NEUTRINO oder VOICEVOX (oder einer lokalen Vorschau-Stimme), Mix mit Kompressor und Limiter und am Ende eine fertige MP3.

Läuft unter Windows. Version 1.2.0.

| Zum Lesen | Was drinsteht |
| --- | --- |
| [ANLEITUNG.md](ANLEITUNG.md) | Erste Schritte, was die App kann, jeder Schalter, alle Details und die Kommandozeile (in der App: Hilfe › Erste Schritte) |
| [FEHLERBEHEBUNG.md](FEHLERBEHEBUNG.md) | wenn etwas nicht klappt (Hilfe › Fehlerbehebung) |
| [TESTLISTE.md](TESTLISTE.md) | der Praxistest für 1.2.0 (mit den Punkten aus 1.1.0) |
| [CHANGELOG.md](CHANGELOG.md) | was in jeder Version neu ist |
| [CREDITS.md](CREDITS.md) | wessen Arbeit drinsteckt, mit Lizenzen |

## Installation

Am einfachsten mit der Setup.exe von der [Release-Seite](https://github.com/StrikerLUL/Vloid_songs/releases): ohne Adminrechte, mit Eintrag im Startmenü. Sie bringt ihr eigenes Python mit und lädt beim ersten Mal alle Bibliotheken. Klänge, Modelle und NEUTRINO richtet danach **Hilfe › Einrichten** in der App ein; die `setup_….py`-Skripte machen dasselbe von der Kommandozeile (siehe [Anleitung › Klang der Instrumente](ANLEITUNG.md#klang-der-instrumente)) (`main.py --einrichten alles`). Ein neues Release entsteht von selbst, wenn eine neue Version in `main` landet; die App findet es über „Nach Update suchen“.

Deine Daten (Einstellungen, Songs, Vorlagen, Vorbilder, Motive, Protokolle) liegen in `Dokumente\Vloid Songs`. Steht in `datenordner.txt` im Programmordner `programmordner`, bleiben sie wie früher in `vocaloid_generator`.

### Aus dem Quellcode

Mit [uv](https://docs.astral.sh/uv/). Im Projektordner (dort, wo `pyproject.toml` liegt) ausführen:

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

NEUTRINO darf die App nicht selbst laden: von [studio-neutrino.com](https://studio-neutrino.com/) laden, entpacken und unter **Hilfe › Einrichten** den Ordner wählen, in dem `bin` und `model` liegen. Ohne NEUTRINO singt VOICEVOX oder eine Vorschau-Stimme.

## Starten

Mit der Setup.exe: „Vloid Songs“ im Startmenü. Aus dem Quellcode `uv run vocaloid_generator\app.py` oder `Vloid Songs starten.bat`; mit `--browser` öffnet sich dieselbe Oberfläche im Browser unter http://127.0.0.1:8090. Die Kommandozeile `uv run vocaloid_generator\main.py` nutzt dieselben Einstellungen, z. B.:

```powershell
uv run vocaloid_generator\main.py --style Rock --bpm 140 --key E --scale minor --seed 42
uv run vocaloid_generator\main.py --rezept "Walzer im Mondlicht (3/4)"
uv run vocaloid_generator\main.py --neu melody:Chorus          # der letzte Song mit neuer Refrain-Melodie
```

Alle Optionen stehen in der [Anleitung unter Kommandozeile](ANLEITUNG.md#kommandozeile) und in `main.py --help`.

## Was die App kann

- **Komponieren:** zehn Stile, Bauplan mit bewährten Akkordfolgen, Melodie nach dem Wortakzent, Begleitung, Schlagzeug mit Grooves echter Schlagzeuger, 4/4-, 3/4- und 6/8-Takt, Rap-Teil, Solo.
- **Singen:** NEUTRINO (mit Fassungen und Comping, StyleShift pro Sektion, Duett, Begleitstimmen, Idol-Rufen), VOICEVOX, DiffSinger (Versuch) oder eine eigene Gesangsspur.
- **Klingen:** SoundFonts, Orchester, Flügel, Bass und Gitarre aus echten Aufnahmen, eigene Synths, Drum-Machines, Verstärker, Surge XT, ein Mix mit Platz für den Gesang, Mastering nach Vorbild-Songs.
- **Ändern:** Neu würfeln pro Teil und Sektion, Töne in der Piano-Roll ziehen, eine Phrase neu singen, Remix in einem anderen Stil, Wieder öffnen aus dem Verlauf.
- **Schreiben:** Japanisch mit Kanji, Romaji und englischen Wörtern, eigener Text pro Wiederholung, Text-Helfer, Song-Rezepte mit Beispieltext.
- **Ausgeben:** MP3 mit Tags und Titelbild, Off-Vocal und A-cappella, Lyric-Video in 1080p, „Fertig für YouTube“, ZIP für die DAW, Noten für Tuning-Tools, Album über Nacht.

Was jede Funktion genau tut und wo ihr Schalter steht: [ANLEITUNG.md](ANLEITUNG.md).

## Tests

```powershell
uv run pytest                 # alles
uv run pytest -m "not slow"   # ohne den Test, der echtes Audio rendert
```

## Aufbau

| Datei | Aufgabe |
| --- | --- |
| `settings.py` | alle Einstellungen eines Songs, mit Prüfung der Werte |
| `pipeline.py` | der komplette Ablauf: komponieren, Gesang, rendern, mischen, exportieren; Remix |
| `singing.py`, `rendering.py`, `mixdown.py` | Gesang mit der passenden Engine, die Spuren als WAV, womit gemischt wird |
| `meter.py`, `ritardando.py` | 3/4- und 6/8-Takt; langsamer zum Schluss mit Tempowechseln in den MIDI-Dateien |
| `rap.py`, `vocal_chops.py` | Rap-Teil von der VOICEVOX-Sprechstimme; Vocal Chops im Drop |
| `theory.py` | Tonarten, Akkorde, Stufen wie „IVmaj7“, Griffe mit Stimmführung |
| `styles.py` | die Stile: Instrumente, Spielweisen pro Sektion, Akkordfolgen, Mix |
| `song_plan.py` | Bauplan: Sektionen, Tonarten, Akkorde und Energie |
| `melody_writer.py` | Gesangsmelodie mit Motiven, Refrain-Hook, Wortakzent, Melisma und Duett-Aufteilung |
| `melody_import.py` | eigene Melodie aus einer MIDI-Datei lesen und in eine Sektion legen |
| `melody_score.py`, `chord_spice.py` | Punkte für eine Gesangsmelodie (die eingängigste von 30 singt); Zwischendominanten, Leihakkorde und Marusa-Folge |
| `humming.py` | eine gesummte Melodie (Aufnahme) in eine MIDI-Datei verwandeln |
| `preview.py` | geänderte Töne sofort anhören: Synth über der Band, nur um die Änderungen herum |
| `parts.py`, `drums.py` | Begleitung, Gegenstimme, Solo, Percussion und Schlagzeug |
| `orchestrator.py` | setzt alles zusammen und schreibt die MIDI-Spuren |
| `riff.py`, `kime.py`, `buildup.py` | eigenes Riff für Intro, Zwischenspiel und Outro; Kime, Stopps und kleine Fills; Aufbau innerhalb der Sektion |
| `bass_runs.py`, `band_runs.py`, `anison.py`, `groove_feel.py` | melodischer Anime-Bass; Läufe und Glissandi; Anison-Grooves; die Band im Timing des Schlagzeugers |
| `renderer.py` | rendert MIDI mit dem SoundFont (FluidSynth oder tinysoundfont) |
| `sound_library.py`, `setup_soundfonts.py` | welches Instrument aus welchem zusätzlichen SoundFont spielt, und deren Download |
| `sfz.py`, `sample_library.py`, `setup_samples.py` | Sampler für SFZ-Instrumente, welches Instrument aus welchen Orchester-Aufnahmen spielt, und deren Download |
| `mix_movement.py` | Bewegung im Mix: Anlauf vor dem Refrain, Hall pro Sektion, breitere Refrains |
| `motifs.py` | zusätzliche und aus MIDI-Dateien gelernte Rhythmen und Bewegungen für die Gesangsmelodie |
| `polish.py`, `polish_worker.py`, `setup_ace_step.py` | Klang-Veredler: ACE-Step 1.5 spielt die Band neu ein (eigene Umgebung), und diese einrichten |
| `rating.py`, `rating_worker.py`, `setup_bewertung.py` | mehrere Fassungen benoten (Audiobox Aesthetics in eigener Umgebung) und diese einrichten |
| `synth_engine.py` | eigene Synths: Supersaw, Pluck, Pad, Lead, Chiptune, Reese- und Sub-Bass, Future-Bass-Akkorde |
| `drum_machine.py` | Schlagzeug wie aus der TR-808 und TR-909, ohne Samples |
| `surge_sounds.py`, `setup_surge.py` | Werks-Klänge von Surge XT statt der eigenen Synths, und dessen Download |
| `guitar_amp.py` | verzerrte E-Gitarren über Verstärker und Box (eingebaut oder Impulsantwort) |
| `vst_sounds.py` | Surge XT finden, pro Spur einen Klang im Fenster des Instruments wählen und speichern |
| `amp_models.py`, `setup_nam.py` | Modelle echter Verstärker (Neural Amp Modeler, in numpy gerechnet), und deren Download |
| `fx.py` | Riser, Becken-Swell, Impact und Downlifter |
| `vocal_synthesizer.py` | MusicXML, NEUTRINO und die lokale Vorschau-Stimme |
| `voicevox.py` | Singen über die Schnittstelle von VOICEVOX |
| `voice_fx.py` | Atmer, Echo auf dem letzten Wort, Vibrato und Übergänge (PSOLA), beste Fassung, Chor im letzten Refrain, Lautstärke pro Silbe, Gesangs-Swing |
| `ust_export.py` | Gesangsnoten als UTAU-Projekt (.ust) für OpenUtau |
| `resonance.py`, `spoken.py` | Härte zähmen (Resonanz-Filter auf dem Gesang); die Sektion „Sprechen“ mit VOICEVOX |
| `neutrino_score.py` | Noten so schreiben, wie NEUTRINO sie gut singen kann: Haltezeichen, Atemzeichen, Doppelvokale, Englisch als Katakana |
| `backing_vocals.py` | Begleitstimmen: Harmonie je Refrain, Doppelung, gesungene Flächen, Ad-libs |
| `casting.py`, `vocal_check.py` | Stimmen-Casting und der Gesangs-Check unter dem Player |
| `vocal_mix.py`, `vocal_tone.py` | der Gesang sitzt vorn (Platz in der Band, Nachführen, Platte, Delay, Klang wie im Vorbild) und die Kette pro Stimme und Stil |
| `style_fx.py`, `airwindows.py`, `setup_airwindows.py` | Stil-Effekte auf dem Gesang, Airwindows Consolidated und dessen Download |
| `own_vocal.py` | eigene Gesangsspur einsetzen und an den Noten ausrichten |
| `diffsinger.py` | DiffSinger-Stimmen für OpenUtau singen lassen (onnxruntime, Versuch) |
| `karaoke.py` | der Text zum Mitlesen mit der Zeit jeder Silbe, und das Lyric-Video über ffmpeg |
| `mixer.py`, `exporter.py` | Mischen, Mastern, MP3- und ZIP-Export |
| `reference.py` | Vorbild-Songs messen: Tempo, Tonart, Stil, Lautstärke-Verlauf, Gesangsanteil |
| `history.py` | der Verlauf: jeder Song mit Seed und Einstellungen, Suche, Namen und Notizen |
| `project.py`, `tags.py` | den Gesang eines Songs aufheben und wieder öffnen; Titel, Liedtext und Titelbild in der MP3 |
| `album.py` | Album über Nacht |
| `youtube.py` | „Fertig für YouTube“: Ordner mit MP3, Video, Titelbild und Beschreibung |
| `lyrics.py`, `readings.py` | Liedtext in Silben: Kanji-Lesung, Romaji, Partikel; Zahlwörter und は, へ, を auch in Kana richtig lesen |
| `drum_kit.py`, `setup_drums.py` | echtes Schlagzeug aus dem DRS Kit, und dessen Download |
| `band_library.py`, `setup_band.py` | Flügel, E-Bass und E-Gitarre aus Aufnahmen, und deren Download |
| `grooves.py`, `setup_grooves.py` | Grooves und Fills aus dem Groove MIDI Dataset, und dessen Download |
| `separation.py`, `separation_worker.py`, `setup_demucs.py` | Mix pro Instrument: Demucs zerlegt die Vorbilder (eigene Umgebung), und diese einrichten |
| `accompaniment.py`, `accompaniment_worker.py`, `setup_begleitung.py` | KI-Begleitung: der Anticipatory Music Transformer (eigene Umgebung), und diese einrichten |
| `ai_melody.py` | KI-Melodie (Versuch): das Modell der KI-Begleitung schlägt Refrain-Melodien vor |
| `config.py`, `userdata.py` | wo Programm und Daten liegen, und der Umzug nach Dokumente |
| `einrichten.py`, `systemcheck.py`, `fehlerbericht.py`, `updates.py` | Einrichten, System prüfen, Fehlerbericht und Updates (Hilfe-Menü, `gui/dialogs.py`) |
| `cancel.py`, `resume.py`, `applog.py` | Abbrechen, Weitermachen nach einem Absturz, Protokolldatei |
| `app.py`, `gui/` | die Oberfläche (NiceGUI): Seite, Einstellungen, Player mit wavesurfer.js, Mitlesen, Piano-Roll zum Ändern des Gesangs |
| `vorlagen.py`, `rezepte.py` | eigene Vorlagen speichern und laden; Song-Rezepte mit Beispieltext |
| `lyric_helper.py` | Text-Helfer: Silben gegen Platz, Reime und Lesungen pro Zeile |
| `laufzeit.py`, `speicher.py` | Restzeit und Meldung, wenn ein Song fertig ist; Platz auf der Festplatte |
| `main.py` | die Kommandozeile |
