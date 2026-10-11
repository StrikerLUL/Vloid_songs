# model.py - Model for Vocaloid Music AI Generator Pro MVC
import logging

from settings import SongSettings

log = logging.getLogger(__name__)

class VocaloidModel:
    """Hält die Einstellungen für die Oberfläche und meldet jede Änderung an die Beobachter.
    Gespeichert und geprüft wird über settings.SongSettings."""
    def __init__(self):
        self._log_text = ""
        self._apply_flat(SongSettings().to_flat())

        # Observer callback list (callbacks are functions with signature callback(property_name, new_value))
        self._observers = []

        # Load initial settings from file if available
        self.load_settings()

    def add_observer(self, callback):
        if callback not in self._observers:
            self._observers.append(callback)

    def remove_observer(self, callback):
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify(self, property_name, value):
        for callback in self._observers:
            try:
                callback(property_name, value)
            except Exception:
                pass

    @property
    def bpm(self): return self._bpm
    @bpm.setter
    def bpm(self, val):
        val = int(val)
        if self._bpm != val:
            self._bpm = val
            self._notify("bpm", val)

    @property
    def style(self): return self._style
    @style.setter
    def style(self, val):
        val = str(val)
        if self._style != val:
            self._style = val
            self._notify("style", val)

    @property
    def energy(self): return self._energy
    @energy.setter
    def energy(self, val):
        val = str(val)
        if self._energy != val:
            self._energy = val
            self._notify("energy", val)

    @property
    def key(self): return self._key
    @key.setter
    def key(self, val):
        val = str(val)
        if self._key != val:
            self._key = val
            self._notify("key", val)

    @property
    def scale(self): return self._scale
    @scale.setter
    def scale(self, val):
        val = str(val)
        if self._scale != val:
            self._scale = val
            self._notify("scale", val)

    @property
    def singer(self): return self._singer
    @singer.setter
    def singer(self, val):
        val = str(val)
        if self._singer != val:
            self._singer = val
            self._notify("singer", val)

    @property
    def vocal_engine(self): return self._vocal_engine
    @vocal_engine.setter
    def vocal_engine(self, val):
        val = str(val)
        if self._vocal_engine != val:
            self._vocal_engine = val
            self._notify("vocal_engine", val)

    @property
    def vst_path(self): return self._vst_path
    @vst_path.setter
    def vst_path(self, val):
        val = str(val)
        if self._vst_path != val:
            self._vst_path = val
            self._notify("vst_path", val)

    @property
    def breathiness(self): return self._breathiness
    @breathiness.setter
    def breathiness(self, val):
        val = float(val)
        if self._breathiness != val:
            self._breathiness = val
            self._notify("breathiness", val)

    @property
    def swing(self): return self._swing
    @swing.setter
    def swing(self, val):
        val = float(val)
        if self._swing != val:
            self._swing = val
            self._notify("swing", val)

    @property
    def jitter(self): return self._jitter
    @jitter.setter
    def jitter(self, val):
        val = float(val)
        if self._jitter != val:
            self._jitter = val
            self._notify("jitter", val)

    @property
    def shimmer(self): return self._shimmer
    @shimmer.setter
    def shimmer(self, val):
        val = bool(val)
        if self._shimmer != val:
            self._shimmer = val
            self._notify("shimmer", val)

    @property
    def active_sections(self): return self._active_sections
    @active_sections.setter
    def active_sections(self, val):
        val = list(val)
        if self._active_sections != val:
            self._active_sections = val
            self._notify("active_sections", val)

    @property
    def lyrics(self): return self._lyrics
    @lyrics.setter
    def lyrics(self, val):
        val = str(val)
        if self._lyrics != val:
            self._lyrics = val
            self._notify("lyrics", val)

    @property
    def log_text(self): return self._log_text
    @log_text.setter
    def log_text(self, val):
        val = str(val)
        if self._log_text != val:
            self._log_text = val
            self._notify("log_text", val)

    # Paths
    @property
    def neutrino_pfad(self): return self._neutrino_pfad
    @neutrino_pfad.setter
    def neutrino_pfad(self, val):
        val = str(val)
        if self._neutrino_pfad != val:
            self._neutrino_pfad = val
            self._notify("neutrino_pfad", val)

    @property
    def soundfont_pfad(self): return self._soundfont_pfad
    @soundfont_pfad.setter
    def soundfont_pfad(self, val):
        val = str(val)
        if self._soundfont_pfad != val:
            self._soundfont_pfad = val
            self._notify("soundfont_pfad", val)

    @property
    def output_ordner(self): return self._output_ordner
    @output_ordner.setter
    def output_ordner(self, val):
        val = str(val)
        if self._output_ordner != val:
            self._output_ordner = val
            self._notify("output_ordner", val)

    # Master FX
    @property
    def compressor_threshold(self): return self._compressor_threshold
    @compressor_threshold.setter
    def compressor_threshold(self, val):
        val = float(val)
        if self._compressor_threshold != val:
            self._compressor_threshold = val
            self._notify("compressor_threshold", val)

    @property
    def compressor_ratio(self): return self._compressor_ratio
    @compressor_ratio.setter
    def compressor_ratio(self, val):
        val = float(val)
        if self._compressor_ratio != val:
            self._compressor_ratio = val
            self._notify("compressor_ratio", val)

    @property
    def limiter_threshold(self): return self._limiter_threshold
    @limiter_threshold.setter
    def limiter_threshold(self, val):
        val = float(val)
        if self._limiter_threshold != val:
            self._limiter_threshold = val
            self._notify("limiter_threshold", val)

    # Dynamic Instrument Properties Helpers
    # We will declare all these explicitly to make linting and static analysis happy and fast.
    
    # Volumes
    @property
    def volume_piano(self): return self._volume_piano
    @volume_piano.setter
    def volume_piano(self, v): self._volume_piano = float(v); self._notify("volume_piano", float(v))
    @property
    def volume_bass(self): return self._volume_bass
    @volume_bass.setter
    def volume_bass(self, v): self._volume_bass = float(v); self._notify("volume_bass", float(v))
    @property
    def volume_guitar(self): return self._volume_guitar
    @volume_guitar.setter
    def volume_guitar(self, v): self._volume_guitar = float(v); self._notify("volume_guitar", float(v))
    @property
    def volume_strings(self): return self._volume_strings
    @volume_strings.setter
    def volume_strings(self, v): self._volume_strings = float(v); self._notify("volume_strings", float(v))
    @property
    def volume_synth(self): return self._volume_synth
    @volume_synth.setter
    def volume_synth(self, v): self._volume_synth = float(v); self._notify("volume_synth", float(v))
    @property
    def volume_brass(self): return self._volume_brass
    @volume_brass.setter
    def volume_brass(self, v): self._volume_brass = float(v); self._notify("volume_brass", float(v))
    @property
    def volume_drums(self): return self._volume_drums
    @volume_drums.setter
    def volume_drums(self, v): self._volume_drums = float(v); self._notify("volume_drums", float(v))
    @property
    def volume_melody(self): return self._volume_melody
    @volume_melody.setter
    def volume_melody(self, v): self._volume_melody = float(v); self._notify("volume_melody", float(v))
    @property
    def volume_vocals(self): return self._volume_vocals
    @volume_vocals.setter
    def volume_vocals(self, v): self._volume_vocals = float(v); self._notify("volume_vocals", float(v))
    @property
    def volume_master(self): return self._volume_master
    @volume_master.setter
    def volume_master(self, v): self._volume_master = float(v); self._notify("volume_master", float(v))

    # Panning
    @property
    def pan_piano(self): return self._pan_piano
    @pan_piano.setter
    def pan_piano(self, v): self._pan_piano = float(v); self._notify("pan_piano", float(v))
    @property
    def pan_bass(self): return self._pan_bass
    @pan_bass.setter
    def pan_bass(self, v): self._pan_bass = float(v); self._notify("pan_bass", float(v))
    @property
    def pan_guitar(self): return self._pan_guitar
    @pan_guitar.setter
    def pan_guitar(self, v): self._pan_guitar = float(v); self._notify("pan_guitar", float(v))
    @property
    def pan_strings(self): return self._pan_strings
    @pan_strings.setter
    def pan_strings(self, v): self._pan_strings = float(v); self._notify("pan_strings", float(v))
    @property
    def pan_synth(self): return self._pan_synth
    @pan_synth.setter
    def pan_synth(self, v): self._pan_synth = float(v); self._notify("pan_synth", float(v))
    @property
    def pan_brass(self): return self._pan_brass
    @pan_brass.setter
    def pan_brass(self, v): self._pan_brass = float(v); self._notify("pan_brass", float(v))
    @property
    def pan_drums(self): return self._pan_drums
    @pan_drums.setter
    def pan_drums(self, v): self._pan_drums = float(v); self._notify("pan_drums", float(v))
    @property
    def pan_melody(self): return self._pan_melody
    @pan_melody.setter
    def pan_melody(self, v): self._pan_melody = float(v); self._notify("pan_melody", float(v))
    @property
    def pan_vocals(self): return self._pan_vocals
    @pan_vocals.setter
    def pan_vocals(self, v): self._pan_vocals = float(v); self._notify("pan_vocals", float(v))
    @property
    def pan_master(self): return self._pan_master
    @pan_master.setter
    def pan_master(self, v): self._pan_master = float(v); self._notify("pan_master", float(v))

    # Enabled
    @property
    def enabled_piano(self): return self._enabled_piano
    @enabled_piano.setter
    def enabled_piano(self, v): self._enabled_piano = bool(v); self._notify("enabled_piano", bool(v))
    @property
    def enabled_bass(self): return self._enabled_bass
    @enabled_bass.setter
    def enabled_bass(self, v): self._enabled_bass = bool(v); self._notify("enabled_bass", bool(v))
    @property
    def enabled_guitar(self): return self._enabled_guitar
    @enabled_guitar.setter
    def enabled_guitar(self, v): self._enabled_guitar = bool(v); self._notify("enabled_guitar", bool(v))
    @property
    def enabled_strings(self): return self._enabled_strings
    @enabled_strings.setter
    def enabled_strings(self, v): self._enabled_strings = bool(v); self._notify("enabled_strings", bool(v))
    @property
    def enabled_synth(self): return self._enabled_synth
    @enabled_synth.setter
    def enabled_synth(self, v): self._enabled_synth = bool(v); self._notify("enabled_synth", bool(v))
    @property
    def enabled_brass(self): return self._enabled_brass
    @enabled_brass.setter
    def enabled_brass(self, v): self._enabled_brass = bool(v); self._notify("enabled_brass", bool(v))
    @property
    def enabled_drums(self): return self._enabled_drums
    @enabled_drums.setter
    def enabled_drums(self, v): self._enabled_drums = bool(v); self._notify("enabled_drums", bool(v))
    @property
    def enabled_melody(self): return self._enabled_melody
    @enabled_melody.setter
    def enabled_melody(self, v): self._enabled_melody = bool(v); self._notify("enabled_melody", bool(v))
    @property
    def enabled_vocals(self): return self._enabled_vocals
    @enabled_vocals.setter
    def enabled_vocals(self, v): self._enabled_vocals = bool(v); self._notify("enabled_vocals", bool(v))
    @property
    def enabled_master(self): return self._enabled_master
    @enabled_master.setter
    def enabled_master(self, v): self._enabled_master = bool(v); self._notify("enabled_master", bool(v))

    # Mute
    @property
    def mute_piano(self): return self._mute_piano
    @mute_piano.setter
    def mute_piano(self, v): self._mute_piano = bool(v); self._notify("mute_piano", bool(v))
    @property
    def mute_bass(self): return self._mute_bass
    @mute_bass.setter
    def mute_bass(self, v): self._mute_bass = bool(v); self._notify("mute_bass", bool(v))
    @property
    def mute_guitar(self): return self._mute_guitar
    @mute_guitar.setter
    def mute_guitar(self, v): self._mute_guitar = bool(v); self._notify("mute_guitar", bool(v))
    @property
    def mute_strings(self): return self._mute_strings
    @mute_strings.setter
    def mute_strings(self, v): self._mute_strings = bool(v); self._notify("mute_strings", bool(v))
    @property
    def mute_synth(self): return self._mute_synth
    @mute_synth.setter
    def mute_synth(self, v): self._mute_synth = bool(v); self._notify("mute_synth", bool(v))
    @property
    def mute_brass(self): return self._mute_brass
    @mute_brass.setter
    def mute_brass(self, v): self._mute_brass = bool(v); self._notify("mute_brass", bool(v))
    @property
    def mute_drums(self): return self._mute_drums
    @mute_drums.setter
    def mute_drums(self, v): self._mute_drums = bool(v); self._notify("mute_drums", bool(v))
    @property
    def mute_melody(self): return self._mute_melody
    @mute_melody.setter
    def mute_melody(self, v): self._mute_melody = bool(v); self._notify("mute_melody", bool(v))
    @property
    def mute_vocals(self): return self._mute_vocals
    @mute_vocals.setter
    def mute_vocals(self, v): self._mute_vocals = bool(v); self._notify("mute_vocals", bool(v))
    @property
    def mute_master(self): return self._mute_master
    @mute_master.setter
    def mute_master(self, v): self._mute_master = bool(v); self._notify("mute_master", bool(v))

    # Solo
    @property
    def solo_piano(self): return self._solo_piano
    @solo_piano.setter
    def solo_piano(self, v): self._solo_piano = bool(v); self._notify("solo_piano", bool(v))
    @property
    def solo_bass(self): return self._solo_bass
    @solo_bass.setter
    def solo_bass(self, v): self._solo_bass = bool(v); self._notify("solo_bass", bool(v))
    @property
    def solo_guitar(self): return self._solo_guitar
    @solo_guitar.setter
    def solo_guitar(self, v): self._solo_guitar = bool(v); self._notify("solo_guitar", bool(v))
    @property
    def solo_strings(self): return self._solo_strings
    @solo_strings.setter
    def solo_strings(self, v): self._solo_strings = bool(v); self._notify("solo_strings", bool(v))
    @property
    def solo_synth(self): return self._solo_synth
    @solo_synth.setter
    def solo_synth(self, v): self._solo_synth = bool(v); self._notify("solo_synth", bool(v))
    @property
    def solo_brass(self): return self._solo_brass
    @solo_brass.setter
    def solo_brass(self, v): self._solo_brass = bool(v); self._notify("solo_brass", bool(v))
    @property
    def solo_drums(self): return self._solo_drums
    @solo_drums.setter
    def solo_drums(self, v): self._solo_drums = bool(v); self._notify("solo_drums", bool(v))
    @property
    def solo_melody(self): return self._solo_melody
    @solo_melody.setter
    def solo_melody(self, v): self._solo_melody = bool(v); self._notify("solo_melody", bool(v))
    @property
    def solo_vocals(self): return self._solo_vocals
    @solo_vocals.setter
    def solo_vocals(self, v): self._solo_vocals = bool(v); self._notify("solo_vocals", bool(v))
    @property
    def solo_master(self): return self._solo_master
    @solo_master.setter
    def solo_master(self, v): self._solo_master = bool(v); self._notify("solo_master", bool(v))

    # Styles/Patterns
    @property
    def style_piano(self): return self._style_piano
    @style_piano.setter
    def style_piano(self, v): self._style_piano = str(v); self._notify("style_piano", str(v))
    @property
    def style_bass(self): return self._style_bass
    @style_bass.setter
    def style_bass(self, v): self._style_bass = str(v); self._notify("style_bass", str(v))
    @property
    def style_guitar(self): return self._style_guitar
    @style_guitar.setter
    def style_guitar(self, v): self._style_guitar = str(v); self._notify("style_guitar", str(v))
    @property
    def style_strings(self): return self._style_strings
    @style_strings.setter
    def style_strings(self, v): self._style_strings = str(v); self._notify("style_strings", str(v))
    @property
    def style_synth(self): return self._style_synth
    @style_synth.setter
    def style_synth(self, v): self._style_synth = str(v); self._notify("style_synth", str(v))
    @property
    def style_brass(self): return self._style_brass
    @style_brass.setter
    def style_brass(self, v): self._style_brass = str(v); self._notify("style_brass", str(v))
    @property
    def style_drums(self): return self._style_drums
    @style_drums.setter
    def style_drums(self, v): self._style_drums = str(v); self._notify("style_drums", str(v))
    @property
    def style_melody(self): return self._style_melody
    @style_melody.setter
    def style_melody(self, v): self._style_melody = str(v); self._notify("style_melody", str(v))

    def _apply_flat(self, flat):
        for k, v in flat.items():
            setattr(self, f"_{k}", v)

    def to_settings(self) -> SongSettings:
        """Aktueller Stand als geprüfte SongSettings (für die Pipeline)."""
        flat = {k: getattr(self, f"_{k}") for k in SongSettings().to_flat()}
        return SongSettings.from_flat(flat)

    def save_settings(self):
        """Speichert alle Einstellungen als JSON."""
        try:
            self.to_settings().save()
        except Exception as e:
            log.warning("Einstellungen konnten nicht gespeichert werden: %s", e)

    def load_settings(self):
        """Lädt gespeicherte Einstellungen (oder die alte settings.json).
        Pfade werden aufgelöst, damit die Oberfläche die tatsächlich genutzten Ordner zeigt."""
        settings = SongSettings.load()
        flat = settings.to_flat()
        flat["neutrino_pfad"] = settings.neutrino_dir()
        flat["soundfont_pfad"] = settings.soundfont_file()
        flat["output_ordner"] = settings.output_dir()
        self._apply_flat(flat)
