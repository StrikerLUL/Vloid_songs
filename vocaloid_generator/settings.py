# settings.py – Alle Song-Einstellungen an einem Ort, mit Prüfung der Werte (pydantic)
import json
import logging
import os
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

import config

log = logging.getLogger(__name__)

INSTRUMENTS = ("piano", "bass", "guitar", "strings", "synth", "brass", "bells", "choir", "counter", "perc",
               "drums", "melody")
# fx: Riser, Becken-Swells und Impacts an den Übergängen (Audio, kein MIDI)
CHANNELS = INSTRUMENTS + ("fx", "vocals", "master")
# Teile, die sich einzeln neu würfeln lassen ("melody" ist die Gesangsmelodie, "chords" Akkorde und Ablauf),
# im ganzen Song ("bass") oder nur in einer Sektionsart ("melody:Chorus")
REROLLABLE = ("chords",) + INSTRUMENTS
CHANNEL_FIELDS = ("volume", "pan", "enabled", "mute", "solo")
# Wählbare Spielweisen pro Instrument; "default" nimmt das Muster des Genres
STYLE_OPTIONS = {
    "piano": ("default", "chords", "eighths", "stabs", "arpeggio", "arpeggio16", "ballad_arp", "jazz_ch"),
    "bass": ("default", "root", "driving", "sync", "octaves", "wobble", "sub_pulse", "lazy", "rolling", "walking"),
    "guitar": ("default", "chill_riff", "strummed", "palm_mute", "power_chords", "cutting"),
    "strings": ("default", "legato", "build", "pizzicato", "staccato", "harp"),
    "synth": ("default", "pad", "riser", "staccato_pluck", "wide_saw", "pluck", "arp", "supersaw", "fb_chords"),
    "brass": ("default", "stabs", "accents", "horns"),
    "bells": ("default", "sparkle", "sparkle16", "hook_octave", "accents", "music_box"),
    "choir": ("default", "aahs", "oohs"),
    "counter": ("default", "answer", "guide", "solo"),
    "perc": ("default", "shaker", "claps", "tambourine", "congas", "cowbell", "taiko"),
    # Drums spielen die Grooves des Stils; wählbar ist der Klang: SoundFont-Kit oder Drum-Machine 808/909.
    # Die Lead-Stimme spielt den Refrain-Hook im Intro und Outro
    "drums": ("default", "soundfont", "808", "909"),
    "melody": ("default",),
}
# Ziel-Lautheit des Masters je nach Plattform (LUFS); Streaming-Dienste regeln lautere Songs herunter
MASTER_TARGETS = {-12.0: "Standard (-12 LUFS)", -14.0: "YouTube und Spotify (-14 LUFS)",
                  -16.0: "Apple Music (-16 LUFS)", -9.0: "Laut wie im Club (-9 LUFS)"}
KEYS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

# Die App speichert in deinem Datenordner; settings.json ist das alte Format und wird nur noch gelesen
SETTINGS_PATH = os.path.join(config.DATA_DIR, "Einstellungen.json")
LEGACY_SETTINGS_PATH = os.path.join(config.BASE_DIR, "settings.json")

# Jitter-Wert, bei dem der Humanizer genau die Genre-Standardwerte nutzt
DEFAULT_JITTER = 0.02

DEFAULT_LYRICS = (
    "[Verse]\n"
    "よ る の ま ち を あ る い て た\n"
    "ひ と り き り の か え り み ち\n"
    "ね お ん の ひ か り に と け て\n"
    "き み の こ え を さ が し て た\n\n"
    "[Pre-Chorus]\n"
    "と ど か な い と し っ て も\n"
    "て を の ば し て し ま う の\n"
    "こ の む ね の お く で\n"
    "な に か が は じ ま る\n\n"
    "[Chorus]\n"
    "い ま う た う よ き み に と ど け\n"
    "こ の お も い を ほ し の よ う に\n"
    "か が や い て よ る を こ え て\n"
    "ず っ と そ ば に い た い か ら わ す れ な い で\n\n"
    "[Bridge]\n"
    "な み だ の あ と も わ ら え る よ う に\n"
    "も う い ち ど だ け し ん じ て み た い"
)
# Text für einen Rap-Teil ohne eigenen Text (nicht im Textfeld der App, damit es so bleibt wie bisher)
DEFAULT_RAP_LYRICS = (
    "\n\n[Rap]\n"
    "き み の な ま え を よ ぶ た び に\n"
    "こ こ ろ の お く が さ わ ぐ ん だ\n"
    "ま よ わ ず い こ う よ こ の み ち を\n"
    "ふ り む か な い で は し り だ せ"
)

DEFAULT_VOLUMES = {
    "drums": 1.0, "bass": 0.9, "piano": 0.8, "guitar": 0.8, "strings": 0.7,
    "synth": 0.7, "brass": 0.7, "bells": 0.7, "choir": 0.7, "counter": 0.7, "perc": 0.7,
    "melody": 0.8, "fx": 0.7, "vocals": 1.0, "master": 1.0,
}
_DEFAULT_PANS = {
    "drums": 0.0, "bass": 0.0, "piano": -0.25, "guitar": 0.0, "strings": -0.40,
    "synth": 0.0, "brass": 0.20, "bells": 0.35, "choir": 0.0, "counter": 0.30, "perc": -0.35,
    "melody": -0.15, "fx": 0.0, "vocals": 0.0, "master": 0.0,
}


