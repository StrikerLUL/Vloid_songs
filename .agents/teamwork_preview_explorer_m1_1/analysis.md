# Vocaloid Music AI Generator Pro GUI Overhaul Analysis and MVC Design

This report provides the analysis, architectural design, implementation details, and test strategy for overhauling the Vocaloid Music AI Generator Pro GUI into a modern, DAW-like interface using a clean Model-View-Controller (MVC) template.

---

## 1. GUI Environment & Library Verification

### 1.1 Automated Import Checking Code
Due to the headless, non-interactive execution environment, direct shell-based package querying was restricted. However, the following verification script is designed to check for available GUI libraries and their installation status. It should be run in the target environment:

```python
# check_gui_libs.py
import sys

def check_libraries():
    libraries = ["customtkinter", "PyQt6", "PySide6", "tkinter", "TkinterDnD2", "windnd"]
    results = {}
    
    print("=== Python Environment GUI Library Check ===")
    print(f"Python version: {sys.version}")
    print("-" * 44)
    
    for lib in libraries:
        try:
            __import__(lib)
            results[lib] = "Installed (Import OK)"
        except ImportError as e:
            results[lib] = f"Not Installed ({e})"
            
    for lib, status in results.items():
        print(f"{lib:<15}: {status}")
    print("============================================")

if __name__ == "__main__":
    check_libraries()
```

### 1.2 Library Status & Recommendations
* **`tkinter`**: **Installed** (built-in). The current interface (`gui.py`) is successfully written in standard tkinter.
* **`customtkinter`**: **Recommended**. It provides modern, dark-mode widgets with custom colors and shapes out of the box, preserving the core tkinter event loop and programming model. If not already installed, it must be added to `requirements.txt` (`customtkinter>=5.2.0`) and installed via:
  ```powershell
  pip install customtkinter
  ```
* **`PyQt6` / `PySide6`**: Excellent for large-scale enterprise desktop applications but introduces heavy dependency sizes, complex installation setups, and GPL/LGPL licensing constraints. Rewriting the entire application in Qt would require a complete redesign of the event loop, layouts, and widget bindings, posing a high regression risk for little added benefit compared to CustomTkinter.

---

## 2. GUI Framework Selection & Justification

We recommend **CustomTkinter** as the target GUI framework for the Vocaloid Music AI Generator Pro.

### 2.1 Justification Matrix

| Criteria | CustomTkinter | PyQt6 / PySide6 | Standard Tkinter |
| :--- | :--- | :--- | :--- |
| **Aesthetic Suitability** | Excellent. Native dark mode, modern flat controls, rounded corners, customizable neon accents. | Excellent. Fully customizable via Qt Style Sheets (QSS). | Poor. Outdated styling, hard-to-customize borders, system-dependent widget rendering. |
| **Migration Effort** | Low. Directly compatible with Tkinter variables, event loops, geometries (`grid`, `pack`), and bindings. | High. Requires complete rewrite of widgets, signals/slots, and layouts. | None. Already implemented, but fails DAW styling requirements. |
| **Footprint / Performance** | Mellow. Lightweight Python wrapper, fast startup, small installation size. | Heavy. Large package sizes (approx. 80-120MB), high memory usage. | Very Light. Built-in Python library. |
| **Licensing** | MIT (Permissive, open source). | GPL (PyQt6) / LGPL (PySide6). Strict commercial use clauses. | PSF License (Permissive). |
| **Threading Support** | Native integration with `root.after()` or virtual events. | Native QThread / QRunnable with Signals. | Native integration, but standard widgets look poor. |

### 2.2 Aesthetic Specifications
* **Background Theme**: Dark mode `#1a1a2e` (deep navy) and `#16213e`.
* **Accent Colors**: Pink/Magenta (`#e94560`) for primary buttons and high-energy sections; Purple (`#533483`) for headers and selection boundaries; Cyan (`#00e5ff`) for active sliders, indicators, and tooltips.
* **Typography**: Segoe UI / Arial for labels, and Consolas / Courier New for text editors and logs.

---

## 3. MVC Architecture Design

To ensure separation of concerns, testability, and modularity, the overhauled GUI will be organized under a clean MVC pattern.

```
vocaloid_generator/
│
├── main.py                    # Application entry point
├── model.py                   # VocaloidModel (state and settings)
├── controller.py              # VocaloidController (event handlers & thread coordination)
│
└── view/
    ├── __init__.py
    ├── main_view.py           # Main view manager (sidebar, tabs, progress bar)
    └── tabs.py                # Individual tab views (Dashboard, VocalsSynths, etc.)
```

