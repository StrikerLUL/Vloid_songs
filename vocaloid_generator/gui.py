# gui.py – Vocaloid Generator Pro – Erweiterte GUI mit allen Reglern
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from generator_logic import starte_generierung
from config import (
    SONG_TEXT_VERSE, SONG_TEXT_CHORUS, SONG_TEXT_PRECHORUS, SONG_TEXT_BRIDGE,
    BPM, KEY, MODE, CHORD_STYLE, VOCAL_BREATHINESS, VOCAL_SHIMMER, SWING,
    SONG_STRUCTURE, SECTION_CONFIG,
)

# ── Farben (Dark Theme) ────────────────────────────────────────────────────────
BG        = "#1a1a2e"
BG2       = "#16213e"
BG3       = "#0f3460"
ACCENT    = "#e94560"
ACCENT2   = "#533483"
FG        = "#eaeaea"
FG2       = "#a8a8b3"
ENTRY_BG  = "#0d1b2a"

FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)


class VocaloidGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("✦ Vocaloid Music AI Generator Pro ✦")
        self.root.geometry("980x860")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        # ── Scrollbarer Hauptbereich ──────────────────────────────────────────
        outer = tk.Frame(root, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.main = tk.Frame(canvas, bg=BG, padx=18, pady=12)
        self.main_id = canvas.create_window((0, 0), window=self.main, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(self.main_id, width=canvas.winfo_width())
        self.main.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.main_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._build_ui()

    # ── Helper ─────────────────────────────────────────────────────────────────
    def _label(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", BG2), fg=kw.pop("fg", FG2),
                        font=kw.pop("font", FONT_LABEL), **kw)

    def _section_frame(self, title: str, color: str = BG2) -> tk.LabelFrame:
        f = tk.LabelFrame(
            self.main, text=f"  {title}  ",
            bg=color, fg=ACCENT, font=("Segoe UI", 10, "bold"),
            relief="flat", bd=2, padx=10, pady=8,
            highlightbackground=ACCENT2, highlightthickness=1,
        )
        f.pack(fill=tk.X, pady=6)
        return f

    def _combo(self, parent, var, values, width=14, **kw):
        cb = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width, **kw)
        cb.configure()
        return cb

    # ── UI aufbauen ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Titel
        tk.Label(
            self.main, text="✦  Vocaloid Music AI Generator Pro  ✦",
            font=("Segoe UI", 17, "bold"), bg=BG, fg=ACCENT
        ).pack(pady=(6, 14))

        self._build_song_settings()
        self._build_vocal_settings()
        self._build_structure_settings()
        self._build_lyrics()
        self._build_controls()
        self._build_log()

    # ── Song-Einstellungen ─────────────────────────────────────────────────────
    def _build_song_settings(self):
        f = self._section_frame("🎵 Song-Einstellungen")

        row1 = tk.Frame(f, bg=BG2)
        row1.pack(fill=tk.X, pady=4)

        # BPM
        self._label(row1, "Tempo (BPM):").pack(side=tk.LEFT)
        self.bpm_spin = tk.Spinbox(
            row1, from_=60, to=220, width=5,
            bg=ENTRY_BG, fg=FG, insertbackground=FG, relief="flat",
            font=FONT_LABEL
        )
        self.bpm_spin.delete(0, "end")
        self.bpm_spin.insert(0, str(BPM))
        self.bpm_spin.pack(side=tk.LEFT, padx=(4, 16))

        # Stil
        self._label(row1, "Stil:").pack(side=tk.LEFT)
        self.style_var = tk.StringVar(value="J-Pop Energy")
        self._combo(row1, self.style_var, [
            "J-Pop Energy", "Kawaii Chiptune", "Ballade", "Rock", "City Pop", "Dark Vocaloid"
        ], width=14).pack(side=tk.LEFT, padx=(4, 16))

        # Energie
        self._label(row1, "Energie:").pack(side=tk.LEFT)
        self.energy_var = tk.StringVar(value="Hoch")
        self._combo(row1, self.energy_var, ["Maximal", "Hoch", "Normal", "Niedrig"], width=10
                    ).pack(side=tk.LEFT, padx=4)

        row2 = tk.Frame(f, bg=BG2)
        row2.pack(fill=tk.X, pady=4)

        # Tonart
        self._label(row2, "Tonart:").pack(side=tk.LEFT)
        self.key_var = tk.StringVar(value=KEY)
        self._combo(row2, self.key_var,
                    ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
                    width=5).pack(side=tk.LEFT, padx=(4, 16))

        # Skala/Modus
        self._label(row2, "Skala:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=MODE)
        self._combo(row2, self.mode_var,
                    ["minor", "major", "dorian", "phrygian"],
                    width=10).pack(side=tk.LEFT, padx=(4, 16))

        # Sänger
        self._label(row2, "NEUTRINO Sänger:").pack(side=tk.LEFT)
        self.singer_var = tk.StringVar(value="MERROW")
        self._combo(row2, self.singer_var,
                    ["MERROW", "NAKUMO", "RUNO", "SOMA"],
                    width=10).pack(side=tk.LEFT, padx=4)

        # Row 3: VST3 & Engine
        row3 = tk.Frame(f, bg=BG2)
        row3.pack(fill=tk.X, pady=(6, 4))

        self._label(row3, "Vocal Engine:").pack(side=tk.LEFT)
        self.vocal_engine_var = tk.StringVar(value="NEUTRINO")
        self._combo(row3, self.vocal_engine_var, ["NEUTRINO", "OPENUTAU", "DIFFSINGER", "LOCAL"], width=12).pack(side=tk.LEFT, padx=(4, 16))

        self._label(row3, "Eigener VST3-Synth (.vst3):").pack(side=tk.LEFT)
        self.vst_path_var = tk.StringVar(value="")
        self.vst_entry = tk.Entry(
            row3, textvariable=self.vst_path_var, width=35,
            bg=ENTRY_BG, fg=FG, insertbackground=FG, relief="flat",
            font=FONT_LABEL
        )
        self.vst_entry.pack(side=tk.LEFT, padx=(4, 8), fill=tk.X, expand=True)

        tk.Button(
            row3, text="Durchsuchen...",
            command=self._select_vst,
            bg=BG3, fg=FG, font=FONT_SMALL, relief="flat", padx=8,
            activebackground=ACCENT2, activeforeground=FG, cursor="hand2"
        ).pack(side=tk.LEFT, padx=4)

        # Info-Label unter der VST-Zeile
        row_info = tk.Frame(f, bg=BG2)
        row_info.pack(fill=tk.X, pady=(2, 4))
        self._label(
            row_info,
            "💡 Tipp: Nutze VST3-Plugins wie Vital oder Surge XT für Studioqualität! Ohne VST greift der Fallback-Synth.",
            fg="#00e5ff", font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=4)

    def _select_vst(self):
        path = filedialog.askopenfilename(
            title="Eigener VST3-Synth (.vst3) auswählen",
            filetypes=[("VST3 Plugins", "*.vst3"), ("Alle Dateien", "*.*")]
        )
        if path:
            self.vst_path_var.set(path)
            self.log(f"VST3 geladen: {path}")

    # ── Vocal-Einstellungen ────────────────────────────────────────────────────
    def _build_vocal_settings(self):
        f = self._section_frame("🎤 Vocal-Einstellungen")

        row = tk.Frame(f, bg=BG2)
        row.pack(fill=tk.X, pady=4)

        # Breathiness Slider
        self._label(row, "Atemhaftigkeit:").pack(side=tk.LEFT)
        self.breath_var = tk.DoubleVar(value=VOCAL_BREATHINESS)
        breath_slider = tk.Scale(
            row, from_=0.0, to=0.12, resolution=0.005,
            orient=tk.HORIZONTAL, variable=self.breath_var,
            bg=BG2, fg=FG, troughcolor=BG3, highlightthickness=0,
            length=160, showvalue=True, font=FONT_SMALL
        )
        breath_slider.pack(side=tk.LEFT, padx=(4, 20))

        # Swing
        self._label(row, "Swing:").pack(side=tk.LEFT)
        self.swing_var = tk.DoubleVar(value=SWING)
        swing_slider = tk.Scale(
            row, from_=0.0, to=0.5, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.swing_var,
            bg=BG2, fg=FG, troughcolor=BG3, highlightthickness=0,
            length=160, showvalue=True, font=FONT_SMALL
        )
        swing_slider.pack(side=tk.LEFT, padx=(4, 20))

        # Shimmer Checkbox
        self.shimmer_var = tk.BooleanVar(value=VOCAL_SHIMMER)
        tk.Checkbutton(
            row, text="✨ Shimmer (Vocaloid-Effekt)",
            variable=self.shimmer_var,
            bg=BG2, fg=FG, selectcolor=BG3,
            activebackground=BG2, activeforeground=ACCENT,
            font=FONT_LABEL
        ).pack(side=tk.LEFT, padx=8)

    # ── Song-Struktur ──────────────────────────────────────────────────────────
    def _build_structure_settings(self):
        f = self._section_frame("🗂️ Song-Struktur")

        info = tk.Label(f, text="Wähle die Sektionen und ihre Reihenfolge:", bg=BG2, fg=FG2, font=FONT_SMALL)
        info.pack(anchor=tk.W, pady=(0, 6))

        # Checkboxen für Sektionen
        self.section_vars = {}
        checks_frame = tk.Frame(f, bg=BG2)
        checks_frame.pack(fill=tk.X)

        # Standard-Struktur: Intro Build-up Verse PreChorus Chorus Verse PreChorus Chorus Bridge Chorus Outro
        all_sections = ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Bridge", "Outro"]
        default_on   = {"Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Bridge", "Outro"}

        for i, sec in enumerate(all_sections):
            var = tk.BooleanVar(value=(sec in default_on))
            self.section_vars[sec] = var
            tk.Checkbutton(
                checks_frame, text=sec,
                variable=var, bg=BG2, fg=FG,
                selectcolor=BG3, activebackground=BG2, activeforeground=ACCENT,
                font=FONT_LABEL
            ).grid(row=0, column=i, padx=10, sticky=tk.W)

        # Presets
        preset_frame = tk.Frame(f, bg=BG2)
        preset_frame.pack(fill=tk.X, pady=(8, 0))
        self._label(preset_frame, "Schnell-Preset:").pack(side=tk.LEFT)

        presets = {
            "Standard": ["Intro","Build-up","Verse","PreChorus","Chorus","Verse","PreChorus","Chorus","Bridge","Chorus","Outro"],
            "Kurz":     ["Verse","Chorus","Verse","Chorus","Outro"],
            "Nur Chorus": ["Chorus","Chorus","Chorus"],
            "Ballade":  ["Intro","Verse","Verse","Chorus","Bridge","Chorus","Outro"],
        }
        self.preset_structure = presets  # Speichern für Callback

        for name, struct in presets.items():
            tk.Button(
                preset_frame, text=name,
                command=lambda s=struct: self._apply_preset(s),
                bg=BG3, fg=FG, relief="flat", padx=8,
                activebackground=ACCENT2, activeforeground=FG,
                font=FONT_SMALL, cursor="hand2"
            ).pack(side=tk.LEFT, padx=4)

    def _apply_preset(self, structure: list):
        """Setzt Checkboxen entsprechend dem Preset."""
        active_secs = set(structure)
        for sec, var in self.section_vars.items():
            var.set(sec in active_secs)
        self.log(f"Preset: {' → '.join(structure)}")

    def _get_song_structure(self) -> list:
        """Baut die Song-Struktur aus den Checkboxen."""
        # Standard-Reihenfolge
        template = ["Intro","Build-up","Verse","PreChorus","Chorus","Verse","PreChorus","Chorus","Bridge","Chorus","Outro"]
        return [s for s in template if self.section_vars.get(s, tk.BooleanVar()).get()]

    # ── Lyrics ─────────────────────────────────────────────────────────────────
    def _build_lyrics(self):
        f = self._section_frame("📝 Lyrics (Hiragana / Romaji)")

        sections_lyrics = [
            ("Verse",      SONG_TEXT_VERSE,     "verse_entry"),
            ("Pre-Chorus", SONG_TEXT_PRECHORUS, "prechorus_entry"),
            ("Chorus",     SONG_TEXT_CHORUS,    "chorus_entry"),
            ("Bridge",     SONG_TEXT_BRIDGE,    "bridge_entry"),
        ]

        for label_text, default, attr in sections_lyrics:
            tk.Label(f, text=f"{label_text}:", bg=BG2, fg=FG2, font=FONT_LABEL).pack(anchor=tk.W, pady=(4, 0))
            entry = tk.Text(
                f, height=2, width=80,
                bg=ENTRY_BG, fg=FG, insertbackground=FG,
                relief="flat", font=FONT_MONO,
                selectbackground=ACCENT2
            )
            entry.insert(tk.END, default)
            entry.pack(pady=(0, 4), fill=tk.X)
            setattr(self, attr, entry)

    # ── Start-Button ───────────────────────────────────────────────────────────
    def _build_controls(self):
        ctrl = tk.Frame(self.main, bg=BG)
        ctrl.pack(pady=10)

        self.start_btn = tk.Button(
            ctrl, text="▶  SONG GENERIEREN",
            command=self.run_generation,
            bg=ACCENT, fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat", padx=30, pady=10,
            activebackground="#c73652", activeforeground="white",
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.LEFT, padx=8)

        tk.Button(
            ctrl, text="🗑 Log leeren",
            command=self._clear_log,
            bg=BG3, fg=FG2, font=FONT_LABEL,
            relief="flat", padx=12, pady=10,
            activebackground=BG2, cursor="hand2"
        ).pack(side=tk.LEFT, padx=4)

    # ── Log ────────────────────────────────────────────────────────────────────
    def _build_log(self):
        tk.Label(self.main, text="Fortschritt:", bg=BG, fg=FG2, font=FONT_LABEL).pack(anchor=tk.W)
        self.log_area = scrolledtext.ScrolledText(
            self.main, height=12, width=90,
            state="disabled",
            bg=ENTRY_BG, fg="#00ff88",
            insertbackground=FG,
            font=FONT_MONO,
            relief="flat",
            selectbackground=ACCENT2
        )
        self.log_area.pack(pady=5, fill=tk.X)

    def log(self, message: str):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")
        self.root.update_idletasks()

    def _clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", tk.END)
        self.log_area.configure(state="disabled")

    # ── Generierung starten ────────────────────────────────────────────────────
    def run_generation(self):
        self.start_btn.configure(state="disabled", text="⏳  Generiere...")
        self.log("━" * 55)
        self.log("  Neuer Job gestartet")
        self.log("━" * 55)

        # Parameter auslesen
        v_text  = self.verse_entry.get("1.0",     tk.END).strip()
        pc_text = self.prechorus_entry.get("1.0",  tk.END).strip()
        c_text  = self.chorus_entry.get("1.0",    tk.END).strip()
        b_text  = self.bridge_entry.get("1.0",    tk.END).strip()

        try:
            bpm_val = int(self.bpm_spin.get())
        except ValueError:
            bpm_val = BPM

        structure = self._get_song_structure()
        if not structure:
            messagebox.showwarning("Warnung", "Keine Sektionen ausgewählt!")
            self.start_btn.configure(state="normal", text="▶  SONG GENERIEREN")
            return

        thread = threading.Thread(
            target=self._generation_thread,
            args=(v_text, pc_text, c_text, b_text, bpm_val, structure),
            daemon=True
        )
        thread.start()

    def _generation_thread(self, v, pc, c, b, bpm, structure):
        vst_pfad = self.vst_path_var.get().strip()
        vocal_eng = self.vocal_engine_var.get()
        success = starte_generierung(
            self.log,
            verse_text=v,
            prechorus_text=pc,
            chorus_text=c,
            bridge_text=b,
            bpm=bpm,
            style=self.style_var.get(),
            energy=self.energy_var.get(),
            singer=self.singer_var.get(),
            key=self.key_var.get(),
            mode=self.mode_var.get(),
            breathiness=self.breath_var.get(),
            shimmer=self.shimmer_var.get(),
            swing=self.swing_var.get(),
            song_structure=structure,
            vocal_engine=vocal_eng,
            vst_pfad=vst_pfad if vst_pfad else None,
        )

        def finish():
            self.start_btn.configure(state="normal", text="▶  SONG GENERIEREN")
            if success:
                messagebox.showinfo("✦ Erfolg ✦", "Song wurde erfolgreich generiert!\n→ output/final_song.mp3")
            else:
                messagebox.showerror("Fehler", "Generierung fehlgeschlagen. Siehe Log.")

        self.root.after(0, finish)


if __name__ == "__main__":
    root = tk.Tk()
    app = VocaloidGUI(root)
    root.mainloop()
