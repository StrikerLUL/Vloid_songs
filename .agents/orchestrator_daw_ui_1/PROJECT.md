# Project: Vocaloid Music AI Generator Pro GUI Overhaul

## Architecture
We are overhauling the existing tkinter-based GUI to a professional DAW-like interface using CustomTkinter under the Model-View-Controller (MVC) pattern.

```
+---------------+      Registers      +-------------+
|               | ------------------► |             |
|     View      |                     | Controller  |
| (customtkinter| ◄------------------ |             |
+---------------+   Updates widgets   +-------------+
        ▲                                    │
        │ Binds                              │ Updates state
        │ events                             ▼
+---------------+                     +-------------+
|  Controller   |                     |    Model    |
| (coordinates) |                     | (pure state)|
+---------------+                     +-------------+
```

### Module Breakdown
- `vocaloid_generator/model.py`: Pure state holder, independent of tkinter/customtkinter, triggers observer callbacks when fields are updated.
- `vocaloid_generator/view/widgets.py`: Houses custom GUI widgets: `HoverTooltip` for hover tooltips, `VSTDropArea` for drag-and-drop vst3 file loader.
- `vocaloid_generator/view/tabs.py`: Defines the visual layouts for the four tabs (Dashboard, Vocals & Synths, Arrangement, Lyrics).
- `vocaloid_generator/view/main_view.py`: Configures the main window grid layout, side navigation bar (switching tabs), animated progress bar, status bar, and logs.
- `vocaloid_generator/controller.py`: Instantiates model/view, binds events, manages non-blocking background workers, handles preset transitions.
- `vocaloid_generator/gui_mvc.py`: Launch script for running the new MVC GUI application.
- `vocaloid_generator/test_gui.py`: Automated programmatic tests checking tab presence, non-blocking background execution, tooltip scheduling, and MVC separation.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Architecture & Design | MVC class diagrams, folder layout, framework decision | none | DONE |
| 2 | Component & View Layout | Implement CustomTkinter views, tabs, tooltip bindings, VST drop area | M1 | PLANNED |
| 3 | Controller & Threading | MVC state flow bindings, preset loading, non-blocking background execution with thread-safe queue | M2 | PLANNED |
| 4 | Verification Suite | Automated tests for GUI verification and Forensic Auditor validation | M3 | PLANNED |

## Interface Contracts
- **View Events**: View exposes widgets and explicit registration methods (e.g. `set_generate_callback(handler)`) for the Controller to hook into.
- **Model State Updates**: Model registers callbacks (`register_listener(cb)`) and calls them with key/value pairs whenever properties change.
- **Background Worker**: Worker outputs status/progress dicts to a thread-safe `queue.Queue`. View schedules periodic polling via `.after(100, monitor)` to update the progress bar.
- **Fallback Safety**: VSTDropArea falls back to `filedialog.askopenfilename` click-to-browse if `windnd` is not importable.

## Code Layout
- `vocaloid_generator/model.py`
- `vocaloid_generator/controller.py`
- `vocaloid_generator/view/`
  - `vocaloid_generator/view/__init__.py`
  - `vocaloid_generator/view/main_view.py`
  - `vocaloid_generator/view/tabs.py`
  - `vocaloid_generator/view/widgets.py`
- `vocaloid_generator/gui_mvc.py`
- `vocaloid_generator/test_gui.py`
