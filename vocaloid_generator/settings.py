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
    "bass": ("default", "root", "driving", "sync", "octaves", "wobble", "sub_pulse", "lazy", "rolling"),
    "guitar": ("default", "chill_riff", "strummed", "palm_mute", "power_chords", "cutting"),
    "strings": ("default", "legato", "build", "pizzicato", "staccato", "harp"),
    "synth": ("default", "pad", "riser", "staccato_pluck", "wide_saw", "pluck", "arp", "supersaw", "fb_chords"),
    "brass": ("default", "stabs", "accents", "horns"),
    "bells": ("default", "sparkle", "sparkle16", "hook_octave", "accents", "music_box"),
    "choir": ("default", "aahs", "oohs"),
    "counter": ("default", "answer", "guide", "solo"),
    "perc": ("default", "shaker", "claps", "tambourine", "congas", "cowbell"),
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

# Die App speichert hier; settings.json ist das alte Format und wird nur noch gelesen
SETTINGS_PATH = os.path.join(config.BASE_DIR, "user_settings.json")
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
    seed: Optional[int] = Field(None, ge=0)
    # Wie oft ein Teil bei gleichem Seed neu gewürfelt wurde; ohne Eintrag bleibt er, wie der Seed ihn macht.
    # Schlüssel: Teil ("bass") oder Teil in einer Sektionsart ("melody:Chorus")
    variations: dict[str, int] = Field(default_factory=dict)
    # Eigene Akkorde pro Sektionsart ("F G Em Am" oder "IV V iii vi"); leer = die Akkorde des Stils
    custom_chords: dict[str, str] = Field(default_factory=dict)
    melody_midi: str = ""              # eigene Melodie als MIDI-Datei (leer = komponiert)
    melody_midi_section: str = "Chorus"    # in dieser Sektionsart singt die eigene Melodie

    active_sections: list[str] = Field(default_factory=lambda: [
        "Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"
    ])
    lyrics: str = DEFAULT_LYRICS

    singer: str = "MERROW"
    vocal_engine: str = "NEUTRINO"     # NEUTRINO, VOICEVOX oder Vorschau; fehlt eine, singt die andere
    harmonies: bool = True             # zweite Stimme im Refrain (mit NEUTRINO oder VOICEVOX)
    duet_singer: str = ""              # zweite NEUTRINO-Stimme fürs Duett (leer = kein Duett)
    style_shift: int = Field(0, ge=-6, le=6)   # NEUTRINO StyleShift: + heller, - dunkler
    vocal_takes: int = Field(1, ge=1, le=3)    # NEUTRINO singt so oft (StyleShift ±1), die sauberste Fassung zählt
    vibrato: float = Field(1.0, ge=0.0, le=2.0)   # 0 = gerade Töne, 1 = wie gesungen, 2 = doppelt so viel
    glide: float = Field(1.0, ge=0.0, le=2.0)     # Übergänge zwischen Tönen: 0 = springen, 1 = wie gesungen, 2 = länger
    breaths: bool = True               # hörbares Einatmen vor den Phrasen
    echo_throws: bool = True           # Echo auf dem letzten Wort einer Phrase
    final_choir: bool = True           # im letzten Refrain singt ein Chor mit
    voicevox_url: str = ""             # Adresse von VOICEVOX (leer = http://127.0.0.1:50021, App oder Engine)
    voicevox_singer: int = Field(0, ge=0)          # VOICEVOX-Singstimme (Stil-ID, 0 = die erste)
    # Vorbild-Songs (reference.py) und was sie bestimmen dürfen; jedes lässt sich abschalten
    reference_tracks: list[ReferenceTrack] = Field(default_factory=list)
    reference_folder: str = ""         # Ordner mit Lieblingssongs zum Anhaken (leer = vocaloid_generator/vorbilder)
    ref_mastering: bool = True         # Klang und Lautheit des Masters wie die Vorbilder
    ref_energy: bool = True            # leise und laute Teile so weit auseinander wie in den Vorbildern
    ref_vocal_level: bool = True       # Gesang so laut gegen die Band wie in den Vorbildern
    ref_tempo_key: bool = True         # Tempo und Tonart der Vorbilder vorschlagen
    ref_style: bool = True             # passenden Stil vorschlagen
    vst_path: str = ""
    vst_sounds: dict[str, str] = Field(default_factory=dict)   # Spur → gespeicherter Klang des VST-Instruments
    sound_library: bool = True         # bessere Klänge aus tools/soundfonts (setup_soundfonts.py), wenn vorhanden
    guitar_amp: bool = True            # verzerrte E-Gitarren über Verstärker und Box statt verzerrter Samples
    cabinet_ir: str = ""               # Impulsantwort einer Gitarrenbox (WAV); leer = eingebaute Box
    lofi_texture: bool = True          # im Stil Lo-Fi: Knistern, leiernde Bandmaschine, gedämpfte Höhen
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
        """Gleicher Song, nur dieser Teil wird neu gewürfelt ("bass" im ganzen Song, "bass:Chorus" nur im Refrain)."""
        if not is_rerollable(part):
            raise ValueError(f"Unbekannter Teil: {part}")
        return self.with_updates(variations={**self.variations, part: self.variations.get(part, 0) + 1})

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
        path = path or SETTINGS_PATH
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

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
