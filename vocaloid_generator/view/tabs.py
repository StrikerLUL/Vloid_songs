# view/tabs.py - Tab Views for Vocaloid Generator Pro MVC
import tkinter as tk
import customtkinter as ctk
from settings import STYLE_OPTIONS

from .widgets import HoverTooltip, VSTDropArea

class SongTab(ctk.CTkFrame):
    """Song Tab: Key, mode, BPM inputs, structure reordering, preview player, progress bar."""
    def __init__(self, master, on_preset_clicked, **kwargs):
        super().__init__(master, fg_color="#1a1a2e", **kwargs)
        self.on_preset_clicked = on_preset_clicked
        
        # Outer container
        container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Grid structure for SongTab
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(1, weight=1) # Allow structure list to expand
        
        # Title
        lbl_title = ctk.CTkLabel(container, text="🎵 SONG GENERAL CONFIGURATION", font=("Segoe UI", 14, "bold"), text_color="#ff2a5f")
        lbl_title.grid(row=0, column=0, columnspan=2, pady=(15, 10), sticky="n")
        
        # Left column: Controls (BPM, Key, Mode, Preset, Preview Player)
        left_panel = ctk.CTkFrame(container, fg_color="transparent")
        left_panel.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # BPM
        lbl_bpm = ctk.CTkLabel(left_panel, text="Tempo (BPM):", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_bpm.pack(anchor="w", pady=(5, 2))
        self.bpm_var = tk.IntVar(value=160)
        self.bpm_spin = ctk.CTkEntry(left_panel, width=120, textvariable=self.bpm_var, fg_color="#0d1b2a", text_color="#eaeaea", border_color="#533483")
        self.bpm_spin.pack(anchor="w", pady=(0, 10))
        HoverTooltip(self.bpm_spin, "Beats per minute (Tempo)")
        
        # Key
        lbl_key = ctk.CTkLabel(left_panel, text="Tonart (Key):", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_key.pack(anchor="w", pady=(5, 2))
        self.key_var = tk.StringVar(value="A")
        self.key_opt = ctk.CTkOptionMenu(
            left_panel, variable=self.key_var,
            values=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
            fg_color="#0d1b2a", button_color="#533483", button_hover_color="#ff2a5f",
            dropdown_fg_color="#16213e", dropdown_text_color="#eaeaea", dropdown_hover_color="#533483", text_color="#eaeaea"
        )
        self.key_opt.pack(anchor="w", pady=(0, 10))
        
        # Mode / Scale
        lbl_scale = ctk.CTkLabel(left_panel, text="Modus (Mode):", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_scale.pack(anchor="w", pady=(5, 2))
        self.scale_var = tk.StringVar(value="minor")
        self.scale_opt = ctk.CTkOptionMenu(
            left_panel, variable=self.scale_var,
            values=["minor", "major", "dorian", "phrygian"],
            fg_color="#0d1b2a", button_color="#533483", button_hover_color="#ff2a5f",
            dropdown_fg_color="#16213e", dropdown_text_color="#eaeaea", dropdown_hover_color="#533483", text_color="#eaeaea"
        )
        self.scale_opt.pack(anchor="w", pady=(0, 10))
        
        # Preset Selector
        lbl_preset = ctk.CTkLabel(left_panel, text="Stil Preset:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_preset.pack(anchor="w", pady=(5, 2))
        self.preset_var = tk.StringVar(value="J-Pop Energy")
        self.preset_opt = ctk.CTkOptionMenu(
            left_panel, variable=self.preset_var,
            values=["J-Pop Energy", "Kawaii Chiptune", "Ballade", "Rock", "City Pop", "Dark Vocaloid"],
            command=self._preset_changed,
            fg_color="#0d1b2a", button_color="#533483", button_hover_color="#ff2a5f",
            dropdown_fg_color="#16213e", dropdown_text_color="#eaeaea", dropdown_hover_color="#533483", text_color="#eaeaea"
        )
        self.preset_opt.pack(anchor="w", pady=(0, 15))
        
        # Preview Player Frame
        play_frame = ctk.CTkFrame(left_panel, fg_color="#0d1b2a", border_color="#533483", border_width=1, corner_radius=6)
        play_frame.pack(fill="x", pady=10)
        
        lbl_player = ctk.CTkLabel(play_frame, text="🎧 PREVIEW PLAYER (final_mix.wav)", font=("Segoe UI", 9, "bold"), text_color="#00f5d4")
        lbl_player.pack(pady=5)
        
        btn_frame = ctk.CTkFrame(play_frame, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        self.btn_play = ctk.CTkButton(btn_frame, text="▶ Play", width=80, height=28, fg_color="#00f5d4", text_color="#1a1a2e", font=("Segoe UI", 9, "bold"), command=self.play_wav)
        self.btn_play.pack(side="left", padx=5)
        
        self.btn_stop = ctk.CTkButton(btn_frame, text="■ Stop", width=80, height=28, fg_color="#ff2a5f", text_color="#ffffff", font=("Segoe UI", 9, "bold"), command=self.stop_wav)
        self.btn_stop.pack(side="left", padx=5)
        
        # Progress & Status (inside tab)
        progress_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        progress_frame.pack(fill="x", pady=10)
        
        self.status_lbl = ctk.CTkLabel(progress_frame, text="Status: Bereit", text_color="#00f5d4", font=("Segoe UI", 10, "bold"))
        self.status_lbl.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, progress_color="#00f5d4", fg_color="#0d1b2a", height=12, corner_radius=4)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0.0)
        
        # Right column: Song Structure Reordering List
        right_panel = ctk.CTkFrame(container, fg_color="#0d1b2a", border_color="#533483", border_width=1, corner_radius=8)
        right_panel.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        
        lbl_struct = ctk.CTkLabel(right_panel, text="📋 SONGARRANGEMENT (Reihenfolge)", font=("Segoe UI", 10, "bold"), text_color="#a8a8b3")
        lbl_struct.pack(pady=(10, 5))
        
        # Scrollable container for the list of sections
        self.scroll_list = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Add section controls
        add_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=10)
        
        self.add_section_var = tk.StringVar(value="Chorus")
        self.add_section_opt = ctk.CTkOptionMenu(
            add_frame, variable=self.add_section_var,
            values=["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Bridge", "Outro"],
            fg_color="#16213e", button_color="#533483", text_color="#eaeaea", width=120
        )
        self.add_section_opt.pack(side="left", padx=(0, 5))
        
        btn_add = ctk.CTkButton(add_frame, text="+ Hinzufügen", fg_color="#533483", hover_color="#ff2a5f", text_color="#ffffff", width=90, font=("Segoe UI", 9, "bold"), command=self._add_section)
        btn_add.pack(side="left")
        
        self.on_structure_changed = None # Set by controller
        self.get_preview_path = None # Set by controller: returns the path of final_mix.wav
        self.structure_data = [] # Local copy of active sections structure list

    def _preset_changed(self, val):
        self.on_preset_clicked(val)

    def _add_section(self):
        sec = self.add_section_var.get()
        self.structure_data.append(sec)
        if self.on_structure_changed:
            self.on_structure_changed(list(self.structure_data))

    def _move_up(self, idx):
        if idx > 0:
            self.structure_data[idx], self.structure_data[idx-1] = self.structure_data[idx-1], self.structure_data[idx]
            if self.on_structure_changed:
                self.on_structure_changed(list(self.structure_data))

    def _move_down(self, idx):
        if idx < len(self.structure_data) - 1:
            self.structure_data[idx], self.structure_data[idx+1] = self.structure_data[idx+1], self.structure_data[idx]
            if self.on_structure_changed:
                self.on_structure_changed(list(self.structure_data))

    def _delete_section(self, idx):
        self.structure_data.pop(idx)
        if self.on_structure_changed:
            self.on_structure_changed(list(self.structure_data))

    def set_structure(self, structure):
        self.structure_data = list(structure)
        
        # Clear scroll list
        for widget in self.scroll_list.winfo_children():
            widget.destroy()
            
        # Draw rows
        sec_colors = {
            "Intro": "#9b5de5",       # Purple
            "Build-up": "#ff2a5f",    # Pink
            "Verse": "#00bbf9",       # Blue
            "PreChorus": "#00f5d4",   # Cyan
            "Chorus": "#f15bb5",      # Magenta
            "Bridge": "#fee440",      # Yellow
            "Outro": "#4a4e69"        # Dark Gray
        }
        
        for idx, sec in enumerate(self.structure_data):
            row_frame = ctk.CTkFrame(self.scroll_list, fg_color="#16213e", height=40)
            row_frame.pack(fill="x", pady=3)
            
            # Color block
            color = sec_colors.get(sec, "#533483")
            block = ctk.CTkFrame(row_frame, fg_color=color, width=15, height=30)
            block.pack(side="left", padx=5, pady=5)
            
            # Label
            lbl = ctk.CTkLabel(row_frame, text=f"{idx+1}. {sec}", font=("Segoe UI", 10, "bold"), text_color="#eaeaea")
            lbl.pack(side="left", padx=5)
            
            # Up, Down, Delete buttons
            btn_del = ctk.CTkButton(row_frame, text="✕", width=25, height=22, fg_color="#9e2a2b", hover_color="#ff2a5f", text_color="#ffffff", command=lambda i=idx: self._delete_section(i))
            btn_del.pack(side="right", padx=3)
            
            btn_down = ctk.CTkButton(row_frame, text="▼", width=25, height=22, fg_color="#3a3e59", hover_color="#533483", text_color="#eaeaea", command=lambda i=idx: self._move_down(i))
            btn_down.pack(side="right", padx=3)
            
            btn_up = ctk.CTkButton(row_frame, text="▲", width=25, height=22, fg_color="#3a3e59", hover_color="#533483", text_color="#eaeaea", command=lambda i=idx: self._move_up(i))
            btn_up.pack(side="right", padx=3)

    def play_wav(self):
        import os
        from tkinter import messagebox
        wav_path = self.get_preview_path() if self.get_preview_path else None
        if not wav_path or not os.path.exists(wav_path):
            messagebox.showinfo("Vorschau", "Noch kein Song vorhanden. Erst generieren, dann abspielen.")
            return
        try:
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            messagebox.showerror("Vorschau", f"Abspielen nicht möglich: {e}")

    def stop_wav(self):
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

class LyricsTab(ctk.CTkFrame):
    """Lyrics Tab: Section-by-section lyrics editor with syllable count."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#1a1a2e", **kwargs)
        
        container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        lbl_title = ctk.CTkLabel(container, text="📝 SONG LYRICS (SECTION EDITOR)", font=("Segoe UI", 14, "bold"), text_color="#ff2a5f")
        lbl_title.pack(pady=(15, 10))
        
        # Section selection
        selection_frame = ctk.CTkFrame(container, fg_color="transparent")
        selection_frame.pack(fill="x", padx=20, pady=5)
        
        lbl_sec = ctk.CTkLabel(selection_frame, text="Sektion auswählen:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_sec.pack(side="left", padx=(0, 10))
        
        self.section_var = tk.StringVar(value="Verse")
        self.section_opt = ctk.CTkOptionMenu(
            selection_frame, variable=self.section_var,
            values=["Verse", "PreChorus", "Chorus", "Bridge"],
            command=self._on_section_selected,
            fg_color="#0d1b2a", button_color="#533483", text_color="#eaeaea"
        )
        self.section_opt.pack(side="left")
        
        # Info & Syllable Count
        self.info_lbl = ctk.CTkLabel(selection_frame, text="Silbenanzahl: 0", text_color="#00f5d4", font=("Segoe UI", 10, "bold"))
        self.info_lbl.pack(side="right")
        
        # Lyrics Textbox
        self.lyrics_box = ctk.CTkTextbox(
            container, fg_color="#0d1b2a", text_color="#eaeaea",
            border_color="#533483", border_width=1, font=("Consolas", 10), corner_radius=6
        )
        self.lyrics_box.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.lyrics_box.bind("<KeyRelease>", self._on_key_release)
        
        # Local sections dictionary
        self.sections_lyrics = {"Verse": "", "PreChorus": "", "Chorus": "", "Bridge": ""}
        self.on_lyrics_changed = None # Set by controller to receive rebuilt lyrics

    def _on_section_selected(self, val):
        self.lyrics_box.delete("1.0", "end")
        self.lyrics_box.insert("1.0", self.sections_lyrics.get(val, ""))
        self._update_syllables()

    def _on_key_release(self, event=None):
        val = self.section_var.get()
        self.sections_lyrics[val] = self.lyrics_box.get("1.0", "end-1c")
        self._update_syllables()
        if self.on_lyrics_changed:
            rebuilt = self._rebuild_lyrics()
            self.on_lyrics_changed(rebuilt)

    def _update_syllables(self):
        text = self.lyrics_box.get("1.0", "end-1c").strip()
        syllables = len([s for s in text.split() if s]) if text else 0
        self.info_lbl.configure(text=f"Silbenanzahl (Syllable Count): {syllables}")

    def _rebuild_lyrics(self):
        text = ""
        if self.sections_lyrics.get("Verse"):
            text += f"[Verse]\n{self.sections_lyrics['Verse']}\n\n"
        if self.sections_lyrics.get("PreChorus"):
            text += f"[PreChorus]\n{self.sections_lyrics['PreChorus']}\n\n"
        if self.sections_lyrics.get("Chorus"):
            text += f"[Chorus]\n{self.sections_lyrics['Chorus']}\n\n"
        if self.sections_lyrics.get("Bridge"):
            text += f"[Bridge]\n{self.sections_lyrics['Bridge']}\n\n"
        return text.strip()

    def get_lyrics(self):
        return self._rebuild_lyrics()

    def set_lyrics(self, text):
        # Parse full text into sections
        sections = {"Verse": "", "Chorus": "", "PreChorus": "", "Bridge": ""}
        current_sec = None
        for line in text.splitlines():
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
                    if sections[current_sec]:
                        sections[current_sec] += "\n" + line
                    else:
                        sections[current_sec] = line
        
        self.sections_lyrics = sections
        # Reload current section
        val = self.section_var.get()
        self.lyrics_box.delete("1.0", "end")
        self.lyrics_box.insert("1.0", self.sections_lyrics.get(val, ""))
        self._update_syllables()

class InstrumenteTab(ctk.CTkFrame):
    """Instrumente Tab: Volume, style/pattern, and enabled state per instrument."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#1a1a2e", **kwargs)
        
        container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        lbl_title = ctk.CTkLabel(container, text="🎺 INSTRUMENT PRESET & VOLUME ROUTING", font=("Segoe UI", 14, "bold"), text_color="#ff2a5f")
        lbl_title.pack(pady=(15, 10))
        
        # Grid frame
        grid_frame = ctk.CTkFrame(container, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        for r in range(4):
            grid_frame.grid_rowconfigure(r, weight=1)
            
        instruments = ["Piano", "Bass", "Guitar", "Strings", "Synth", "Brass", "Drums", "Melody"]
        
        # Spielweisen pro Instrument kommen aus dem Einstellungs-Modell
        self.style_options = {inst: list(STYLE_OPTIONS[inst.lower()]) for inst in instruments}
        
        self.controls = {}
        
        for idx, inst in enumerate(instruments):
            row = idx % 4
            col = idx // 4
            
            card = ctk.CTkFrame(grid_frame, fg_color="#0d1b2a", border_color="#3a3e59", border_width=1, corner_radius=6)
            card.grid(row=row, column=col, padx=10, pady=5, sticky="nsew")
            
            # Header row: Enabled checkbox + Title
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=5)
            
            en_var = tk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(header, text=inst.upper(), variable=en_var, font=("Segoe UI", 11, "bold"), text_color="#eaeaea", fg_color="#533483", border_color="#00f5d4")
            cb.pack(side="left")
            
            # Controls row (Volume slider & Style option)
            ctrl_row = ctk.CTkFrame(card, fg_color="transparent")
            ctrl_row.pack(fill="x", padx=10, pady=(0, 5))
            
            lbl_vol = ctk.CTkLabel(ctrl_row, text="Vol:", text_color="#a8a8b3", font=("Segoe UI", 9, "bold"))
            lbl_vol.pack(side="left", padx=(0, 5))
            
            vol_var = tk.DoubleVar(value=0.8)
            slider = ctk.CTkSlider(ctrl_row, from_=0.0, to=1.0, variable=vol_var, width=120, button_color="#00f5d4", progress_color="#533483")
            slider.pack(side="left", padx=5)
            
            lbl_style = ctk.CTkLabel(ctrl_row, text="Stil:", text_color="#a8a8b3", font=("Segoe UI", 9, "bold"))
            lbl_style.pack(side="left", padx=(10, 5))
            
            style_var = tk.StringVar(value="default")
            opt = ctk.CTkOptionMenu(
                ctrl_row, variable=style_var,
                values=self.style_options[inst],
                width=100, height=22, fg_color="#16213e", button_color="#3a3e59", text_color="#eaeaea"
            )
            opt.pack(side="left")
            
            self.controls[inst.lower()] = {
                "enabled": en_var,
                "volume": vol_var,
                "style": style_var
            }

class MixerTab(ctk.CTkFrame):
    """Mixer Tab: Vertical faders, panning, solo/mute buttons for all instruments + master compressor & limiter."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#1a1a2e", **kwargs)
        
        # Split layout: Top (Faders), Bottom (Master FX)
        self.grid_rowconfigure(0, weight=4)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Faders container
        faders_container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        faders_container.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        
        lbl_title = ctk.CTkLabel(faders_container, text="🎚️ DAW PROFESSIONAL MIXING DESK", font=("Segoe UI", 12, "bold"), text_color="#ff2a5f")
        lbl_title.pack(pady=8)
        
        faders_frame = ctk.CTkFrame(faders_container, fg_color="transparent")
        faders_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        channels = ["piano", "bass", "guitar", "strings", "synth", "brass", "drums", "melody", "vocals", "master"]
        
        for c in range(10):
            faders_frame.grid_columnconfigure(c, weight=1)
            
        self.channels_controls = {}
        
        for idx, chan in enumerate(channels):
            chan_strip = ctk.CTkFrame(faders_frame, fg_color="#0d1b2a", border_color="#3a3e59", border_width=1, corner_radius=4)
            chan_strip.grid(row=0, column=idx, padx=4, pady=5, sticky="nsew")
            
            # Label
            lbl = ctk.CTkLabel(chan_strip, text=chan.upper(), font=("Segoe UI", 9, "bold"), text_color="#00f5d4" if chan in ["vocals", "master"] else "#eaeaea")
            lbl.pack(pady=5)
            
            # Fader (Vertical Slider)
            vol_var = tk.DoubleVar(value=0.8 if chan not in ["vocals", "master"] else 1.0)
            fader = ctk.CTkSlider(chan_strip, from_=0.0, to=1.0, variable=vol_var, orientation="vertical", width=20, height=220, button_color="#00f5d4", progress_color="#533483")
            fader.pack(pady=10)
            
            # Pan Slider (Horizontal)
            lbl_pan = ctk.CTkLabel(chan_strip, text="PAN", font=("Segoe UI", 8), text_color="#a8a8b3")
            lbl_pan.pack()
            
            pan_var = tk.DoubleVar(value=0.0)
            pan_slider = ctk.CTkSlider(chan_strip, from_=-1.0, to=1.0, variable=pan_var, height=12, width=70, button_color="#533483", progress_color="#3a3e59")
            pan_slider.pack(pady=2)
            
            # Solo & Mute buttons
            btn_frame = ctk.CTkFrame(chan_strip, fg_color="transparent")
            btn_frame.pack(pady=5)
            
            solo_var = tk.BooleanVar(value=False)
            mute_var = tk.BooleanVar(value=False)
            
            btn_s = ctk.CTkButton(
                btn_frame, text="S", width=26, height=20, fg_color="#3a3e59", text_color="#eaeaea", font=("Segoe UI", 9, "bold"),
                command=lambda ch=chan: self._toggle_solo(ch)
            )
            btn_s.pack(side="left", padx=2)
            
            btn_m = ctk.CTkButton(
                btn_frame, text="M", width=26, height=20, fg_color="#3a3e59", text_color="#eaeaea", font=("Segoe UI", 9, "bold"),
                command=lambda ch=chan: self._toggle_mute(ch)
            )
            btn_m.pack(side="left", padx=2)
            
            self.channels_controls[chan] = {
                "volume": vol_var,
                "pan": pan_var,
                "solo": solo_var,
                "mute": mute_var,
                "btn_solo": btn_s,
                "btn_mute": btn_m
            }
            
        # Bottom panel: Master FX Settings
        fx_container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        fx_container.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        lbl_fx_title = ctk.CTkLabel(fx_container, text="🎛️ MASTER EFFECTS (COMPRESSOR & LIMITER)", font=("Segoe UI", 11, "bold"), text_color="#ff2a5f")
        lbl_fx_title.pack(pady=(5, 5))
        
        fx_grid = ctk.CTkFrame(fx_container, fg_color="transparent")
        fx_grid.pack(fill="x", expand=True, padx=20, pady=5)
        
        fx_grid.grid_columnconfigure(0, weight=1)
        fx_grid.grid_columnconfigure(1, weight=1)
        fx_grid.grid_columnconfigure(2, weight=1)
        
        # 1. Compressor Threshold
        f0 = ctk.CTkFrame(fx_grid, fg_color="transparent")
        f0.grid(row=0, column=0, sticky="nsew")
        lbl_c_thresh = ctk.CTkLabel(f0, text="Compressor Threshold (dB):", text_color="#a8a8b3", font=("Segoe UI", 9, "bold"))
        lbl_c_thresh.pack(anchor="w")
        self.comp_thresh_var = tk.DoubleVar(value=-20.0)
        self.comp_thresh_slider = ctk.CTkSlider(f0, from_=-60.0, to=0.0, variable=self.comp_thresh_var, button_color="#00f5d4", progress_color="#533483")
        self.comp_thresh_slider.pack(fill="x", pady=5)
        
        # 2. Compressor Ratio
        f1 = ctk.CTkFrame(fx_grid, fg_color="transparent")
        f1.grid(row=0, column=1, sticky="nsew", padx=20)
        lbl_c_ratio = ctk.CTkLabel(f1, text="Compressor Ratio:", text_color="#a8a8b3", font=("Segoe UI", 9, "bold"))
        lbl_c_ratio.pack(anchor="w")
        self.comp_ratio_var = tk.DoubleVar(value=2.0)
        self.comp_ratio_slider = ctk.CTkSlider(f1, from_=1.0, to=20.0, variable=self.comp_ratio_var, button_color="#00f5d4", progress_color="#533483")
        self.comp_ratio_slider.pack(fill="x", pady=5)
        
        # 3. Limiter Threshold
        f2 = ctk.CTkFrame(fx_grid, fg_color="transparent")
        f2.grid(row=0, column=2, sticky="nsew")
        lbl_l_thresh = ctk.CTkLabel(f2, text="Limiter Threshold (dB):", text_color="#a8a8b3", font=("Segoe UI", 9, "bold"))
        lbl_l_thresh.pack(anchor="w")
        self.lim_thresh_var = tk.DoubleVar(value=-0.3)
        self.lim_thresh_slider = ctk.CTkSlider(f2, from_=-20.0, to=0.0, variable=self.lim_thresh_var, button_color="#ff2a5f", progress_color="#533483")
        self.lim_thresh_slider.pack(fill="x", pady=5)

    def _toggle_solo(self, chan):
        ctrls = self.channels_controls[chan]
        new_val = not ctrls["solo"].get()
        ctrls["solo"].set(new_val)
        if new_val:
            ctrls["btn_solo"].configure(fg_color="#00f5d4", text_color="#1a1a2e")
        else:
            ctrls["btn_solo"].configure(fg_color="#3a3e59", text_color="#eaeaea")
            
    def _toggle_mute(self, chan):
        ctrls = self.channels_controls[chan]
        new_val = not ctrls["mute"].get()
        ctrls["mute"].set(new_val)
        if new_val:
            ctrls["btn_mute"].configure(fg_color="#ff2a5f", text_color="#ffffff")
        else:
            ctrls["btn_mute"].configure(fg_color="#3a3e59", text_color="#eaeaea")

class SettingsTab(ctk.CTkFrame):
    """Settings Tab: Configure file paths and Humanizer swing/jitter parameters."""
    def __init__(self, master, on_vst_selected=None, **kwargs):
        super().__init__(master, fg_color="#1a1a2e", **kwargs)
        
        container = ctk.CTkFrame(self, fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=2)
        
        lbl_title = ctk.CTkLabel(container, text="⚙️ SYSTEM CONFIGURATION & ENSEMBLING Settings", font=("Segoe UI", 14, "bold"), text_color="#ff2a5f")
        lbl_title.grid(row=0, column=0, columnspan=2, pady=(15, 20), sticky="n")
        
        # 1. NEUTRINO Path
        lbl_neu = ctk.CTkLabel(container, text="NEUTRINO Pfad:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_neu.grid(row=1, column=0, padx=20, pady=10, sticky="e")
        
        p_frame1 = ctk.CTkFrame(container, fg_color="transparent")
        p_frame1.grid(row=1, column=1, padx=20, pady=10, sticky="w")
        self.neutrino_path_var = tk.StringVar()
        self.entry_neu = ctk.CTkEntry(p_frame1, textvariable=self.neutrino_path_var, width=320, fg_color="#0d1b2a", text_color="#eaeaea", border_color="#533483")
        self.entry_neu.pack(side="left")
        self.btn_neu = ctk.CTkButton(p_frame1, text="Durchsuchen...", width=90, fg_color="#533483", hover_color="#ff2a5f", command=self._browse_neutrino)
        self.btn_neu.pack(side="left", padx=5)
        
        # 2. SOUNDFONT Path
        lbl_sf = ctk.CTkLabel(container, text="SoundFont (.sf2) Pfad:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_sf.grid(row=2, column=0, padx=20, pady=10, sticky="e")
        
        p_frame2 = ctk.CTkFrame(container, fg_color="transparent")
        p_frame2.grid(row=2, column=1, padx=20, pady=10, sticky="w")
        self.soundfont_path_var = tk.StringVar()
        self.entry_sf = ctk.CTkEntry(p_frame2, textvariable=self.soundfont_path_var, width=320, fg_color="#0d1b2a", text_color="#eaeaea", border_color="#533483")
        self.entry_sf.pack(side="left")
        self.btn_sf = ctk.CTkButton(p_frame2, text="Durchsuchen...", width=90, fg_color="#533483", hover_color="#ff2a5f", command=self._browse_soundfont)
        self.btn_sf.pack(side="left", padx=5)
        
        # 3. OUTPUT Directory
        lbl_out = ctk.CTkLabel(container, text="Output Ordner:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_out.grid(row=3, column=0, padx=20, pady=10, sticky="e")
        
        p_frame3 = ctk.CTkFrame(container, fg_color="transparent")
        p_frame3.grid(row=3, column=1, padx=20, pady=10, sticky="w")
        self.output_dir_var = tk.StringVar()
        self.entry_out = ctk.CTkEntry(p_frame3, textvariable=self.output_dir_var, width=320, fg_color="#0d1b2a", text_color="#eaeaea", border_color="#533483")
        self.entry_out.pack(side="left")
        self.btn_out = ctk.CTkButton(p_frame3, text="Durchsuchen...", width=90, fg_color="#533483", hover_color="#ff2a5f", command=self._browse_output)
        self.btn_out.pack(side="left", padx=5)
        
        # 4. Humanizer Swing
        lbl_swing = ctk.CTkLabel(container, text="Humanizer Swing:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_swing.grid(row=4, column=0, padx=20, pady=12, sticky="e")
        self.swing_var = tk.DoubleVar(value=0.12)
        self.swing_slider = ctk.CTkSlider(container, from_=0.0, to=0.5, variable=self.swing_var, width=280, button_color="#00f5d4", progress_color="#533483")
        self.swing_slider.grid(row=4, column=1, padx=20, pady=12, sticky="w")
        
        # 5. Humanizer Jitter
        lbl_jitter = ctk.CTkLabel(container, text="Timing-Streuung (0.02 = Genre-Standard):", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_jitter.grid(row=5, column=0, padx=20, pady=12, sticky="e")
        self.jitter_var = tk.DoubleVar(value=0.02)
        self.jitter_slider = ctk.CTkSlider(container, from_=0.0, to=0.1, variable=self.jitter_var, width=280, button_color="#00f5d4", progress_color="#533483")
        self.jitter_slider.grid(row=5, column=1, padx=20, pady=12, sticky="w")

        # 6. Eigener VST3-Synth für Synth- und Melodie-Spur
        lbl_vst = ctk.CTkLabel(container, text="Eigener VST3-Synth:", text_color="#a8a8b3", font=("Segoe UI", 10, "bold"))
        lbl_vst.grid(row=6, column=0, padx=20, pady=12, sticky="ne")
        self.vst_area = VSTDropArea(container, on_vst_selected or (lambda path: None))
        self.vst_area.grid(row=6, column=1, padx=20, pady=12, sticky="w")
        HoverTooltip(self.vst_area, "Wird für die Synth- und Melodie-Spur genutzt, z. B. Surge XT.")

    def _browse_neutrino(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="NEUTRINO Ordner auswählen")
        if path:
            self.neutrino_path_var.set(path)
            
    def _browse_soundfont(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="SoundFont (.sf2) auswählen", filetypes=[("SoundFont Files", "*.sf2"), ("All Files", "*.*")])
        if path:
            self.soundfont_path_var.set(path)
            
    def _browse_output(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Output Ordner auswählen")
        if path:
            self.output_dir_var.set(path)