### 3.1 MVC Component Responsibilities

1. **Model (`model.py`)**:
   * Contains only data and business logic.
   * Holds variables representing the GUI state: BPM, style, energy, key, scale, singer, engine, VST path, breathiness, swing, shimmer, active sections, lyrics, and log text.
   * Completely independent of the GUI framework (no imports of `tkinter` or `customtkinter`).
   * Provides getter/setter properties and a listener/observer pattern so the Controller can trigger UI updates when data changes.

2. **View (`view/main_view.py` & `view/tabs.py`)**:
   * Responsible only for visual layout and styling.
   * Subclasses CustomTkinter components (`CTk`, `CTkFrame`, etc.).
   * Does NOT make decisions, run music generation, or hold state variables.
   * Exposes methods for updating values (e.g., `set_progress(value)`, `append_log(text)`, `update_preset_controls(data)`).
   * Binds user events (button clicks, slider changes) to callbacks provided by the Controller.

3. **Controller (`controller.py`)**:
   * Mediates communication between the Model and the View.
   * Instantiates the Model and the View.
   * Listens to user interactions from the View, updates the Model, and synchronizes the View with Model changes.
   * Manages the non-blocking background thread for song generation.
   * Loads presets and pushes the parameters to the Model.

### 3.2 Event Flow (e.g., Generating a Song)

```
[User Clicks "Generate" in View]
           │
           ▼
[View executes callback: controller.handle_generate_click()]
           │
           ▼
[Controller validates input parameters via Model] ──(If Invalid)──► [Controller calls View: view.show_warning()]
           │
      (If Valid)
           │
           ▼
[Controller updates Model state: generation_active = True]
           │
           ├────────────────────────────────────────┐
           ▼                                        ▼
[Model fires listener event]           [Controller spawns Background Thread]
           │                                        │
           ▼                                        ▼
[View disables inputs & starts animations]  [Runs starte_generierung() asynchronously]
                                                    │
                                                    ▼
                                            [Periodic Progress Updates]
                                                    │
                                                    ▼
                                            [Controller writes progress to Queue]
                                                    │
                                                    ▼
                                            [View's after() loop polls Queue]
                                                    │
                                                    ▼
                                            [View updates ProgressBar & StatusLabel]
                                                    │
                                           (On Thread Complete)
                                                    │
                                                    ▼
                                            [Controller schedules finish() on main thread]
                                                    │
                                                    ▼
                                            [Controller updates Model: active = False]
                                                    │
                                                    ▼
                                            [View re-enables inputs & shows result dialog]
```

### 3.3 Detailed Class Layout

#### `model.py`
```python
class VocaloidModel:
    def __init__(self):
        # Parametric Fields
        self._bpm = 120
        self._style = "J-Pop Energy"
        self._energy = "Hoch"
        self._key = "C"
        self._mode = "minor"
        self._singer = "MERROW"
        self._vocal_engine = "NEUTRINO"
        self._vst_path = ""
        self._breathiness = 0.04
        self._swing = 0.0
        self._shimmer = False
        
        # Structure and Lyrics
        self._song_structure = ["Intro", "Verse", "Chorus", "Outro"]
        self._lyrics = {
            "Verse": "あいうえお",
            "PreChorus": "かきくけこ",
            "Chorus": "さしすせそ",
            "Bridge": "たちつてと"
        }
        
        # Generation State
        self.generation_active = False
        self.progress = 0.0
        self.status_message = "Ready"
        
        self._listeners = []

    def register_listener(self, callback):
        self._listeners.append(callback)

    def _notify(self, event_type, value):
        for callback in self._listeners:
            callback(event_type, value)

    # Properties with setters that notify listeners
    @property
    def bpm(self): return self._bpm
    @bpm.setter
    def bpm(self, val):
        self._bpm = int(val)
        self._notify("bpm", self._bpm)

    # (Repeat property declarations for other fields)
```

---

## 4. Key Feature Implementation Details

### 4.1 Custom Hover Tooltips (`view/widgets.py`)
To show popups explaining musical terms (like *BPM*, *Swing*, *Breathiness*, *Shimmer*) when hovering, we implement a custom borderless `HoverTooltip` window.

