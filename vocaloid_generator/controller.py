# controller.py - Controller for Vocaloid Music AI Generator Pro MVC
import logging
import os
import queue
import threading
from tkinter import messagebox, TclError

from settings import CHANNELS, INSTRUMENTS
from vocal_synthesizer import installed_singers


class _QueueLogHandler(logging.Handler):
    """Forwards engine log records from the worker thread into the GUI queue."""
    def __init__(self, target_queue):
        super().__init__(level=logging.INFO)
        self.target_queue = target_queue
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        prefix = {logging.WARNING: "[WARN] ", logging.ERROR: "[FEHLER] ", logging.CRITICAL: "[FEHLER] "}.get(record.levelno, "")
        self.target_queue.put(("log", prefix + self.format(record)))


class VocaloidController:
    """Controller that binds the VocaloidModel and VocaloidMainView, handles events, and manages background threads."""
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.queue = queue.Queue()
        self.generation_in_progress = False
        self.last_song_path = None

        # Preview player plays the mix from the configured output folder
        self.view.song_tab.get_preview_path = lambda: os.path.join(self.model.output_ordner, "final_mix.wav")

        # Bind View events to Controller callbacks
        self.model.add_observer(self.model_changed)
        
        # Populate initial view values from the model
        self.sync_model_to_view()
        
        # Setup change trace bindings from View widgets back to the Model
        self.setup_bindings()

    def sync_model_to_view(self):
        """Populate all View variables with initial Model state."""
        self.view.song_tab.bpm_var.set(self.model.bpm)
        self.view.song_tab.key_var.set(self.model.key)
        self.view.song_tab.scale_var.set(self.model.scale)
        self.view.song_tab.set_structure(self.model.active_sections)
        
        self.view.lyrics_tab.set_lyrics(self.model.lyrics)
        
        for inst in INSTRUMENTS:
            ctrls = self.view.instrumente_tab.controls[inst]
            ctrls["volume"].set(getattr(self.model, f"volume_{inst}"))
            ctrls["style"].set(getattr(self.model, f"style_{inst}"))
            ctrls["enabled"].set(getattr(self.model, f"enabled_{inst}"))
            
        for chan in CHANNELS:
            ctrls = self.view.mixer_tab.channels_controls[chan]
            ctrls["volume"].set(getattr(self.model, f"volume_{chan}"))
            ctrls["pan"].set(getattr(self.model, f"pan_{chan}"))
            ctrls["solo"].set(getattr(self.model, f"solo_{chan}"))
            ctrls["mute"].set(getattr(self.model, f"mute_{chan}"))
            
        self.view.mixer_tab.comp_thresh_var.set(self.model.compressor_threshold)
        self.view.mixer_tab.comp_ratio_var.set(self.model.compressor_ratio)
        self.view.mixer_tab.lim_thresh_var.set(self.model.limiter_threshold)
        
        self.view.settings_tab.neutrino_path_var.set(self.model.neutrino_pfad)
        self.view.settings_tab.soundfont_path_var.set(self.model.soundfont_pfad)
        self.view.settings_tab.output_dir_var.set(self.model.output_ordner)
        self.view.settings_tab.swing_var.set(self.model.swing)
        self.view.settings_tab.jitter_var.set(self.model.jitter)
        self.view.settings_tab.vst_area.set_vst_path(self.model.vst_path)
        self.view.settings_tab.singer_var.set(self.model.singer)
        self.view.settings_tab.set_singers(installed_singers(self.model.neutrino_pfad))
        self.view.settings_tab.harmonies_var.set(self.model.harmonies)
        self.view.settings_tab.style_shift_var.set(self.model.style_shift)
        self.view.song_tab.reference_var.set(self.model.reference_track)

    def setup_bindings(self):
        """Bind tkinter variable trace events and direct edit hooks."""
        # Song Tab
        self.view.song_tab.bpm_var.trace_add("write", lambda *a: self.on_view_bpm_changed())
        self.view.song_tab.key_var.trace_add("write", lambda *a: self.on_view_key_changed())
        self.view.song_tab.scale_var.trace_add("write", lambda *a: self.on_view_scale_changed())
        self.view.song_tab.on_structure_changed = self.on_view_structure_changed
        
        # Lyrics Tab
        self.view.lyrics_tab.on_lyrics_changed = self.on_view_lyrics_changed
        
        # Instrumente Tab
        for inst in INSTRUMENTS:
            ctrls = self.view.instrumente_tab.controls[inst]
            ctrls["volume"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_volume_changed(i))
            ctrls["style"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_style_changed(i))
            ctrls["enabled"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_enabled_changed(i))
            
        # Mixer Tab
        for chan in CHANNELS:
            ctrls = self.view.mixer_tab.channels_controls[chan]
            ctrls["volume"].trace_add("write", lambda *a, c=chan: self.on_view_mixer_volume_changed(c))
            ctrls["pan"].trace_add("write", lambda *a, c=chan: self.on_view_mixer_pan_changed(c))
            ctrls["solo"].trace_add("write", lambda *a, c=chan: self.on_view_mixer_solo_changed(c))
            ctrls["mute"].trace_add("write", lambda *a, c=chan: self.on_view_mixer_mute_changed(c))
            
        # Master FX
        self.view.mixer_tab.comp_thresh_var.trace_add("write", lambda *a: self.on_view_comp_thresh_changed())
        self.view.mixer_tab.comp_ratio_var.trace_add("write", lambda *a: self.on_view_comp_ratio_changed())
        self.view.mixer_tab.lim_thresh_var.trace_add("write", lambda *a: self.on_view_lim_thresh_changed())
        
        # Settings Tab
        self.view.settings_tab.neutrino_path_var.trace_add("write", lambda *a: self.on_view_neutrino_path_changed())
        self.view.settings_tab.soundfont_path_var.trace_add("write", lambda *a: self.on_view_soundfont_path_changed())
        self.view.settings_tab.output_dir_var.trace_add("write", lambda *a: self.on_view_output_dir_changed())
        self.view.settings_tab.swing_var.trace_add("write", lambda *a: self.on_view_swing_changed())
        self.view.settings_tab.jitter_var.trace_add("write", lambda *a: self.on_view_jitter_changed())
        self.view.settings_tab.singer_var.trace_add("write", lambda *a: self.on_view_singer_changed())
        self.view.settings_tab.harmonies_var.trace_add("write", lambda *a: self.on_view_harmonies_changed())
        self.view.settings_tab.style_shift_var.trace_add("write", lambda *a: self.on_view_style_shift_changed())
        self.view.song_tab.reference_var.trace_add("write", lambda *a: self.on_view_reference_changed())

    # View modification handlers -> Model updates
    def on_view_bpm_changed(self):
        try:
            val = self.view.song_tab.bpm_var.get()
            if self.model.bpm != val:
                self.model.bpm = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_key_changed(self):
        val = self.view.song_tab.key_var.get()
        if self.model.key != val:
            self.model.key = val
            self.model.save_settings()

    def on_view_scale_changed(self):
        val = self.view.song_tab.scale_var.get()
        if self.model.scale != val:
            self.model.scale = val
            self.model.save_settings()

    def on_view_structure_changed(self, structure):
        if self.model.active_sections != structure:
            self.model.active_sections = structure
            self.model.save_settings()

    def on_view_lyrics_changed(self, text):
        if self.model.lyrics != text:
            self.model.lyrics = text
            self.model.save_settings()

    def on_view_instrument_volume_changed(self, inst):
        try:
            val = self.view.instrumente_tab.controls[inst]["volume"].get()
            if getattr(self.model, f"volume_{inst}") != val:
                setattr(self.model, f"volume_{inst}", val)
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_instrument_style_changed(self, inst):
        val = self.view.instrumente_tab.controls[inst]["style"].get()
        if getattr(self.model, f"style_{inst}") != val:
            setattr(self.model, f"style_{inst}", val)
            self.model.save_settings()

    def on_view_instrument_enabled_changed(self, inst):
        val = self.view.instrumente_tab.controls[inst]["enabled"].get()
        if getattr(self.model, f"enabled_{inst}") != val:
            setattr(self.model, f"enabled_{inst}", val)
            self.model.save_settings()

    def on_view_mixer_volume_changed(self, chan):
        try:
            val = self.view.mixer_tab.channels_controls[chan]["volume"].get()
            if getattr(self.model, f"volume_{chan}") != val:
                setattr(self.model, f"volume_{chan}", val)
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_mixer_pan_changed(self, chan):
        try:
            val = self.view.mixer_tab.channels_controls[chan]["pan"].get()
            if getattr(self.model, f"pan_{chan}") != val:
                setattr(self.model, f"pan_{chan}", val)
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_mixer_solo_changed(self, chan):
        val = self.view.mixer_tab.channels_controls[chan]["solo"].get()
        if getattr(self.model, f"solo_{chan}") != val:
            setattr(self.model, f"solo_{chan}", val)
            self.model.save_settings()

    def on_view_mixer_mute_changed(self, chan):
        val = self.view.mixer_tab.channels_controls[chan]["mute"].get()
        if getattr(self.model, f"mute_{chan}") != val:
            setattr(self.model, f"mute_{chan}", val)
            self.model.save_settings()

    def on_view_comp_thresh_changed(self):
        try:
            val = self.view.mixer_tab.comp_thresh_var.get()
            if self.model.compressor_threshold != val:
                self.model.compressor_threshold = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_comp_ratio_changed(self):
        try:
            val = self.view.mixer_tab.comp_ratio_var.get()
            if self.model.compressor_ratio != val:
                self.model.compressor_ratio = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_lim_thresh_changed(self):
        try:
            val = self.view.mixer_tab.lim_thresh_var.get()
            if self.model.limiter_threshold != val:
                self.model.limiter_threshold = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_neutrino_path_changed(self):
        val = self.view.settings_tab.neutrino_path_var.get()
        if self.model.neutrino_pfad != val:
            self.model.neutrino_pfad = val
            self.model.save_settings()

    def on_view_singer_changed(self):
        val = self.view.settings_tab.singer_var.get().strip()
        if val and self.model.singer != val:
            self.model.singer = val
            self.model.save_settings()

    def on_view_harmonies_changed(self):
        try:
            val = bool(self.view.settings_tab.harmonies_var.get())
        except (ValueError, TclError):
            return
        if self.model.harmonies != val:
            self.model.harmonies = val
            self.model.save_settings()

    def on_view_style_shift_changed(self):
        try:
            val = int(round(float(self.view.settings_tab.style_shift_var.get())))
        except (ValueError, TclError):
            return
        if self.model.style_shift != val:
            self.model.style_shift = val
            self.model.save_settings()

    def on_view_reference_changed(self):
        val = self.view.song_tab.reference_var.get().strip()
        if self.model.reference_track != val:
            self.model.reference_track = val
            self.model.save_settings()

    def on_view_soundfont_path_changed(self):
        val = self.view.settings_tab.soundfont_path_var.get()
        if self.model.soundfont_pfad != val:
            self.model.soundfont_pfad = val
            self.model.save_settings()

    def on_view_output_dir_changed(self):
        val = self.view.settings_tab.output_dir_var.get()
        if self.model.output_ordner != val:
            self.model.output_ordner = val
            self.model.save_settings()

    def on_view_swing_changed(self):
        try:
            val = self.view.settings_tab.swing_var.get()
            if self.model.swing != val:
                self.model.swing = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    def on_view_jitter_changed(self):
        try:
            val = self.view.settings_tab.jitter_var.get()
            if self.model.jitter != val:
                self.model.jitter = val
                self.model.save_settings()
        except (ValueError, TclError):
            pass

    # VST Path update callback (legacy support)
    def handle_vst_selected(self, path):
        self.model.vst_path = path
        self.model.save_settings()
        self.model.log_text = f"VST-Pfad geladen: {path}"

    # Arrangement Tab callbacks / Preset Manager integration
    def handle_preset_clicked(self, preset_name):
        from preset_manager import apply_preset
        apply_preset(self.model, preset_name)

    def handle_toggle_section(self, section_name):
        pass

    # Model changes -> View updates (Observer pattern)
    def model_changed(self, property_name, value):
        """Called when any Model property gets updated. Keep View in sync."""
        try:
            if property_name == "bpm":
                if self.view.song_tab.bpm_var.get() != value:
                    self.view.song_tab.bpm_var.set(value)
            elif property_name == "key":
                if self.view.song_tab.key_var.get() != value:
                    self.view.song_tab.key_var.set(value)
            elif property_name == "scale":
                if self.view.song_tab.scale_var.get() != value:
                    self.view.song_tab.scale_var.set(value)
            elif property_name == "active_sections":
                self.view.song_tab.set_structure(value)
            elif property_name == "lyrics":
                self.view.lyrics_tab.set_lyrics(value)
            elif property_name.startswith("volume_"):
                inst = property_name.replace("volume_", "")
                if self.view.mixer_tab.channels_controls[inst]["volume"].get() != value:
                    self.view.mixer_tab.channels_controls[inst]["volume"].set(value)
                if inst in self.view.instrumente_tab.controls:
                    if self.view.instrumente_tab.controls[inst]["volume"].get() != value:
                        self.view.instrumente_tab.controls[inst]["volume"].set(value)
            elif property_name.startswith("style_"):
                inst = property_name.replace("style_", "")
                if inst in self.view.instrumente_tab.controls:
                    if self.view.instrumente_tab.controls[inst]["style"].get() != value:
                        self.view.instrumente_tab.controls[inst]["style"].set(value)
            elif property_name.startswith("enabled_"):
                inst = property_name.replace("enabled_", "")
                if inst in self.view.instrumente_tab.controls:
                    if self.view.instrumente_tab.controls[inst]["enabled"].get() != value:
                        self.view.instrumente_tab.controls[inst]["enabled"].set(value)
            elif property_name.startswith("pan_"):
                chan = property_name.replace("pan_", "")
                if self.view.mixer_tab.channels_controls[chan]["pan"].get() != value:
                    self.view.mixer_tab.channels_controls[chan]["pan"].set(value)
            elif property_name.startswith("solo_"):
                chan = property_name.replace("solo_", "")
                ctrls = self.view.mixer_tab.channels_controls[chan]
                if ctrls["solo"].get() != value:
                    ctrls["solo"].set(value)
                if value:
                    ctrls["btn_solo"].configure(fg_color="#00f5d4", text_color="#1a1a2e")
                else:
                    ctrls["btn_solo"].configure(fg_color="#3a3e59", text_color="#eaeaea")
            elif property_name.startswith("mute_"):
                chan = property_name.replace("mute_", "")
                ctrls = self.view.mixer_tab.channels_controls[chan]
                if ctrls["mute"].get() != value:
                    ctrls["mute"].set(value)
                if value:
                    ctrls["btn_mute"].configure(fg_color="#ff2a5f", text_color="#ffffff")
                else:
                    ctrls["btn_mute"].configure(fg_color="#3a3e59", text_color="#eaeaea")
            elif property_name == "compressor_threshold":
                if self.view.mixer_tab.comp_thresh_var.get() != value:
                    self.view.mixer_tab.comp_thresh_var.set(value)
            elif property_name == "compressor_ratio":
                if self.view.mixer_tab.comp_ratio_var.get() != value:
                    self.view.mixer_tab.comp_ratio_var.set(value)
            elif property_name == "limiter_threshold":
                if self.view.mixer_tab.lim_thresh_var.get() != value:
                    self.view.mixer_tab.lim_thresh_var.set(value)
            elif property_name == "neutrino_pfad":
                if self.view.settings_tab.neutrino_path_var.get() != value:
                    self.view.settings_tab.neutrino_path_var.set(value)
                self.view.settings_tab.set_singers(installed_singers(value))
            elif property_name == "singer":
                if self.view.settings_tab.singer_var.get() != value:
                    self.view.settings_tab.singer_var.set(value)
            elif property_name == "style_shift":
                if self.view.settings_tab.style_shift_var.get() != value:
                    self.view.settings_tab.style_shift_var.set(value)
            elif property_name == "reference_track":
                if self.view.song_tab.reference_var.get() != value:
                    self.view.song_tab.reference_var.set(value)
            elif property_name == "harmonies":
                if self.view.settings_tab.harmonies_var.get() != value:
                    self.view.settings_tab.harmonies_var.set(value)
            elif property_name == "soundfont_pfad":
                if self.view.settings_tab.soundfont_path_var.get() != value:
                    self.view.settings_tab.soundfont_path_var.set(value)
            elif property_name == "output_ordner":
                if self.view.settings_tab.output_dir_var.get() != value:
                    self.view.settings_tab.output_dir_var.set(value)
            elif property_name == "swing":
                if self.view.settings_tab.swing_var.get() != value:
                    self.view.settings_tab.swing_var.set(value)
            elif property_name == "jitter":
                if self.view.settings_tab.jitter_var.get() != value:
                    self.view.settings_tab.jitter_var.set(value)
            elif property_name == "vst_path":
                self.view.settings_tab.vst_area.set_vst_path(value)
            elif property_name == "log_text":
                self.view.append_log(value)
        except Exception:
            pass

    # ── Background Task Runner ──────────────────────────────────────────────────
    def handle_generate(self):
        """Triggers the background thread to run actual song generator pipeline without blocking the main event loop."""
        if self.generation_in_progress:
            return
        
        # Verify song structure has active sections
        if not self.model.active_sections:
            messagebox.showwarning("Warnung", "Keine Sektionen im Arrangement-Track aktiv!")
            return
        
        self.generation_in_progress = True
        self.view.generate_btn.configure(state="disabled", text="⏳ Generiere...")
        
        # Clear log and set start layout
        self.view.clear_log()
        self.model.log_text = "━" * 55
        self.model.log_text = "  Vocaloid Music AI Generation Job gestartet (Real Pipeline)"
        self.model.log_text = "━" * 55
        
        # Spawn daemon generation worker thread
        self.worker_thread = threading.Thread(target=self._run_generation_task, daemon=True)
        self.worker_thread.start()
        
        # Start queue polling in the GUI thread loop
        self.view.after(100, self.poll_queue)

    def _run_generation_task(self):
        """Runs the shared pipeline in the worker thread and forwards progress and engine logs to the GUI queue."""
        from pipeline import generate_song

        handler = _QueueLogHandler(self.queue)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        previous_level = root_logger.level
        root_logger.setLevel(logging.INFO)
        try:
            settings = self.model.to_settings()

            def report(fraction, message):
                self.queue.put(("status", message))
                self.queue.put(("progress", fraction))

            result = generate_song(settings, progress=report)
            song_path = result.mp3 or result.mix_wav
            self.last_song_path = song_path
            self.queue.put(("log", "\n✦ Generierung erfolgreich abgeschlossen! ✦"))
            self.queue.put(("log", f"Seed: {result.seed}"))
            self.queue.put(("log", f"Gespeichert in: {song_path}"))
            self.queue.put(("status", "Fertig"))
            self.queue.put(("done", True))
        except Exception as e:
            logging.getLogger(__name__).exception("Generierung fehlgeschlagen")
            self.queue.put(("log", f"\nFEHLER: {e}"))
            self.queue.put(("status", "Fehler"))
            self.queue.put(("done", False))
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)

    def poll_queue(self):
        """Checks the queue for incoming updates from the worker thread and updates the GUI."""
        finished = False
        success = False
        
        while True:
            try:
                msg_type, val = self.queue.get_nowait()
                if msg_type == "status":
                    self.view.set_status(val)
                elif msg_type == "log":
                    self.model.log_text = val
                elif msg_type == "progress":
                    self.view.set_progress(val)
                elif msg_type == "done":
                    finished = True
                    success = val
                self.queue.task_done()
            except queue.Empty:
                break
                
        if finished:
            self.generation_in_progress = False
            self.view.generate_btn.configure(state="normal", text="▶  SONG GENERIEREN")
            if success:
                messagebox.showinfo("✦ Erfolg ✦", f"Song wurde erfolgreich generiert!\n→ {self.last_song_path}")
            else:
                messagebox.showerror("Fehler", "Generierung fehlgeschlagen. Siehe Log.")
        else:
            # Reschedule queue polling
            self.view.after(100, self.poll_queue)
