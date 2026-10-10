# gui_mvc.py - Launch Script for Vocaloid Music AI Generator Pro MVC
import sys
import os

# Add the current directory to path to ensure modules can find each other
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from model import VocaloidModel
from view.main_view import VocaloidMainView
from controller import VocaloidController

def main():
    """Initializes and runs the MVC Vocaloid Music Generator Pro application."""
    model = VocaloidModel()
    
    # Delegate reference container to resolve mutual dependency between View and Controller
    controller_holder = []

    def delegate_generate():
        if controller_holder:
            controller_holder[0].handle_generate()

    def delegate_vst_selected(path):
        if controller_holder:
            controller_holder[0].handle_vst_selected(path)

    def delegate_preset_clicked(structure):
        if controller_holder:
            controller_holder[0].handle_preset_clicked(structure)

    def delegate_toggle_section(sec_name):
        if controller_holder:
            controller_holder[0].handle_toggle_section(sec_name)

    # 1. Initialize view with event delegate callbacks
    view = VocaloidMainView(
        on_generate_callback=delegate_generate,
        on_vst_selected_callback=delegate_vst_selected,
        on_preset_clicked_callback=delegate_preset_clicked,
        on_toggle_section_callback=delegate_toggle_section
    )

    # 2. Initialize controller which binds Model and View
    controller = VocaloidController(model, view)
    controller_holder.append(controller)

    # 3. Start Tkinter Main Event Loop
    view.mainloop()

if __name__ == "__main__":
    main()