```python
import tkinter as tk
import customtkinter as ctk

class HoverTooltip:
    def __init__(self, widget, text, delay_ms=500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tooltip_window = None
        self.id = None
        
        # Bind events
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.unschedule()
        self.id = self.widget.after(self.delay_ms, self.show_tooltip)

    def leave(self, event=None):
        self.unschedule()
        self.hide_tooltip()

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show_tooltip(self):
        if self.tooltip_window:
            return
            
        # Get coordinates relative to screen
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create borderless toplevel window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # DAW style tooltip: dark background (#16213e) with cyan border (#00e5ff)
        frame = ctk.CTkFrame(
            self.tooltip_window, 
            fg_color="#16213e", 
            border_color="#00e5ff", 
            border_width=1,
            corner_radius=4
        )
        frame.pack(padx=1, pady=1)
        
        label = ctk.CTkLabel(
            frame, 
            text=self.text, 
            justify="left", 
            font=("Segoe UI", 9), 
            text_color="#eaeaea",
            padx=8,
            pady=4
        )
        label.pack()

    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
```

### 4.2 Drag-and-Drop VST3 Loader
To load `.vst3` files, we design a dual-layer strategy:
1. **Layer A**: Platform-independent file chooser binding.
2. **Layer B**: Direct drag-drop hooking using `windnd` (Windows-specific ctypes) which operates seamlessly without external Tcl library overlays.

```python
# In view/tabs.py or main_view.py
import os
import customtkinter as ctk
from tkinter import filedialog

class VSTDropArea(ctk.CTkFrame):
    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller
        
        # UI Styling
        self.configure(fg_color="#16213e", border_color="#533483", border_width=1, corner_radius=8)
        
        self.label = ctk.CTkLabel(
            self, 
            text="DRAG .vst3 FILE HERE\nor click to browse",
            font=("Segoe UI", 10, "bold"),
            text_color="#a8a8b3"
        )
        self.label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        # Clicks trigger browser
        self.bind("<Button-1>", self.browse_file)
        self.label.bind("<Button-1>", self.browse_file)
        
        # Register windnd hook if available (Windows OS only)
        try:
            import windnd
            windnd.hook_dropfiles(self, self.handle_dropped_files)
        except ImportError:
            # Fallback to Tcl/Tkdnd if preferred, or rely on browse fallback
            pass

    def browse_file(self, event=None):
        path = filedialog.askopenfilename(
            title="Select VST3 Synthesizer Plugin",
            filetypes=[("VST3 Plugins", "*.vst3"), ("All Files", "*.*")]
        )
        if path:
            self.controller.update_vst_path(path)

    def handle_dropped_files(self, files):
        if not files:
            return
        # Extract path (windnd returns paths as bytes or strings)
        file_path = files[0].decode('utf-8') if isinstance(files[0], bytes) else files[0]
        if file_path.endswith('.vst3'):
            self.controller.update_vst_path(file_path)
            self.label.configure(text=f"VST Loaded:\n{os.path.basename(file_path)}", text_color="#00e5ff")
        else:
            self.label.configure(text="Invalid File!\nOnly .vst3 supported", text_color="#e94560")
            self.after(2000, lambda: self.label.configure(text="DRAG .vst3 FILE HERE\nor click to browse", text_color="#a8a8b3"))
```

### 4.3 Non-Blocking Execution & Progress Bar
To keep the GUI responsive during heavy calculations (Neutrino invocation, track rendering, Pedalboard mixing), we run the backend logic in a separate thread. Communications utilize a thread-safe update queue.

```python
import queue
import threading
import customtkinter as ctk

class GenerationWorker:
    def __init__(self, controller):
        self.controller = controller
        self.update_queue = queue.Queue()
        self.is_running = False

    def start(self, generator_args):
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_job,
            args=(generator_args,),
            daemon=True
        )
        self.thread.start()

    def _run_job(self, args):
        try:
            # Connect the backend log function to push events to the queue
            def log_callback(message):
                # Parse steps for progress calculation
                progress = 0.0
                if "Vocal" in message: progress = 0.3
                elif "Rendering" in message: progress = 0.6
                elif "Mixing" in message: progress = 0.8
                elif "success" in message.lower(): progress = 1.0
                
                self.update_queue.put({"type": "progress", "value": progress, "text": message})

            # Call core generator logic
            from generator_logic import starte_generierung
            success = starte_generierung(log_callback, **args)
            
            self.update_queue.put({"type": "complete", "success": success})
        except Exception as e:
            self.update_queue.put({"type": "error", "error": str(e)})

# Inside the Controller:
def monitor_queue(self):
    try:
        while True:
            msg = self.worker.update_queue.get_nowait()
            if msg["type"] == "progress":
                self.view.update_progress(msg["value"], msg["text"])
            elif msg["type"] == "complete":
                self.handle_completion(msg["success"])
                return
            elif msg["type"] == "error":
                self.handle_error(msg["error"])
                return
    except queue.Empty:
        pass
    
    # Continue polling
    if self.worker.is_running:
        self.view.after(100, self.monitor_queue)
```

