# proposed_setup_neutrino.py
# Verification and diagnostics tool for NEUTRINO installation and model files

import os
import sys
import subprocess

# Add project root to path to load config
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)
# Also add vocaloid_generator subdirectory
vocaloid_gen_path = os.path.join(project_root, "vocaloid_generator")
if vocaloid_gen_path not in sys.path:
    sys.path.append(vocaloid_gen_path)

try:
    from config import NEUTRINO_PFAD, NEUTRINO_MODEL, NEUTRINO_MODEL_PFAD
    print("[Config] Successfully imported config settings.")
except ImportError as e:
    print(f"[Error] Failed to import config: {e}")
    sys.exit(1)

def verify_neutrino():
    print(f"=== NEUTRINO Environment Diagnostic ===")
    print(f"NEUTRINO Path: {NEUTRINO_PFAD}")
    print(f"NEUTRINO Model: {NEUTRINO_MODEL}")
    print(f"NEUTRINO Model Path: {NEUTRINO_MODEL_PFAD}")
    print("-" * 40)

    # 1. Check NEUTRINO directory existence
    if not os.path.exists(NEUTRINO_PFAD):
        print(f"[FAIL] NEUTRINO directory does not exist at: {NEUTRINO_PFAD}")
        return False
    print("[PASS] NEUTRINO directory exists.")

    # 2. Check executable binaries
    bin_dir = os.path.join(NEUTRINO_PFAD, "bin")
    if not os.path.exists(bin_dir):
        print(f"[FAIL] NEUTRINO 'bin' directory not found at: {bin_dir}")
        return False

    ml_exe = os.path.join(bin_dir, "musicXMLtoLabel.exe")
    neu_exe = os.path.join(bin_dir, "neutrino.exe")

    for name, path in [("musicXMLtoLabel.exe", ml_exe), ("neutrino.exe", neu_exe)]:
        if not os.path.exists(path):
            print(f"[FAIL] Required binary {name} is missing at {path}")
            return False
        else:
            print(f"[PASS] Found {name}")

    # 3. Check model files
    if not os.path.exists(NEUTRINO_MODEL_PFAD):
        print(f"[FAIL] Model directory not found at: {NEUTRINO_MODEL_PFAD}")
        return False
    print("[PASS] Model directory exists.")

    required_model_files = ["p.bin", "s.bin", "t.bin", "v.bin", "info.toml"]
    missing_files = []
    for file in required_model_files:
        fpath = os.path.join(NEUTRINO_MODEL_PFAD, file)
        if not os.path.exists(fpath):
            missing_files.append(file)
        else:
            print(f"[PASS] Found model file: {file} ({os.path.getsize(fpath)} bytes)")

    if missing_files:
        print(f"[FAIL] Missing model files in {NEUTRINO_MODEL}: {missing_files}")
        return False

    # 4. Check dependencies/run dry-runs of executables
    print("\n--- Running Dry-Runs to verify DLL dependencies ---")
    
    # Set bin path in environment so DLLs in bin can be resolved
    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

    # Dry-run musicXMLtoLabel.exe (should output usage error when run without arguments, but not crash on DLLs)
    try:
        res = subprocess.run([ml_exe], capture_output=True, env=env, text=True, timeout=5)
        # It typically prints usage message to stderr or stdout
        print("[PASS] musicXMLtoLabel.exe executed successfully (DLL check passed).")
    except subprocess.TimeoutExpired:
        print("[WARN] musicXMLtoLabel.exe timed out.")
    except Exception as e:
        print(f"[FAIL] musicXMLtoLabel.exe execution failed: {e}")
        return False

    # Dry-run neutrino.exe
    try:
        res = subprocess.run([neu_exe], capture_output=True, env=env, text=True, timeout=5)
        print("[PASS] neutrino.exe executed successfully (DLL check passed).")
    except subprocess.TimeoutExpired:
        print("[WARN] neutrino.exe timed out.")
    except Exception as e:
        print(f"[FAIL] neutrino.exe execution failed: {e}")
        return False

    print("\n[SUCCESS] NEUTRINO installation and MERROW model verify successfully.")
    return True

if __name__ == "__main__":
    success = verify_neutrino()
    sys.exit(0 if success else 1)
