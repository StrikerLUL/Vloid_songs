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