class ChannelSettings(BaseModel):
    """Ein Kanal im Mixer: Lautstärke, Panorama, an/aus, Mute/Solo und Spielweise."""
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    volume: float = Field(0.8, ge=0.0, le=2.0)
    pan: float = Field(0.0, ge=-1.0, le=1.0)
    enabled: bool = True
    mute: bool = False
    solo: bool = False
    style: str = "default"


class ReferenceTrack(BaseModel):
    """Ein Vorbild-Song: Datei, Gewicht (wie stark er zählt) und an/aus."""
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    path: str
    weight: float = Field(1.0, ge=0.0, le=3.0)
    enabled: bool = True


MIN_BARS, MAX_BARS = 1, 64        # Länge einer Sektion in Takten
MAX_NOTE_BEATS = 16.0             # so lang darf ein Ton der Melodie von Hand werden


def edit_key(beat: float) -> str:
    """Schlüssel eines geänderten Tons: sein Anfang in Schlägen, auf Sechzehntel gerundet ("12.25")."""
    return f"{round(beat * 4) / 4:g}"


def is_rerollable(key: str) -> bool:
    """Ein Teil aus REROLLABLE, wahlweise mit Sektionsart: "bass" oder "bass:Chorus"."""
    part, _, kind = key.partition(":")
    return part in REROLLABLE and (not kind or kind in config.SECTION_CONFIG)


def _default_channels() -> dict:
    return {ch: ChannelSettings(volume=DEFAULT_VOLUMES[ch], pan=_DEFAULT_PANS[ch]) for ch in CHANNELS}


