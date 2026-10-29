# Credits und Lizenzen

Vloid Songs baut auf der Arbeit vieler anderer auf. Hier steht, was die App nutzt, von wem es ist und unter welcher
Lizenz. Was mit „lädt die App“ markiert ist, kommt erst über den Einrichten-Assistenten auf den Rechner.

## Wenn du Songs veröffentlichst

- **NEUTRINO**: Die Stimmen haben eigene Nutzungsbedingungen (meist: Name der Stimme und „NEUTRINO“ nennen).
  Sie stehen in der Readme jeder Stimme im Ordner `model`. https://studio-neutrino.com
- **VOICEVOX**: Jede Figur verlangt einen Hinweis wie `VOICEVOX:ずんだもん` in der Beschreibung.
  https://voicevox.hiroshiba.jp/term/
- **DiffSinger-Stimmen** (Versuch, lädst du selbst): Jede hat eigene Bedingungen, oft nur nicht kommerziell und mit
  Namensnennung. Sie stehen in der Readme oder `character.yaml` im Ordner der Stimme.
- **Eigene Atmer und Räume** (Ordner `Atmer` und `Hall`): Es gilt die Lizenz der Aufnahmen, die du dort hinlegst.
- **Klänge mit CC-BY oder CC-BY-SA** (AVL-Schlagzeuge, DRS Kit, Salamander-Flügel, Groove MIDI Dataset): Für
  Songs, die du damit machst, verlangen diese Lizenzen nichts. Sie gelten für die Klang- und Notendateien selbst,
  falls du die weitergibst.

## Gesang

| Was | Von | Lizenz |
| --- | --- | --- |
| NEUTRINO (nicht dabei, lädst du selbst) | SHACHI / studio-neutrino.com | eigene Bedingungen |
| Wohlfühl-Tempo und Genres der NEUTRINO-Stimmen (Angaben von den Stimmen-Seiten, 1.4) | studio-neutrino.com | Angaben, kein Code |
| VOICEVOX (nicht dabei, läuft getrennt) | Hiroshiba Kazuyuki | eigene Bedingungen pro Figur |
| pyworld (WORLD-Vocoder) | Masanori Morise, Jeremy Hsu | MIT |
| pyttsx3 (Vorschau-Stimme) | Natesh M Bhat | MPL-2.0 |
| fugashi, unidic-lite (japanischer Text) | Paul O'Leary McCann, NINJAL | MIT, BSD |
| jaconv (Romaji in Kana) | Yukino Ikegami | MIT |
| alkana (englische Wörter in Katakana) | cod | GPL-2.0 |
| e2k (englische Wörter in Katakana, Modell) | Patchethium | Unlicense |
| Praat und parselmouth (PSOLA, Swing, Formanten) | Paul Boersma, David Weenink; Yannick Jadoul | GPL-3.0 |
| onnxruntime (DiffSinger) | Microsoft | MIT |
| DiffSinger-Logik, nachgebaut aus OpenUtau | stakira und OpenUtau-Team; openvpi (DiffSinger) | MIT, Apache-2.0 |
| PyYAML (Einstellungen der DiffSinger-Stimmen) | Kirill Simonov | MIT |

## Instrumente und Klänge

| Was | Von | Lizenz |
| --- | --- | --- |
| GeneralUser GS (`soundfont.sf2`) | S. Christian Collins | GeneralUser GS License v2.0 (frei nutzbar) |
| FluidSynth (lädt die App) | FluidSynth-Team | LGPL-2.1 |
| TinySoundFont / tinysoundfont | Bernhard Schelling, Nathan Whitehead | MIT |
| MS Basic (lädt die App) | MuseScore | MIT |
| FM-Piano, E-Gitarren FSBS (lädt die App) | FreePats | CC0 |
| Red Zeppelin, Black Pearl (lädt die App) | Glen MacArthur, AVL Drumkits | CC-BY-SA 3.0 |
| VSCO 2 Community Edition (lädt die App) | Versilian Studios | CC0 |
| DRS Kit (lädt die App) | DrumGizmo-Team, Jes Eiler (DRSDrums) | CC-BY 4.0 |
| Salamander Grand Piano V3 (lädt die App) | Alexander Holm; SFZ-Fassung sfzinstruments | CC-BY 3.0 |
| Growlybass, Emily Guitar (lädt die App) | Karoryfer Samples | CC0 |
| Surge XT (lädt die App) | Surge Synth Team | GPL-3.0 |
| Surge-Klänge 96 Osc Supersaw, Gameboy, Super Pluck, Japanese Unison, Primitive Reese (kommen mit Surge XT) | Luna, Vincent Zauhar, Claes Johanson, Vospi | GPL-3.0 |
| Groove MIDI Dataset (lädt die App) | Google Magenta | CC-BY 4.0 |

