# test_gui.py - Automated Unit/Mock Tests for Vocaloid Generator Pro MVC
import unittest
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Der App-Ordner liegt eine Ebene über tests/
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

pytest.importorskip("customtkinter")
import tkinter as tk

try:
    tk.Tk().destroy()
except tk.TclError:
    pytest.skip("kein Bildschirm für Tk verfügbar", allow_module_level=True)

class TestVocaloidGeneratorMVC(unittest.TestCase):

    def test_model_independent_of_gui(self):
        """Verify the Model is 100% independent of tkinter and customtkinter."""
        model_path = os.path.join(current_dir, "model.py")
        self.assertTrue(os.path.exists(model_path), "model.py should exist")
        
        with open(model_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Programmatic check that GUI libraries are not imported
        self.assertNotIn("import tkinter", content, "Model should not import tkinter")
        self.assertNotIn("from tkinter", content, "Model should not import from tkinter")
        self.assertNotIn("import customtkinter", content, "Model should not import customtkinter")
        self.assertNotIn("from customtkinter", content, "Model should not import from customtkinter")
        self.assertNotIn("import ctk", content, "Model should not import ctk")

    def test_view_contains_five_tabs(self):
        """Verify the view contains the 5 required DAW layout tab sections."""
        from view.main_view import VocaloidMainView
        from view.tabs import SongTab, LyricsTab, InstrumenteTab, MixerTab, SettingsTab
        
        dummy_cb = lambda *a: None
        view = VocaloidMainView(dummy_cb, dummy_cb, dummy_cb, dummy_cb)
        view.withdraw()  # Prevent rendering window
        try:
            
            # Assert all 5 tabs are present in main content shell
            self.assertIsNotNone(view.song_tab)
            self.assertIsNotNone(view.lyrics_tab)
            self.assertIsNotNone(view.instrumente_tab)
            self.assertIsNotNone(view.mixer_tab)
            self.assertIsNotNone(view.settings_tab)
            
            # Assert correct class types
            self.assertIsInstance(view.song_tab, SongTab)
            self.assertIsInstance(view.lyrics_tab, LyricsTab)
            self.assertIsInstance(view.instrumente_tab, InstrumenteTab)
            self.assertIsInstance(view.mixer_tab, MixerTab)
            self.assertIsInstance(view.settings_tab, SettingsTab)
        finally:
            view.destroy()

    def test_background_generation_non_blocking(self):
        """Verify generation task executes in background, is non-blocking, and polls successfully."""
        from model import VocaloidModel
        from view.main_view import VocaloidMainView
        from controller import VocaloidController
        
        model = VocaloidModel()
        dummy_cb = lambda *a: None
        # We instantiate main view (it is the Tk root itself) and bind it to controller
        view = VocaloidMainView(dummy_cb, dummy_cb, dummy_cb, dummy_cb)
        view.withdraw()

        try:
            controller = VocaloidController(model, view)
            
            # Hook the view buttons to controller actions
            view.on_generate = controller.handle_generate
            
            with patch('controller.VocaloidController._run_generation_task') as mock_run:
                # Trigger generation
                controller.handle_generate()
                
                # Assert generation state is active and button disabled
                self.assertTrue(controller.generation_in_progress)
                self.assertEqual(view.generate_btn.cget("state"), "disabled")
                
                # Queue up mock generation progress reports
                controller.queue.put(("status", "Synthetisiere MIDI..."))
                controller.queue.put(("progress", 0.5))
                controller.queue.put(("log", "[50%] Synthetisiere MIDI..."))
                
                # Run queue poll in GUI main thread context
                controller.poll_queue()
                
                # Verify UI variables updated properly
                self.assertEqual(view.status_lbl.cget("text"), "Status: Synthetisiere MIDI...")
                self.assertEqual(view.progress_bar.get(), 0.5)
                self.assertIn("[50%] Synthetisiere MIDI...", view.log_area.get("1.0", "end"))
                
                # Finish generation
                with patch('tkinter.messagebox.showinfo') as mock_info:
                    controller.queue.put(("done", True))
                    controller.poll_queue()
                    
                    # Check controls reset
                    self.assertFalse(controller.generation_in_progress)
                    self.assertEqual(view.generate_btn.cget("state"), "normal")
                    mock_info.assert_called_once()
        finally:
            view.destroy()

    def test_tooltip_displays_and_schedules(self):
        """Verify tooltips schedule their opening window display correctly on enter."""
        from view.widgets import HoverTooltip
        import tkinter as tk

        # Use a plain tk.Tk root for this unit test since CTkLabel inherits from
        # tk.BaseWidget and its bind() API works correctly with standard tkinter.
        root = tk.Tk()
        root.withdraw()

        try:
            label = tk.Label(root, text="Test Term")
            label.pack()

            tooltip = HoverTooltip(label, "Test Explanation Text", delay=20)

            # Check event triggers exist on the underlying tk widget
            bindings = label.bind()
            self.assertIn("<Enter>", bindings)
            self.assertIn("<Leave>", bindings)

            # Intercept scheduling event
            after_called = []
            def fake_after(delay, cb):
                after_called.append((delay, cb))
                return "after_id_999"

            label.after = fake_after
            tooltip.schedule()

            self.assertEqual(len(after_called), 1)
            self.assertEqual(after_called[0][0], 20)
            self.assertEqual(tooltip.id, "after_id_999")

            label.destroy()
        finally:
            root.destroy()

    def test_vst_drag_and_drop_handling(self):
        """Verify VST selection update propagates path info to Model."""
        from model import VocaloidModel
        from view.main_view import VocaloidMainView
        from controller import VocaloidController
        
        model = VocaloidModel()
        dummy_cb = lambda *a: None
        view = VocaloidMainView(dummy_cb, dummy_cb, dummy_cb, dummy_cb)
        view.withdraw()

        try:
            controller = VocaloidController(model, view)
            
            # Simulate dropping/selecting a vst3 file path
            vst_file = "C:/VSTPlugins/Surge.vst3"
            controller.handle_vst_selected(vst_file)
            
            # Assert state synchronization
            self.assertEqual(model.vst_path, vst_file)
        finally:
            view.destroy()

    def test_singer_and_harmonies_reach_the_settings(self):
        """Stimme und zweite Stimme lassen sich in den Einstellungen wählen und landen in SongSettings."""
        from model import VocaloidModel
        from view.main_view import VocaloidMainView
        from controller import VocaloidController

        view = VocaloidMainView(*[lambda *a: None] * 4)
        view.withdraw()
        try:
            with patch.object(VocaloidModel, "save_settings"):
                model = VocaloidModel()
                VocaloidController(model, view)
                self.assertIn("REINA", view.settings_tab.singer_menu.cget("values"))
                view.settings_tab.singer_var.set("REINA")
                view.settings_tab.harmonies_var.set(False)
                view.settings_tab.style_shift_var.set(2)
                view.song_tab.reference_var.set("C:/Musik/vorbild.mp3")
                settings = model.to_settings()
                self.assertEqual((settings.singer, settings.harmonies), ("REINA", False))
                self.assertEqual((settings.style_shift, settings.reference_track), (2, "C:/Musik/vorbild.mp3"))
        finally:
            view.destroy()


if __name__ == "__main__":
    unittest.main()