### 4.4 Preset Manager Configurations
Preset parameters are stored as static dictionaries mapping styles to Model attributes. Selecting a preset updates the Model, notifying the View to adjust its inputs automatically.

```python
PRESETS = {
    "J-Pop Energy": {
        "bpm": 160,
        "energy": "Hoch",
        "key": "A",
        "mode": "minor",
        "singer": "MERROW",
        "vocal_engine": "NEUTRINO",
        "breathiness": 0.04,
        "swing": 0.05,
        "shimmer": True,
        "song_structure": ["Intro", "Build-up", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]
    },
    "Rock": {
        "bpm": 120,
        "energy": "Hoch",
        "key": "E",
        "mode": "minor",
        "singer": "NAKUMO",
        "vocal_engine": "NEUTRINO",
        "breathiness": 0.08,
        "swing": 0.0,
        "shimmer": False,
        "song_structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]
    },
    "Ballade": {
        "bpm": 75,
        "energy": "Niedrig",
        "key": "C",
        "mode": "major",
        "singer": "RUNO",
        "vocal_engine": "NEUTRINO",
        "breathiness": 0.06,
        "swing": 0.0,
        "shimmer": True,
        "song_structure": ["Intro", "Verse", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]
    },
    "EDM": {
        "bpm": 128,
        "energy": "Maximal",
        "key": "G",
        "mode": "minor",
        "singer": "SOMA",
        "vocal_engine": "DIFFSINGER",
        "breathiness": 0.02,
        "swing": 0.12,
        "shimmer": False,
        "song_structure": ["Intro", "Verse", "PreChorus", "Chorus", "Chorus", "Outro"]
    }
}
```

---

## 5. Automated Test Strategy

To verify the overalled interface programmatically, we implement a testing suite in `vocaloid_generator/test_gui.py` using `unittest` and standard event loop updates without calling `mainloop()` (enabling headless testing compatibility).

### 5.1 Test Cases and Assertions

1. **Tab Layout Test**:
   * **Target**: Verify the sidebar tabs are fully loaded and selectable.
   * **Verification**: Instantiate the View. Assert that `tabview` exists and contains `"Dashboard"`, `"Vocals & Synths"`, `"Arrangement"`, and `"Lyrics"`. Programmatically change tabs and confirm active frames update.

2. **Non-Blocking Thread Test**:
   * **Target**: Verify the UI event loop remains active and responsive while generation is in progress.
   * **Verification**: Start generation from the Controller. Assert that the GUI remains interactive (e.g., `root.update()` does not block). Verify the progress bar state updates using mocked queue inputs.

3. **Tooltip Scheduling Test**:
   * **Target**: Verify that hovering over musical labels triggers tooltips.
   * **Verification**: Programmatically generate a `<Enter>` event on the "Breathiness" label. Assert that the tooltip's display callback is scheduled. Generate `<Leave>` and assert the tooltip gets destroyed or unscheduled.

4. **MVC Separation Test**:
   * **Target**: Strict boundary check.
   * **Verification**: Verify that importing `model.py` does not load `tkinter` or `customtkinter` modules (assertion: check `sys.modules`). Assert that modifying the Model fields updates corresponding values in the View widgets via the Controller.

---

## 6. Implementation Action Plan

1. **Phase 1: Dependencies & File Structure**:
   * Add `customtkinter` and `windnd` to `requirements.txt`.
   * Create `vocaloid_generator/model.py`, `vocaloid_generator/controller.py`, and the folder `vocaloid_generator/view/`.

2. **Phase 2: Component Implementation**:
   * Write `model.py` and implement properties.
   * Write `view/widgets.py` containing `HoverTooltip` and `VSTDropArea`.
   * Write `view/tabs.py` with individual frames.
   * Write `view/main_view.py` for core layout.
   * Write `controller.py` to glue pieces together.

3. **Phase 3: Integration**:
   * Update `vocaloid_generator/main.py` to launch the new MVC layout.
   * Integrate background workers and hook up generation progress.

4. **Phase 4: Verification**:
   * Implement and run the automated test suite `vocaloid_generator/test_gui.py`.