## Mix, Analyse und Modelle

| Was | Von | Lizenz |
| --- | --- | --- |
| pedalboard | Spotify | GPL-3.0 |
| Neural Amp Modeler (das WaveNet der Modelle, in numpy nachgerechnet) | Steven Atkinson | MIT |
| Verstärker-Modelle Marshall JCM2000 Crunch, Peavey 6505+ Red (lädt die App, aus der Sammlung NAM_models) | Tim R, Helga Behrens; pelennor2170 | GPL-3.0 |
| Airwindows Consolidated (lädt die App) | Chris Johnson (Airwindows), Paul Walker (baconpaul) | MIT (Effekte), GPL-3.0 (Plugin) |
| matchering | Sergey Grishakov | GPL-3.0 |
| librosa | librosa-Team | ISC |
| pyloudnorm | Christian Steinmetz | MIT |
| music21 | Michael Scott Asato Cuthbert | BSD-3 |
| pretty_midi, mido | Colin Raffel, Ole Martin Bjørndalen | MIT |
| Audiobox Aesthetics (lädt die App) | Meta | CC-BY 4.0 |
| ACE-Step 1.5 (lädt die App, Versuch) | ACE Studio, StepFun | MIT |
| Demucs mit dem Modell htdemucs (lädt die App) | Meta | MIT |
| Anticipatory Music Transformer (lädt die App, Versuch) | John Thickstun, David Hall, Chris Donahue, Percy Liang (Stanford CRFM) | Apache-2.0 |
| PyTorch, Transformers (in den eigenen Umgebungen der Modelle) | PyTorch-Team, Hugging Face | BSD-3, Apache-2.0 |
| LCM Dreamshaper v7 (lädt die App, KI-Bilder fürs Video, 1.5) | Simian Luo u. a. (Latent Consistency Models), Lykon (Dreamshaper) | MIT |
| diffusers (in der Umgebung der KI-Bilder) | Hugging Face | Apache-2.0 |
| faster-whisper mit CTranslate2 (lädt die App, Hör-Check, 1.5) | SYSTRAN, OpenNMT | MIT |
| Whisper small (Modell des Hör-Checks, als faster-whisper-small) | OpenAI | MIT |

## Oberfläche und Werkzeuge

| Was | Von | Lizenz |
| --- | --- | --- |
| NiceGUI | Zauberzeug | MIT |
| pywebview | Roman Sirokov | BSD-3 |
| wavesurfer.js | katspaugh | BSD-3 |
| Pillow (Titelbilder, Hintergrund des Lyric-Videos) | Jeffrey A. Clark und Mitwirkende | MIT-CMU |
| mutagen (Titel, Liedtext und Titelbild in der MP3) | Joe Wreschnig, Michael Urman, Christoph Reiter und Mitwirkende | GPL-2.0 oder später |
| uv | Astral | MIT / Apache-2.0 |
| Python (bringt die Setup.exe mit, aus python-build-standalone) | Python Software Foundation, Astral | PSF-2.0, MPL-2.0 |
| Inno Setup (baut die Setup.exe) | Jordan Russell, Martijn Laan | eigene, freie Lizenz |

## Vloid Songs selbst

Vloid Songs ist ein privates Projekt und steht unter keiner offenen Lizenz. Die Songs, die du damit
machst, gehören dir; was die Stimmen und Klänge oben verlangen, gilt trotzdem.