class SongSettings(BaseModel):
    """Alles, was einen Song bestimmt. Leere Pfade bedeuten: Standardordner aus config.py."""
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    bpm: int = Field(160, ge=40, le=260)
    style: str = "J-Pop Energy"
    energy: str = "Hoch"
    key: str = "A"
    scale: Literal["minor", "major", "dorian", "phrygian"] = "minor"
    # Takt (meter.py): 4/4 wie bisher, 3/4 (Walzer) oder 6/8 (dort zählt bpm die punktierten Viertel)
    meter: Literal["4/4", "3/4", "6/8"] = "4/4"
    # Remix (v6 Nr. 8, pipeline.remix): Melodie und Akkorde wie im Stil remix_from bei remix_bpm, die Band spielt style
    remix_from: str = ""
    remix_bpm: int = Field(0, ge=0)
    ritardando: bool = True            # Ballade: vor dem Schlussakkord langsamer, der Akkord klingt länger (Fermate)
    seed: Optional[int] = Field(None, ge=0)
    # Wie oft ein Teil bei gleichem Seed neu gewürfelt wurde; ohne Eintrag bleibt er, wie der Seed ihn macht.
    # Schlüssel: Teil ("bass") oder Teil in einer Sektionsart ("melody:Chorus")
    variations: dict[str, int] = Field(default_factory=dict)
    # Eigene Akkorde pro Sektionsart ("F G Em Am" oder "IV V iii vi"); leer = die Akkorde des Stils
    custom_chords: dict[str, str] = Field(default_factory=dict)
    melody_midi: str = ""              # eigene Melodie als MIDI-Datei (leer = komponiert)
    melody_midi_section: str = "Chorus"    # in dieser Sektionsart singt die eigene Melodie
    more_motifs: bool = True           # mehr eingebaute Rhythmen und Gesten für die Gesangsmelodie (motifs.py)
    learned_motifs: bool = True        # Rhythmen und Gesten aus den MIDI-Dateien in motif_folder lernen
    motif_folder: str = ""             # Ordner mit MIDI-Melodien (leer = Motive im Datenordner)
    # Melodie 1.3.0, jedes mit Schalter
    best_melody: bool = True           # M1: jede Sektion vielfach schreiben, die Fassung mit den meisten Punkten singt
    melody_pickups: bool = True        # M2: Auftakte vor dem Takt und vorgezogene Töne über den Taktstrich (nur 4/4)
    melody_tensions: bool = True       # M3: Vorhalte und lange Refrain-Töne auf None oder großer Septime
    melody_climax: bool = True         # M4: der höchste Ton des Songs kommt einmal, am Ende des letzten Refrains
    melody_triplets: bool = True       # M5: Achteltriolen und punktierte Achtel (City Pop, Ballade mehr; nur 4/4)
    chord_spice: float = 0.5           # M6: Akkord-Würze 0 bis 1 (Zwischendominanten, Leihakkorde, sus4, laufender Bass)
    ai_melody: bool = False            # M7 (Versuch): die KI-Begleitung schlägt Refrain-Melodien vor, die beste singt

    active_sections: list[str] = Field(default_factory=lambda: [
        "Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"
    ])
    section_bars: dict[str, int] = Field(default_factory=dict)   # Takte pro Sektionsart; fehlt sie, wie config.py
    # Geänderte Töne der Gesangsmelodie: {Schlag ab Songanfang: Tonhöhe}, gelten für Seed und Zähler dieses Songs
    melody_edits: dict[str, int] = Field(default_factory=dict)
    melody_lengths: dict[str, float] = Field(default_factory=dict)   # {Schlag: neue Länge in Schlägen}
    lyrics: str = DEFAULT_LYRICS
    numbered_lyrics: bool = True       # „[Verse 2]“ im Liedtext: das zweite Vorkommen singt seinen eigenen Text

    singer: str = "MERROW"
    vocal_engine: str = "NEUTRINO"     # NEUTRINO, VOICEVOX, DiffSinger oder Vorschau; fehlt eine, singt die andere
    harmonies: bool = True             # zweite Stimme im Refrain (mit NEUTRINO oder VOICEVOX)
    duet_singer: str = ""              # zweite NEUTRINO-Stimme fürs Duett (leer = kein Duett)
    support_singer: str = ""           # B5: Support-Modell, eine zweite Stimme färbt die Hauptstimme (leer = aus)
    style_shift: int = Field(0, ge=-6, le=6)   # NEUTRINO StyleShift: + heller, - dunkler
    vocal_takes: int = Field(1, ge=1, le=3)    # NEUTRINO singt so oft (StyleShift ±1), die sauberste Fassung zählt
    vibrato: float = Field(1.0, ge=0.0, le=2.0)   # 0 = gerade Töne, 1 = wie gesungen, 2 = doppelt so viel
    glide: float = Field(1.0, ge=0.0, le=2.0)     # Übergänge zwischen Tönen: 0 = springen, 1 = wie gesungen, 2 = länger
    psola_reshape: bool = True         # Vibrato und Übergänge mit Praat-PSOLA statt WORLD (Klang bleibt)
    own_vocal: str = ""                 # eigene Gesangsspur (WAV), ersetzt die Hauptstimme; leer = die Engine singt
    own_vocal_align: bool = True       # die eigene Spur an den Noten ausrichten (z. B. Vorlauftakt weg)
    # von Hand neu gesungene Phrasen (E3): {Schlag einer Note der Phrase (edit_key): {"style_shift": int, "singer": str}}
    phrase_fixes: dict[str, dict] = Field(default_factory=dict)
    breaths: bool = True               # hörbares Einatmen vor den Phrasen
    recorded_breaths: bool = True      # aufgenommene Atmer aus dem Ordner Atmer statt Rauschen (wenn welche da sind)
    echo_throws: bool = True           # Echo auf dem letzten Wort einer Phrase
    final_choir: bool = True           # im letzten Refrain singt ein Chor mit
    vocal_comping: bool = True         # bei mehreren Fassungen jede Phrase aus der saubersten (voice_fx.comp)
    phrase_expression: bool = True     # Ausdruck pro Phrase: zum Höhepunkt lauter und heller, am Ende weicher
    syllable_dynamics: bool = True     # Lautstärke pro Silbe: Betonungen lauter, weicher Einsatz, Anlauf leiser
    text_expression: bool = True       # St2 (1.5.0): Zeilen mit 涙/ごめん leiser und dunkler, mit 叫べ/走れ kräftiger
    note_swells: bool = True           # St3 (1.5.0): gehaltene Töne mitten in der Phrase schwellen an
    living_double: bool = True         # St5 (1.5.0): die Doppelung im Refrain schwankt in Zeit und Tonhöhe wie gesungen
    hearing_check: bool = True         # St4 (1.5.0): nach dem Singen hört eine Spracherkennung ab (setup_hoercheck.py)
    vocal_chain: bool = True           # Studio-Kette: Sättigung, Hall und Delay je Sektion, echte Doppelung
    vocal_tone: bool = True            # Kette pro Stimme und Stil: EQ und Sättigung für helle/tiefe Stimmen, Ballade, Rock
    airwindows: bool = True            # Airwindows Consolidated (setup_airwindows.py): Band auf dem Gesang, Console7
    # Stil-Effekte (style_fx.py), jeweils nur in den Stilen, zu denen sie gehören
    telephone_fx: bool = True          # die erste Zeile wie durchs Telefon
    stutter_fx: bool = True            # die Stimme stottert im letzten Schlag vor dem Refrain
    hard_tune: bool = True             # harter Tune im Refrain (Future Bass, Kawaii)
    formant_fx: bool = True            # Formanten verschoben: kindlicher (Kawaii, Idol) oder dunkler
    vocal_swing: bool = True           # der Gesang swingt mit der Band, wenn der Song swingt (Lo-Fi)
    romaji: bool = True                # Liedtext in lateinischen Buchstaben (Romaji) japanisch singen
    smart_readings: bool = True        # Partikel は/へ/を auch in reinen Kana, Zahlwörter wie 一回 richtig (1.3.0)
    # Gesang 1.1, jedes mit Schalter. Noten, die NEUTRINO gut singen kann (neutrino_score.py):
    long_vowel_mark: bool = True       # lang gezogene Vokale und Melisma als ー statt als neue Silbe
    breath_marks: bool = True          # Atemzeichen in langen Phrasen (NEUTRINO trennt dort, braucht weniger Speicher)
    fast_diphthongs: bool = True       # zwei schnelle Töne mit Doppelvokal (か + い) auf einem Ton
    english_kana: bool = True          # englische Wörter als Katakana singen (love → ラブ)
    singable_melody: bool = True       # Melodie auf Singbarkeit prüfen: Sprünge, Spitzen, Atempausen
    # StyleShift pro Sektion: Strophe ruhiger und tiefer, Refrain kräftiger und heller (Versatz zum StyleShift)
    section_style: bool = True
    verse_style_shift: int = Field(-1, ge=-3, le=3)
    chorus_style_shift: int = Field(1, ge=-3, le=3)
    even_takes: bool = True            # Fassungen mit demselben StyleShift, gewertet nur nach groben Fehlern
    # Gesang sitzt vorn (vocal_mix.py)
    vocal_unmask: bool = True          # die Band wird dort leiser, wo der Gesang gerade laut ist (wie Trackspacer)
    vocal_ride: bool = True            # der Gesang wird nachgeführt, damit er gleich weit über der Band steht
    convolution_reverb: bool = True    # Gesangsplatte aus einer Impulsantwort, Pre-Delay im Tempo
    ducked_delay: bool = True          # das Gesangs-Delay ist leiser, solange gesungen wird
    resonance_tamer: bool = True       # G2 (1.3.0): Härte zähmen, nur gerade herausstechende Frequenzen leiser
    intonation: float = Field(0.5, ge=0.0, le=1.0)   # G1: ruhigen Teil schiefer Töne so weit zur Note ziehen
    ornaments: float = Field(0.35, ge=0.0, le=1.0)   # G3: Shakuri, Fall, Kobushi; 0,35 = dezent, je Stil dosiert
    vocal_pocket: bool = True          # G4: Gesang leicht hinter (City Pop, Lo-Fi, Ballade) oder vor dem Schlag (Rock, DnB)
    group_vocals: int = Field(0, ge=0, le=4)         # G5: 0 = aus, 3 oder 4 NEUTRINO-Stimmen als Gruppe
    diffsinger_expression: bool = True  # G8: DiffSinger mit Varianz-Modell: Strophe hauchig, Refrain kräftig
    spoken_sound: str = "Hall"         # G7: Klang der Sektion „Sprechen“: Hall, Telefon oder trocken
    # Begleitstimmen wie in Produktionen (backing_vocals.py), von NEUTRINO gesungen
    harmony_variety: bool = True       # Harmonie je Refrain anders (Phrasenenden, Terz darunter, darüber, Oktave)
    harmony_double: bool = True        # jede Harmonie zweimal gesungen, links und rechts
    sung_pads: bool = True             # gesungene Flächen (う, あ) im Refrain statt des Keyboard-Chors
    adlibs: bool = True                # Rufe und Echo-Antworten im letzten Refrain
    idol_calls: bool = True            # „はい！はい！“ mehrerer Stimmen im Refrain (Idol-Pop, Kawaii, J-Pop, Rock)
    vocal_chops: bool = True           # Schnipsel der Hauptstimme als Riff im Drop (vocal_chops.py)
    # Stimmen-Casting (casting.py): Lieblingsstimme je Stil, beim Wechsel des Stils gewählt
    style_singer: bool = True
    style_singers: dict[str, str] = Field(default_factory=dict)
    voicevox_url: str = ""             # Adresse von VOICEVOX (leer = http://127.0.0.1:50021, App oder Engine)
    voicevox_singer: int = Field(0, ge=0)          # VOICEVOX-Singstimme (Stil-ID, 0 = die erste)
    # Rap-Teil (v6 Nr. 7): die VOICEVOX-Sprechstimme spricht ihn im Takt; aus (oder ohne VOICEVOX) singt ihn die Engine
    rap_voice: bool = True
    rap_speaker: int = Field(0, ge=0)              # VOICEVOX-Sprechstimme für den Rap (Stil-ID, 0 = die erste)
    voicevox_dynamics: bool = True     # F2: VOICEVOX singt Silben- und Phrasen-Lautstärke selbst (statt nachher)
    diffsinger_voice: str = ""         # F1: DiffSinger-Stimme (Ordner oder Name; leer = die erste gefundene)
    # Vorbild-Songs (reference.py) und was sie bestimmen dürfen; jedes lässt sich abschalten
    reference_tracks: list[ReferenceTrack] = Field(default_factory=list)
    reference_folder: str = ""         # Ordner mit Lieblingssongs zum Anhaken (leer = Vorbilder im Datenordner)
    ref_mastering: bool = True         # Klang und Lautheit des Masters wie die Vorbilder
    ref_energy: bool = True            # leise und laute Teile so weit auseinander wie in den Vorbildern
    ref_vocal_level: bool = True       # Gesang so laut gegen die Band wie in den Vorbildern
    ref_stems: bool = True             # Gesang, Schlagzeug, Bass und Rest einzeln wie die Vorbilder (mit Demucs)
    ref_vocal_curve: bool = True       # die Klangkurve des Gesangs (Terzbänder, ±4 dB) wie im Vorbild-Gesang
    ref_tempo_key: bool = True         # Tempo und Tonart der Vorbilder vorschlagen
    ref_style: bool = True             # passenden Stil vorschlagen
    ref_structure: bool = True         # S1 (1.5.0): Ablauf, Takte und Akkorde des Vorbilds vorschlagen (vorbild_ablauf)
    # Songs 1.5.0, jedes mit Schalter
    key_words: bool = True             # S2: Kernwort des Refrains hoch oder lang, Gefühlswörter lang (Beste Melodie)
    catchy_chorus: bool = True         # S3: Ohrwurm-Wertung des Refrains bei „Beste Melodie suchen“
    chorus_lift: bool = True           # S5: erster Refrain schlanker, letzter mit allem
    # Charakter 1.5.0, jedes mit Schalter
    jpop_idol_split: bool = True       # C1: J-Pop Energy als Anison-Band ohne Royal Road, Idol-Pop mit Rufen
    # C2: Produzenten-Profil (produzent.py), gilt für alle Songs; ohne Namen und Auswahl ändert sich nichts
    producer_profile: bool = True
    producer_name: str = ""            # Abspann, YouTube-Beschreibung, MP3-Künstler, Tag
    producer_tag: bool = True          # vier Töne aus dem Namen am Anfang jedes Songs
    producer_sound: str = ""           # Erkennungsklang (produzent.SOUNDS); leer = aus dem Namen
    producer_turn: str = ""            # typische Akkordwendung im Refrain (produzent.TURNS); leer = keine
    producer_singer: str = ""          # Lieblingsstimme für alle Stile ohne eigene gemerkte Stimme
    taste_learning: bool = True        # C3: Daumen im Verlauf lenken die Würfel (geschmack.py)
    # der Geschmack, mit dem der Song entstand ([[Schlüssel], Daumen]), damit derselbe Seed derselbe Song bleibt
    taste_snapshot: list = Field(default_factory=list)
    # C4: zwei Stile mischen (style_dna.blend); ohne zweiten Stil ändert sich nichts
    style_blend: bool = True
    blend_style: str = ""              # der zweite Stil
    blend_share: float = Field(0.3, ge=0.1, le=0.5)   # sein Anteil an Instrumenten, Grooves und Akkorden
    vst_path: str = ""
    vst_sounds: dict[str, str] = Field(default_factory=dict)   # Spur → gespeicherter Klang des VST-Instruments
    sound_library: bool = True         # bessere Klänge aus tools/soundfonts (setup_soundfonts.py), wenn vorhanden
    samples: bool = True               # Orchester aus echten Aufnahmen (setup_samples.py, VSCO 2), wenn vorhanden
    real_drums: bool = True            # echtes Schlagzeug aus Aufnahmen (setup_drums.py, DRS Kit), wenn vorhanden
    band_samples: bool = True          # Flügel, E-Bass, E-Gitarre aus Aufnahmen (setup_band.py), wenn vorhanden
    real_grooves: bool = True          # Grooves und Fills echter Schlagzeuger (setup_grooves.py), wenn vorhanden
    lively_bass: bool = True           # Ghost-Notes und Slides im Bass
    guitar_strums: bool = True         # Gitarre schlägt je nach Energie andere Muster an, mit Abdämpfern
    # Band 1.3.0, jedes mit Schalter
    intro_riff: bool = True            # I1: eigenes Riff in Intro, Zwischenspiel (nach dem ersten Refrain) und Outro
    kime: bool = True                  # I2: gemeinsame Akzente (Kime), kurze Stopps und Läufe am Phrasenende (nur 4/4)
    band_groove: bool = True           # I3: Bass, Gitarre und Klavier spielen im Timing des Schlagzeugers (nur 4/4)
    bass_runs: bool = True             # I4: Bass-Läufe, Fills am Phrasenende, Oktaven im Refrain, City-Pop-Funk
    band_runs: bool = True             # I5: Klavierläufe, Glissando und Streicherlauf in den Refrain, Klavier-Hook
    anison_grooves: bool = True        # I6: 2-Beat, Disco-Hi-Hat, Tom-Groove, Wirbel und Becken-Stopps (schnelle Stile)
    section_buildup: bool = True       # I7: erste Strophe beginnt nur mit Klavier/Gitarre, Refrain mit Schicht mehr
    surge_sounds: bool = True          # I8: Supersaw, Pluck, Chip, Future-Bass, Reese aus Surge XT (setup_surge.py)
    amp_models: bool = True            # I9: verzerrte Gitarren über NAM-Modelle echter Verstärker (setup_nam.py)
    # Charakter 1.4.0 (style_dna.py, song_character.py), jedes mit Schalter
    style_chords: bool = True          # eigene Akkordfolgen und Kadenzen je Stil (Rock bVI-bVII-I, City Pop ii-V-I …)
    melody_character: bool = True      # Melodie je Stil: Dichte, Rhythmus, Sprünge, Staccato, Bogen
    style_arrangement: bool = True     # wer wann spielt, je Stil (Lo-Fi ohne Gitarre, Rock ohne Streicher …)
    song_character: bool = True        # jeder Song eigene Klänge, Grooves, Intro und Schluss (aus dem Seed)
    style_sound: bool = True           # Klangbild je Stil: Raum, Delay, Klangfarbe, Breite, Sättigung
    # Stimme 1.4.0
    voice_comfort: bool = True         # Wohlfühl-Tempo der NEUTRINO-Stimme beachten, ohne StyleShift am Stück singen
    gentle_reshape: bool = True        # Vibrato und Übergänge nur dort neu rechnen, wo sich etwas ändert
    soft_vocal_chain: bool = True      # weichere Gesangskette: sanfterer Kompressor, breitere Präsenz
    draft: bool = False                # nur für einen Lauf (pipeline.draft_settings): schneller Entwurf
    auto_rating: bool = True           # mehrere Fassungen automatisch bewerten (setup_bewertung.py), wenn eingerichtet
    guitar_amp: bool = True            # verzerrte E-Gitarren über Verstärker und Box statt verzerrter Samples
    cabinet_ir: str = ""               # Impulsantwort einer Gitarrenbox (WAV); leer = eingebaute Box
    lofi_texture: bool = True          # im Stil Lo-Fi: Knistern, leiernde Bandmaschine, gedämpfte Höhen
    mix_movement: bool = True          # Anlauf vor dem Refrain, Hall pro Sektion, breitere Refrains (mix_movement.py)
    polish: bool = True                # zweite Fassung mit von ACE-Step veredelter Band (setup_ace_step.py), wenn da
    polish_strength: float = Field(0.4, ge=0.05, le=0.95)   # wie viel ACE-Step am Klang der Band ändert
    ai_accompaniment: bool = False     # Begleitstimmen vom Anticipatory Music Transformer (setup_begleitung.py)
    polish_caption: str = ""           # eigene Klangbeschreibung für ACE-Step (Englisch); leer = passend zum Stil
    show_karaoke: bool = True          # Text zum Mitlesen unter dem Player
    lyric_hints: bool = True           # Text-Helfer: Silben gegen Platz, Reime und Lesungen pro Zeile (lyric_helper.py)
    shortcuts: bool = True             # Leertaste spielt, Strg+Enter erzeugt, Strg+Z nimmt die letzte Notenänderung zurück
    video_colors: bool = True          # Lyric-Video im Farbverlauf des Stils, Text und Wellenform in seinen Farben
    video_background: str = ""         # eigenes Bild als Hintergrund des Lyric-Videos; leer = Farbverlauf des Stils
    # Musikvideo 1.5.0 (musikvideo.py, Tab Video); jedes hat einen Schalter, aus = Lyric-Video wie bisher
    music_video: bool = True           # das Bild folgt dem Song: Szene je Stil, Sektionen, Takt, Akkorde, Spektrum
    video_scene: str = ""              # leer = passend zum Stil, sonst ein Stilname oder „Textkunst“
    video_motion: Literal["Stil", "ruhig", "lebhaft"] = "Stil"
    video_kanji: bool = True           # Text wie geschrieben (Kanji), Wort für Wort eingefärbt, statt Hiragana
    video_romaji: bool = True          # Romaji unter der Zeile
    video_german: bool = True          # deine Übersetzung („> …“ unter der Zeile) im Video
    video_chords: bool = True          # Akkord unten links, mit dem nächsten
    video_melody_line: bool = True     # die Gesangsmelodie als Notenlinie
    video_spectrum: bool = True        # Spektrum des fertigen Mixes
    video_words: bool = True           # Bilder aus dem Text: Regen bei 雨, Sterne bei 星, Chat bei 既読
    video_titles: bool = True          # Titelkarte am Anfang, Abspann mit Stimme am Ende
    video_hud: bool = True             # Ablaufleiste mit den Sektionen und Schläge
    video_figure: str = ""             # eigene Figur (PNG mit Transparenz), Mund zu
    video_figure_open: str = ""        # dieselbe Figur mit offenem Mund; leer = nur das eine Bild
    youtube_chapters: bool = True      # Kapitel (Strophe, Refrain …) mit Zeitmarken in der YouTube-Beschreibung
    ai_backgrounds: bool = True        # V13: ein KI-Bild pro Sektion (setup_bilder.py), wenn eingerichtet
    # Verlässlichkeit (1.0.0); jedes hat einen Schalter
    reuse_steps: bool = True           # fertigen Gesang wiederverwenden, nach einem Absturz weitermachen (resume.py)
    log_file: bool = True              # Protokoll in Protokolle\vloid_songs.log im Datenordner (applog.py)
    update_check: bool = True          # beim Start nach einer neuen Version schauen (updates.py)
    setup_wizard: bool = True          # Einrichten-Assistent beim Start, solange er nicht abgeschlossen ist
    done_notice: bool = True           # Windows-Benachrichtigung, wenn ein längerer Lauf fertig ist (laufzeit.py)
    # Alltag (1.0.0)
    history_keep: int = Field(30, ge=0, le=1000)   # so viele Songs behält der Verlauf (0 = alle); benannte immer
    keep_projects: bool = True         # den Gesang jedes Songs im Verlauf aufheben, zum Wieder-Öffnen (project.py)
    album_vary: bool = True            # Album über Nacht: jeder Song in eigener Tonart und leicht anderem Tempo
    breathiness: float = Field(0.028, ge=0.0, le=0.2)
    shimmer: bool = True
    swing: float = Field(0.12, ge=0.0, le=0.5)
    jitter: float = Field(DEFAULT_JITTER, ge=0.0, le=0.1)

    neutrino_pfad: str = ""
    soundfont_pfad: str = ""
    output_ordner: str = ""

    compressor_threshold: float = Field(-20.0, ge=-60.0, le=0.0)
    compressor_ratio: float = Field(2.0, ge=1.0, le=20.0)
    limiter_threshold: float = Field(-0.3, ge=-20.0, le=0.0)
    master_lufs: float = Field(-12.0, ge=-20.0, le=-6.0)   # Ziel-Lautheit des Masters (MASTER_TARGETS)
    true_peak: bool = True             # auch zwischen den Samples höchstens -1 dBTP (mixer.TRUE_PEAK_DB)
    mix_punch: bool = True             # I10: Parallelkompression Schlagzeug, Bus-Kompressor Band, Mehrband im Master
    vocal_versions: bool = True        # Off-Vocal (ohne Gesang) und A-cappella (nur Gesang) als eigene MP3
    id3_tags: bool = True              # Titel, Stimme, Stil, Tempo, Tonart, Liedtext und Titelbild in die MP3

    # 1.6.0
    simple_view: bool = True           # einfache Ansicht: Stil, Stimmung, Stimme, Länge, Text, ein Knopf (gui/einfach.py)
    quality: str = "Gut"               # in der einfachen Ansicht: Schnell, Gut oder Beste (qualitaet.py)
    song_length: str = "Normal"        # in der einfachen Ansicht: Kurz, Normal oder Lang (qualitaet.LENGTHS)
    tidy_switches: bool = True         # Schalter ausblenden, die im Hör-Duell keinen hörbaren Unterschied machten
    mood: float = Field(0.5, ge=0.0, le=1.0)   # Stimmung: 0 ruhig … 1 wild, verschiebt die Spannung aller Sektionen
    tension_curve: bool = True         # die gezeichnete Spannungskurve lenkt Schlagzeug, Besetzung und Mix (spannung.py)
    tension: dict[str, float] = Field(default_factory=dict)   # {„Chorus#2“: 0 bis 1} je Vorkommen einer Sektion
    local_cache: bool = True           # Zwischenspeicher und Projekte nicht in OneDrive, sondern auf dem PC (speicher.py)
    remote_lan: bool = False           # Handy als Fernbedienung: die App im WLAN, mit Zugangscode (fernbedienung.py)
    remote_code: str = ""              # Zugangscode fürs Handy; leer = beim ersten Einschalten würfeln

    channels: dict[str, ChannelSettings] = Field(default_factory=_default_channels)

    @model_validator(mode="before")
    @classmethod
    def _single_reference(cls, data):
        """Ältere Einstellungen kennen nur einen Vorbild-Song (reference_track)."""
        if isinstance(data, dict) and data.get("reference_track") and not data.get("reference_tracks"):
            data = {**data, "reference_tracks": [{"path": data["reference_track"]}]}
        return data

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        value = _FLAT_TO_SHARP.get(value, value)
        if value not in KEYS:
            raise ValueError(f"Unbekannte Tonart: {value}")
        return value

    @field_validator("video_scene")
    @classmethod
    def _check_scene(cls, value: str) -> str:
        from video_szenen import CHOICES
        if value not in CHOICES:
            raise ValueError(f"Unbekannte Szene: {value} (möglich: {', '.join(c for c in CHOICES if c)})")
        return value

    @field_validator("quality")
    @classmethod
    def _check_quality(cls, value: str) -> str:
        from qualitaet import PRESETS
        if value not in PRESETS:
            raise ValueError(f"Unbekannte Qualität: {value} (möglich: {', '.join(PRESETS)})")
        return value

    @field_validator("song_length")
    @classmethod
    def _check_length(cls, value: str) -> str:
        from qualitaet import LENGTHS
        if value not in LENGTHS:
            raise ValueError(f"Unbekannte Länge: {value} (möglich: {', '.join(LENGTHS)})")
        return value

    @field_validator("tension", mode="before")
    @classmethod
    def _check_tension(cls, value: dict) -> dict:
        """{„Chorus#2“: 0 bis 1}; Schlüssel ohne Nummer gelten fürs erste Vorkommen."""
        out = {}
        for key, level in (value or {}).items():
            kind, _, number = str(key).partition("#")
            if kind in config.SECTION_CONFIG and (not number or number.isdigit()):
                out[f"{kind}#{int(number or 1)}"] = min(1.0, max(0.0, float(level)))
        return out

    @field_validator("active_sections")
    @classmethod
    def _check_sections(cls, value: list) -> list:
        unknown = [s for s in value if s not in config.SECTION_CONFIG]
        if unknown:
            raise ValueError(f"Unbekannte Sektionen: {unknown}")
        return list(value)

    @field_validator("vst_sounds", mode="before")
    @classmethod
    def _check_vst_sounds(cls, value: dict) -> dict:
        from vst_sounds import PARTS
        return {part: str(state) for part, state in (value or {}).items() if part in PARTS and state}

    @field_validator("variations", mode="before")
    @classmethod
    def _check_variations(cls, value: dict) -> dict:
        return {part: int(n) for part, n in (value or {}).items() if is_rerollable(part) and int(n) > 0}

    @field_validator("section_bars", mode="before")
    @classmethod
    def _check_section_bars(cls, value: dict) -> dict:
        return {kind: int(bars) for kind, bars in (value or {}).items()
                if kind in config.SECTION_CONFIG and MIN_BARS <= int(bars) <= MAX_BARS}

    @field_validator("melody_edits", mode="before")
    @classmethod
    def _check_melody_edits(cls, value: dict) -> dict:
        edits = {}
        for beat, pitch in (value or {}).items():
            try:
                edits[edit_key(float(beat))] = max(0, min(127, int(pitch)))
            except (TypeError, ValueError):
                continue
        return edits

    @field_validator("melody_lengths", mode="before")
    @classmethod
    def _check_melody_lengths(cls, value: dict) -> dict:
        lengths = {}
        for beat, length in (value or {}).items():
            try:
                lengths[edit_key(float(beat))] = min(max(round(float(length) * 4) / 4, 0.25), MAX_NOTE_BEATS)
            except (TypeError, ValueError):
                continue
        return lengths

    @field_validator("custom_chords", mode="before")
    @classmethod
    def _check_custom_chords(cls, value: dict) -> dict:
        return {kind: str(text) for kind, text in (value or {}).items()
                if kind in config.SECTION_CONFIG and str(text).strip()}

    @field_validator("melody_midi_section")
    @classmethod
    def _check_melody_section(cls, value: str) -> str:
        if value not in config.SECTION_CONFIG:
            raise ValueError(f"Unbekannte Sektion: {value}")
        return value

    @field_validator("channels", mode="before")
    @classmethod
    def _complete_channels(cls, value: dict) -> dict:
        channels = _default_channels()
        for name, data in (value or {}).items():
            if name in channels:
                base = channels[name].model_dump()
                incoming = data.model_dump() if isinstance(data, ChannelSettings) else dict(data)
                channels[name] = ChannelSettings(**{**base, **incoming})
        return channels

    # ── Pfade ──────────────────────────────────────────────────────────────────
    def neutrino_dir(self) -> str:
        return _existing_or_default(self.neutrino_pfad, config.NEUTRINO_PFAD, "NEUTRINO-Ordner")

    def soundfont_file(self) -> str:
        return _existing_or_default(self.soundfont_pfad, config.SOUNDFONT_PFAD, "SoundFont")

    def own_soundfont(self) -> bool:
        """
        Spielt ein selbst gewählter SoundFont statt des mitgelieferten? Alte Einstellungen zeigen oft auf den
        mitgelieferten, nur an anderer Stelle; das zählt nicht als eigener.
        """
        if not self.soundfont_pfad or not os.path.exists(self.soundfont_pfad):
            return False
        path, default = self.soundfont_pfad, config.SOUNDFONT_PFAD
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(default)):
            return False
        try:
            return not (os.path.basename(path).lower() == os.path.basename(default).lower()
                        and os.path.getsize(path) == os.path.getsize(default))
        except OSError:
            return True

    def output_dir(self) -> str:
        configured = self.output_ordner
        if configured and (os.path.isdir(configured) or os.path.isdir(os.path.dirname(configured))):
            return configured
        if configured:
            log.warning("Output-Ordner nicht erreichbar: %s. Nutze %s", configured, config.OUTPUT_ORDNER)
        return config.OUTPUT_ORDNER

    # ── Hilfen für die Pipeline ─────────────────────────────────────────────────
    def instrument_styles(self) -> dict:
        return {inst: self.channels[inst].style for inst in INSTRUMENTS}

    def rerolled(self, part: str) -> "SongSettings":
        """
        Gleicher Song, nur dieser Teil wird neu gewürfelt ("bass" im ganzen Song, "bass:Chorus" nur im Refrain).
        Neue Melodie oder neue Akkorde verwerfen die geänderten Töne, sie gehörten zur alten Melodie.
        """
        if not is_rerollable(part):
            raise ValueError(f"Unbekannter Teil: {part}")
        new_melody = part.partition(":")[0] in ("melody", "chords")
        return self.with_updates(variations={**self.variations, part: self.variations.get(part, 0) + 1},
                                 melody_edits={} if new_melody else self.melody_edits,
                                 melody_lengths={} if new_melody else self.melody_lengths,
                                 phrase_fixes={} if new_melody else self.phrase_fixes)

    def section_config(self) -> dict:
        """config.SECTION_CONFIG mit den eigenen Längen der Sektionen."""
        return {kind: {**cfg, "bars": self.section_bars.get(kind, cfg["bars"])}
                for kind, cfg in config.SECTION_CONFIG.items()}

    def with_updates(self, **updates) -> "SongSettings":
        """Kopie mit geänderten Werten, die wieder geprüft wird."""
        return SongSettings.model_validate({**self.model_dump(), **updates})

    # ── Flaches Format (alte settings.json und VocaloidModel) ──────────────────
    def to_flat(self) -> dict:
        flat = self.model_dump(exclude={"channels"})
        for ch, data in self.channels.items():
            for field in CHANNEL_FIELDS:
                flat[f"{field}_{ch}"] = getattr(data, field)
            if ch in INSTRUMENTS:
                flat[f"style_{ch}"] = data.style
        return flat

    @classmethod
    def from_flat(cls, flat: dict) -> "SongSettings":
        data = {k: v for k, v in flat.items() if k in cls.model_fields and k != "channels"}
        channels = {}
        for ch in CHANNELS:
            fields = CHANNEL_FIELDS + (("style",) if ch in INSTRUMENTS else ())
            values = {f: flat[f"{f}_{ch}"] for f in fields if f"{f}_{ch}" in flat}
            if values:
                channels[ch] = values
        data["channels"] = channels
        return cls._validate_leniently(data)

    # ── Laden und Speichern ────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: str = None) -> "SongSettings":
        """Lädt die Einstellungen; ungültige Werte werden durch Standardwerte ersetzt."""
        candidates = [path] if path else [SETTINGS_PATH, LEGACY_SETTINGS_PATH]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError) as e:
                    log.warning("Einstellungen in %s nicht lesbar (%s), nutze Standardwerte.", candidate, e)
                    return cls()
                if "channels" in data:
                    return cls._validate_leniently(data)
                return cls.from_flat(data)
        return cls()

    def save(self, path: str = None) -> None:
        """Erst in eine Nebendatei, dann umbenennen: stürzt die App mittendrin ab, bleiben die alten Einstellungen
        lesbar, statt dass eine halbe Datei beim nächsten Start alles auf Standard setzt."""
        path = path or SETTINGS_PATH
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)
        os.replace(path + ".tmp", path)

    @classmethod
    def _validate_leniently(cls, data: dict) -> "SongSettings":
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            bad = {err["loc"][0] for err in e.errors() if err["loc"]}
            log.warning("Ungültige Einstellungen %s ersetzt durch Standardwerte.", sorted(bad))
            return cls.model_validate({k: v for k, v in data.items() if k not in bad})


def _existing_or_default(configured: str, default: str, label: str) -> str:
    if configured and os.path.exists(configured):
        return configured
    if configured:
        log.warning("%s nicht gefunden: %s. Nutze %s", label, configured, default)
    return default
