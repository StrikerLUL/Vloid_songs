# model.py - Model for Vocaloid Music AI Generator Pro MVC
import logging

from settings import CHANNEL_FIELDS, CHANNELS, INSTRUMENTS, SongSettings

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
    def style_shift(self): return self._style_shift
    @style_shift.setter
    def style_shift(self, val):
        val = int(round(float(val)))
        if self._style_shift != val:
            self._style_shift = val
            self._notify("style_shift", val)

    @property
    def reference_track(self): return self._reference_track
    @reference_track.setter
    def reference_track(self, val):
        val = str(val)
        if self._reference_track != val:
            self._reference_track = val
            self._notify("reference_track", val)

    @property
    def harmonies(self): return self._harmonies
    @harmonies.setter
    def harmonies(self, val):
        val = bool(val)
        if self._harmonies != val:
            self._harmonies = val
            self._notify("harmonies", val)

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


# Kanal-Eigenschaften wie volume_piano oder style_bells, für jeden Kanal aus settings.py
_CASTS = {"volume": float, "pan": float, "enabled": bool, "mute": bool, "solo": bool, "style": str}


def _channel_property(name: str, cast):
    def getter(self):
        return getattr(self, f"_{name}")

    def setter(self, value):
        value = cast(value)
        setattr(self, f"_{name}", value)
        self._notify(name, value)

    return property(getter, setter)


for _channel in CHANNELS:
    for _field in CHANNEL_FIELDS + (("style",) if _channel in INSTRUMENTS else ()):
        setattr(VocaloidModel, f"{_field}_{_channel}", _channel_property(f"{_field}_{_channel}", _CASTS[_field]))
