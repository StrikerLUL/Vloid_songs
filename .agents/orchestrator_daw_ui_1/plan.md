# Plan - Vocaloid Music AI Generator Pro UI Overhaul

## Goal
Implement a complete UI/UX overhaul of the Vocaloid Music AI Generator Pro from tkinter to a professional DAW-like interface using CustomTkinter, adhering strictly to the Model-View-Controller (MVC) pattern. Ensure background tasks are run in non-blocking threads with an animated progress bar and status indicators, custom tooltips, a preset manager, drag-and-drop support, and modularized code.

## Milestones

### Milestone 1: Analysis and Design
- **Objective**: Assess the existing tkinter code in `gui.py` and other modules to map out the required controls and parameters. Determine the detailed MVC structure and layout of the DAW view.
- **Verification**: Code review of the existing tkinter interface, proposed MVC module files, and draft UI layout plan.

### Milestone 2: Implementation of the DAW View (CustomTkinter)
- **Objective**: Create the core View components. Construct a professional dark mode interface with neon accents (#1a1a2e bg with pink/purple/cyan accents), featuring a sidebar/tab navigation with 4 tabs:
  1. Dashboard (BPM, Style, Energy, Key)
  2. Vocals & Synths (NEUTRINO singers, VST3 selection, Breathiness, Swing)
  3. Arrangement (Visual timeline or movable blocks for structure)
  4. Lyrics (Clean editor)
- **Features**: Implement custom tooltips for musical terms, file Drag-and-Drop support for `.vst3` loading, and progress indicators/animations.
- **Verification**: Reviewer checks the layout, styling, and presence of all interactive components.

### Milestone 3: MVC Separation and Threading Controller
- **Objective**: Implement Model and Controller classes. Model holds configuration and state. Controller binds Model and View, handling user interactions. Integration of non-blocking background thread worker using simulated dummy backend generation. Add preset management (parameter presets loading/saving/selecting).
- **Verification**: Automated testing to verify that triggering a generation task does not block the UI thread (main event loop) and executes asynchronously.

### Milestone 4: Integration, Hardening, and Automated Verification
- **Objective**: Finalize unit tests and programmatic UI testing. Ensure no regressions occur in existing backend functionalities and verify the complete MVC integration.
- **Verification**: Run comprehensive automated testing suite showing:
  - Tab presence check
  - Non-blocking thread behavior check
  - Tooltips verification
  - Drag-and-drop event simulation
- **Audit**: Run Forensic Auditor to confirm clean execution, genuine non-blocking MVC design, and no test hardcoding.

---

## Action Plan
1. **Initialize project metadata and files.**
2. **Launch Explorer** to perform research on custom tkinter widgets, drag-and-drop library (e.g., tkinterdnd2 or custom simulation), tooltip design, and MVC blueprint.
3. **Launch Worker** to implement the View, Model, Controller, and tests.
4. **Launch Reviewer** to audit code quality, aesthetics, and design.
5. **Launch Challenger** to stress-test threading and UI event loops.
6. **Launch Forensic Auditor** to verify integrity and ensure no fake implementations.
7. **Submit final report to Sentinel.**
