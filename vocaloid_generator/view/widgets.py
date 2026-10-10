# view/widgets.py - Custom Widgets for Vocaloid Generator Pro MVC
import tkinter as tk
import customtkinter as ctk

class HoverTooltip:
    """Displays a borderless dark-mode frame with a cyan border explaining a musical term on hover."""
    def __init__(self, widget, text, delay=300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.id = None
        
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<ButtonPress>", self.hide)

    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self, event=None):
        self.unschedule()
        if self.tooltip_window:
            return
        
        # Place tooltip slightly offset from mouse or widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.configure(bg="#1a1a2e")
        
        # Border frame using cyan accent
        frame = ctk.CTkFrame(
            self.tooltip_window, 
            fg_color="#16213e", 
            border_color="#00f5d4", 
            border_width=1.5,
            corner_radius=4
        )
        frame.pack(fill="both", expand=True)
        
        label = ctk.CTkLabel(
            frame, 
            text=self.text, 
            text_color="#eaeaea", 
            justify="left", 
            font=("Segoe UI", 9),
            padx=8, 
            pady=4
        )
        label.pack(padx=2, pady=2)

    def hide(self, event=None):
        self.unschedule()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class VSTDropArea(ctk.CTkFrame):
    """Displays a drop area for .vst3 files with drag-and-drop or click fallback file browser."""
    def __init__(self, master, on_vst_selected_callback, **kwargs):
        # Default styling to match the deep dark DAW interface with neon pink/purple border
        super().__init__(
            master, 
            fg_color="#16213e", 
            border_color="#ff2a5f", 
            border_width=1, 
            corner_radius=6, 
            **kwargs
        )
        self.on_vst_selected = on_vst_selected_callback
        
        self.label = ctk.CTkLabel(
            self,
            text="🎵 Drag & Drop .vst3 file here\n- or -\nClick to Browse VST3 Plugin",
            text_color="#00f5d4",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=16,
            cursor="hand2"
        )
        self.label.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Bind click to file browser
        self.bind("<Button-1>", self._browse_file)
        self.label.bind("<Button-1>", self._browse_file)
        
        self._setup_drag_and_drop()

    def set_vst_path(self, path):
        """Update display when VST path changes."""
        if path:
            import os
            filename = os.path.basename(path)
            self.label.configure(
                text=f"✅ VST3 Loaded:\n{filename}\n\n(Click/Drop to replace)",
                text_color="#ff2a5f"
            )
        else:
            self.label.configure(
                text="🎵 Drag & Drop .vst3 file here\n- or -\nClick to Browse VST3 Plugin",
                text_color="#00f5d4"
            )

    def _browse_file(self, event=None):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Eigener VST3-Synth (.vst3) auswählen",
            filetypes=[("VST3 Plugins", "*.vst3"), ("Alle Dateien", "*.*")]
        )
        if path:
            self.on_vst_selected(path)

    def _setup_drag_and_drop(self):
        try:
            import windnd
            def on_drop(files):
                for f in files:
                    if isinstance(f, bytes):
                        path = f.decode('utf-8', errors='ignore')
                    else:
                        path = str(f)
                    if path.lower().endswith('.vst3'):
                        self.on_vst_selected(path)
                        break
            windnd.hook_dropfiles(self, on_drop)
        except (ImportError, Exception):
            pass
