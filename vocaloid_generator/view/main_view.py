# view/main_view.py - Main Window Shell for Vocaloid Generator Pro MVC
import tkinter as tk
import customtkinter as ctk
from .tabs import SongTab, LyricsTab, InstrumenteTab, MixerTab, SettingsTab

class VocaloidMainView(ctk.CTk):
    """Main window integrating the sidebar navigator, tabs container, and bottom console controllers."""
    def __init__(self, on_generate_callback, on_vst_selected_callback, on_preset_clicked_callback, on_toggle_section_callback):
        super().__init__()
        
        self.title("✦ Vocaloid Music AI Generator Pro ✦")
        self.geometry("1200x900")
        self.configure(fg_color="#1a1a2e")
        
        # Configure overall grid structure
        self.grid_rowconfigure(0, weight=4)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Tab contents
        
        # Callbacks to Controller
        self.on_generate = on_generate_callback
        self.on_vst_selected = on_vst_selected_callback
        self.on_preset_clicked = on_preset_clicked_callback
        self.on_toggle_section = on_toggle_section_callback
        
        self._build_sidebar()
        self._build_content_area()
        self._build_bottom_panel()
        
        # Display Song tab by default
        self.show_tab("Song")

    def _build_sidebar(self):
        """Build Left Sidebar Navigation Panel."""
        self.sidebar = ctk.CTkFrame(
            self, 
            width=200, 
            fg_color="#16213e", 
            border_color="#533483", 
            border_width=1, 
            corner_radius=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_propagate(False)
        
        # Title Label
        title_lbl = ctk.CTkLabel(
            self.sidebar,
            text="VOCALOID AI PRO",
            font=("Segoe UI", 16, "bold"),
            text_color="#ff2a5f"
        )
        title_lbl.pack(pady=(20, 30))
        
        subtitle_lbl = ctk.CTkLabel(
            self.sidebar,
            text="DAW WORKSTATION",
            font=("Segoe UI", 8, "bold"),
            text_color="#00f5d4"
        )
        subtitle_lbl.pack(pady=(0, 20))
        
        # Navigation buttons
        self.nav_buttons = {}
        tab_names = ["Song", "Lyrics", "Instrumente", "Mixer", "Settings"]
        
        for name in tab_names:
            btn = ctk.CTkButton(
                self.sidebar,
                text=name,
                anchor="w",
                font=("Segoe UI", 11, "bold"),
                text_color="#eaeaea",
                fg_color="transparent",
                hover_color="#533483",
                height=40,
                corner_radius=4,
                command=lambda n=name: self.show_tab(n)
            )
            btn.pack(fill="x", padx=15, pady=8)
            self.nav_buttons[name] = btn

    def _build_content_area(self):
        """Build Main Content panel where tabs are packed."""
        self.content_container = ctk.CTkFrame(self, fg_color="#1a1a2e")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Instantiate the modular tab panels
        self.song_tab = SongTab(self.content_container, self.on_preset_clicked)
        self.lyrics_tab = LyricsTab(self.content_container)
        self.instrumente_tab = InstrumenteTab(self.content_container)
        self.mixer_tab = MixerTab(self.content_container)
        self.settings_tab = SettingsTab(self.content_container, on_vst_selected=self.on_vst_selected)

    def _build_bottom_panel(self):
        """Build Bottom Panel for generation controllers, progress bar, and log text window."""
        bottom_frame = ctk.CTkFrame(
            self, 
            fg_color="#16213e", 
            border_color="#533483", 
            border_width=1, 
            corner_radius=8
        )
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 15))
        
        bottom_frame.grid_columnconfigure(0, weight=2)
        bottom_frame.grid_columnconfigure(1, weight=3)
        bottom_frame.grid_rowconfigure(0, weight=1)
        
        # Column 0: Generation controllers
        ctrl_panel = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        ctrl_panel.grid(row=0, column=0, padx=20, pady=12, sticky="nsew")
        
        self.generate_btn = ctk.CTkButton(
            ctrl_panel,
            text="▶  SONG GENERIEREN",
            command=self.on_generate,
            font=("Segoe UI", 12, "bold"),
            text_color="#ffffff",
            fg_color="#ff2a5f",
            hover_color="#e94560",
            height=40
        )
        self.generate_btn.pack(fill="x", pady=(10, 5))
        
        # Progress & Status row
        prog_status_frame = ctk.CTkFrame(ctrl_panel, fg_color="transparent")
        prog_status_frame.pack(fill="x", pady=2)
        
        self.status_lbl = ctk.CTkLabel(
            prog_status_frame,
            text="Status: Bereit",
            text_color="#00f5d4",
            font=("Segoe UI", 10, "bold")
        )
        self.status_lbl.pack(side="left")
        
        self.progress_bar = ctk.CTkProgressBar(
            ctrl_panel,
            progress_color="#00f5d4",
            fg_color="#0d1b2a",
            height=12,
            corner_radius=4
        )
        self.progress_bar.pack(fill="x", pady=(2, 8))
        self.progress_bar.set(0.0)
        
        # Column 1: Log Console
        log_panel = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        log_panel.grid(row=0, column=1, padx=20, pady=12, sticky="nsew")
        
        log_header_frame = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_header_frame.pack(fill="x", pady=(0, 2))
        
        log_title = ctk.CTkLabel(
            log_header_frame,
            text="Output-Konsole:",
            text_color="#a8a8b3",
            font=("Segoe UI", 9, "bold")
        )
        log_title.pack(side="left")
        
        self.clear_log_btn = ctk.CTkButton(
            log_header_frame,
            text="Log leeren",
            command=self.clear_log,
            width=80,
            height=20,
            font=("Segoe UI", 8, "bold"),
            fg_color="#3a3e59",
            hover_color="#4a4e69"
        )
        self.clear_log_btn.pack(side="right")
        
        self.log_area = ctk.CTkTextbox(
            log_panel,
            fg_color="#0d1b2a",
            text_color="#00ff88",
            font=("Consolas", 9),
            border_color="#533483",
            border_width=1,
            corner_radius=6
        )
        self.log_area.pack(fill="both", expand=True)
        self.log_area.configure(state="disabled")

    def show_tab(self, name):
        """Switch between the 5 tab panels and highlight active navigation button."""
        # Unpack all tabs
        self.song_tab.pack_forget()
        self.lyrics_tab.pack_forget()
        self.instrumente_tab.pack_forget()
        self.mixer_tab.pack_forget()
        self.settings_tab.pack_forget()
        
        # Update navigation styles
        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color="#533483", border_color="#00f5d4", border_width=1)
            else:
                btn.configure(fg_color="transparent", border_width=0)
                
        # Repack active tab
        if name == "Song":
            self.song_tab.pack(fill="both", expand=True)
        elif name == "Lyrics":
            self.lyrics_tab.pack(fill="both", expand=True)
        elif name == "Instrumente":
            self.instrumente_tab.pack(fill="both", expand=True)
        elif name == "Mixer":
            self.mixer_tab.pack(fill="both", expand=True)
        elif name == "Settings":
            self.settings_tab.pack(fill="both", expand=True)

    def append_log(self, text):
        """Append a message to the console text area."""
        self.log_area.configure(state="normal")
        self.log_area.insert("end", text + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def clear_log(self):
        """Clear all messages from the log window."""
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

    def set_status(self, text):
        """Update status labels."""
        self.status_lbl.configure(text=f"Status: {text}")
        self.song_tab.status_lbl.configure(text=f"Status: {text}")

    def set_progress(self, value):
        """Set progress bars level (0.0 to 1.0)."""
        self.progress_bar.set(value)
        self.song_tab.progress_bar.set(value)
