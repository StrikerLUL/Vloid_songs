# controller.py - Controller for Vocaloid Music AI Generator Pro MVC
import queue
import threading
import time
import os
from tkinter import messagebox, TclError


class VocaloidController:
    """Controller that binds the VocaloidModel and VocaloidMainView, handles events, and manages background threads."""
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.queue = queue.Queue()
        self.generation_in_progress = False

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
        
        for inst in ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody"]:
            ctrls = self.view.instrumente_tab.controls[inst]
            ctrls["volume"].set(getattr(self.model, f"volume_{inst}"))
            ctrls["style"].set(getattr(self.model, f"style_{inst}"))
            ctrls["enabled"].set(getattr(self.model, f"enabled_{inst}"))
            
        for chan in ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody", "vocals", "master"]:
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
        for inst in ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody"]:
            ctrls = self.view.instrumente_tab.controls[inst]
            ctrls["volume"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_volume_changed(i))
            ctrls["style"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_style_changed(i))
            ctrls["enabled"].trace_add("write", lambda *a, i=inst: self.on_view_instrument_enabled_changed(i))
            
        # Mixer Tab
        for chan in ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody", "vocals", "master"]:
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
        """Executes the actual background generation process and pushes progress and logs to the thread queue."""
        import os
        from orchestrator import orchestrate_song
        from vocal_synthesizer import erstelle_musicxml, neutrino_synthese, generiere_lokale_vocals
        from mixer import midi_zu_wav, mische_spuren
        from exporter import exportiere_song
        
        try:
            # 1. Read parameters from model
            bpm = self.model.bpm
            key = self.model.key
            mode = self.model.scale
            style = self.model.style
            active_sections = self.model.active_sections
            lyrics_text = self.model.lyrics
            vocal_engine = self.model.vocal_engine
            singer = self.model.singer
            
            # Paths
            neutrino_path = self.model.neutrino_pfad
            soundfont_path = self.model.soundfont_pfad
            output_folder = self.model.output_ordner
            
            # Make output folder
            os.makedirs(output_folder, exist_ok=True)
            
            # Put start queue status/logs
            self.queue.put(("status", "Orchestriere Song..."))
            self.queue.put(("log", "[10%] Starte Song-Orchestrierung..."))
            self.queue.put(("progress", 0.1))
            
            # Section config template from config.py
            import config
            section_config = getattr(config, "SECTION_CONFIG", {})
            
            # 2. Orchestrate song
            tracks = orchestrate_song(
                genre=style,
                bpm=bpm,
                structure=active_sections,
                key=key,
                mode=mode,
                section_config=section_config
            )
            
            self.queue.put(("status", "Generiere Vocals..."))
            self.queue.put(("log", "[30%] Song-Orchestrierung abgeschlossen. Starte Vocal-Synthese..."))
            self.queue.put(("progress", 0.3))
            
            # 3. Vocals synthesis
            melody_data = tracks.get("melody_data", [])
            
            # Parse syllables from lyrics
            lyrics_sections = {"Verse": "", "Chorus": "", "PreChorus": "", "Bridge": ""}
            current_sec = None
            for line in lyrics_text.splitlines():
                line_strip = line.strip()
                if line_strip.lower() == "[verse]":
                    current_sec = "Verse"
                elif line_strip.lower() == "[chorus]":
                    current_sec = "Chorus"
                elif line_strip.lower() in ["[prechorus]", "[pre-chorus]"]:
                    current_sec = "PreChorus"
                elif line_strip.lower() == "[bridge]":
                    current_sec = "Bridge"
                elif line_strip.startswith("[") and line_strip.endswith("]"):
                    current_sec = None
                else:
                    if current_sec:
                        if lyrics_sections[current_sec]:
                            lyrics_sections[current_sec] += "\n" + line
                        else:
                            lyrics_sections[current_sec] = line
            
            # Reconstruct syllables sequence based on active_sections
            gesamte_silben = []
            for sec in active_sections:
                sec_type = "PreChorus" if sec in ["PreChorus", "Pre-Chorus"] else sec
                if sec_type in lyrics_sections and lyrics_sections[sec_type]:
                    sec_silben = [s for s in lyrics_sections[sec_type].split() if s]
                    gesamte_silben.extend(sec_silben)
            
            # Fallback if no syllables generated
            if not gesamte_silben:
                default_kana = "ほ し が き れ い な よ る に き み の こ え が き こ え る よ う な き が し た"
                gesamte_silben = default_kana.split()
                
            xml_pfad_vorgabe = os.path.join(output_folder, "vocals.xml")
            vocals_wav_path = os.path.join(output_folder, "vocals.wav")
            
            if len(melody_data) > 0 and len(gesamte_silben) > 0:
                xml_pfad = erstelle_musicxml(melody_data, gesamte_silben, bpm, xml_pfad_vorgabe)
                
                # Check vocal engine
                if vocal_engine == "NEUTRINO":
                    try:
                        self.queue.put(("log", "[40%] Synthetisiere mit NEUTRINO..."))
                        model_path = os.path.join(neutrino_path, "model", singer)
                        success = neutrino_synthese(xml_pfad, vocals_wav_path, neutrino_path, model_path)
                        if not success or not os.path.exists(vocals_wav_path):
                            raise Exception("NEUTRINO synthesis returned False or output file missing")
                    except Exception as e:
                        self.queue.put(("log", f"[WARN] NEUTRINO synthesis failed: {e}. Falling back to local synthesis..."))
                        generiere_lokale_vocals(melody_data, gesamte_silben, bpm, vocals_wav_path)
                else:
                    self.queue.put(("log", "[45%] Synthetisiere mit local TTS..."))
                    generiere_lokale_vocals(melody_data, gesamte_silben, bpm, vocals_wav_path)
            else:
                self.queue.put(("log", "[WARN] No melody data or syllables found. Skipping vocals synthesis."))
                if os.path.exists(vocals_wav_path):
                    try:
                        os.remove(vocals_wav_path)
                    except Exception:
                        pass
                        
            # 4. Instrument Rendering MIDI -> WAV
            self.queue.put(("status", "Rendere MIDI-Spuren..."))
            self.queue.put(("log", "[60%] Starte Rendering der MIDI-Spuren zu WAV..."))
            self.queue.put(("progress", 0.6))
            
            instruments = ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody"]
            spur_pfade = []
            lautstaerken = []
            
            volumes_map = {}
            panning_map = {}
            solos_map = {}
            mutes_map = {}
            
            for inst in instruments + ["vocals", "master"]:
                volumes_map[inst] = getattr(self.model, f"volume_{inst}")
                panning_map[inst] = getattr(self.model, f"pan_{inst}")
                solos_map[inst] = getattr(self.model, f"solo_{inst}")
                mutes_map[inst] = getattr(self.model, f"mute_{inst}")
            
            # Render active instruments
            for inst in instruments:
                mid_file = f"{inst}.mid"
                wav_file = f"{inst}.wav"
                mid_path = os.path.join(output_folder, mid_file)
                wav_path = os.path.join(output_folder, wav_file)
                
                is_enabled = getattr(self.model, f"enabled_{inst}", True)
                
                if is_enabled and inst in tracks and len(tracks[inst]) > 0:
                    self.queue.put(("log", f"[70%] Rendere {inst.upper()} zu WAV..."))
                    is_drum = (inst == "drums")
                    import config
                    config.SOUNDFONT_PFAD = soundfont_path
                    
                    midi_zu_wav(mid_path, wav_path, is_drum=is_drum, instrument_type=inst)
                    if os.path.exists(wav_path):
                        spur_pfade.append(wav_path)
                        lautstaerken.append(1.0)
                else:
                    if os.path.exists(wav_path):
                        try:
                            os.remove(wav_path)
                        except Exception:
                            pass
                            
            if os.path.exists(vocals_wav_path) and getattr(self.model, "enabled_vocals", True):
                spur_pfade.append(vocals_wav_path)
                lautstaerken.append(1.0)
                
            # 5. Mix & Master
            self.queue.put(("status", "Mische und Mastere..."))
            self.queue.put(("log", "[85%] Mische Spuren und wende Mastering an..."))
            self.queue.put(("progress", 0.85))
            
            final_mix_path = os.path.join(output_folder, "final_mix.wav")
            final_song_path = os.path.join(output_folder, "final_song.mp3")
            
            if len(spur_pfade) > 0:
                mische_spuren(
                    spur_pfade=spur_pfade,
                    lautstaerken=lautstaerken,
                    output_pfad=final_mix_path,
                    volumes=volumes_map,
                    panning=panning_map,
                    mutes=mutes_map,
                    solos=solos_map,
                    compressor_threshold=self.model.compressor_threshold,
                    compressor_ratio=self.model.compressor_ratio,
                    limiter_threshold=self.model.limiter_threshold
                )
                
                # Export final song to mp3
                self.queue.put(("status", "Exportiere Song..."))
                self.queue.put(("log", "[95%] Exportiere fertigen Song zu MP3..."))
                self.queue.put(("progress", 0.95))
                
                exportiere_song(
                    wav_pfad=final_mix_path,
                    mp3_pfad=final_song_path
                )
                
                self.queue.put(("log", "\n✦ Generierung erfolgreich abgeschlossen! ✦"))
                self.queue.put(("log", f"Gespeichert in: {final_song_path}"))
                self.queue.put(("status", "Fertig"))
                self.queue.put(("done", True))
            else:
                raise Exception("Keine Audiospuren zum Mischen vorhanden.")
                
        except Exception as e:
            self.queue.put(("log", f"\nERROR in background process: {str(e)}"))
            self.queue.put(("status", "Fehler"))
            self.queue.put(("done", False))

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
                messagebox.showinfo("✦ Erfolg ✦", "Song wurde erfolgreich generiert!\n→ output/final_song.mp3")
            else:
                messagebox.showerror("Fehler", "Generierung fehlgeschlagen. Siehe Log.")
        else:
            # Reschedule queue polling
            self.view.after(100, self.poll_queue)
