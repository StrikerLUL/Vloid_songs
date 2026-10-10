import os
import shutil

def setup():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.join(base_dir, "めろう（NEUTRINO-Library）-v3.1")
    dest_dir = os.path.join(base_dir, "NEUTRINO-windows-v3.1", "NEUTRINO", "model", "MERROW")

    print(f"Starting NEUTRINO MERROW setup...")
    print(f"Source root: {src_root}")
    print(f"Destination: {dest_dir}")

    # Check potential source directories
    candidates = [
        os.path.join(src_root, "めろう（NEUTRINO-Library）", "MERROW"),
        os.path.join(src_root, "speaker"),
    ]

    src_dir = None
    for cand in candidates:
        if os.path.exists(cand) and os.path.isdir(cand):
            src_dir = cand
            break

    # If neither path matched, let's do a search for MERROW or speaker under src_root
    if not src_dir and os.path.exists(src_root):
        for root, dirs, files in os.walk(src_root):
            for d in dirs:
                if d == "MERROW" or d == "speaker":
                    src_dir = os.path.join(root, d)
                    break
            if src_dir:
                break

    if not src_dir:
        print(f"Error: Could not find Voice-Library source directory in {src_root}")
        return False

    print(f"Found source directory: {src_dir}")
    os.makedirs(dest_dir, exist_ok=True)

    for item in os.listdir(src_dir):
        src_file = os.path.join(src_dir, item)
        if os.path.isfile(src_file):
            dest_file = os.path.join(dest_dir, item)
            print(f"Copying {src_file} -> {dest_file}")
            shutil.copy2(src_file, dest_file)
            print(f"Copied: {item}")
        elif os.path.isdir(src_file):
            dest_subdir = os.path.join(dest_dir, item)
            print(f"Copying directory {src_file} -> {dest_subdir}")
            if os.path.exists(dest_subdir):
                shutil.rmtree(dest_subdir)
            shutil.copytree(src_file, dest_subdir)
            print(f"Copied directory: {item}")

    print("Setup completed successfully.")
    return True

if __name__ == "__main__":
    setup()
