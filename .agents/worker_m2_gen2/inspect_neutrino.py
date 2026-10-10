import os
import subprocess
import numpy as np

def test_run():
    neutrino_pfad = r"c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\NEUTRINO-windows-v3.1\NEUTRINO"
    bin_pfad = os.path.join(neutrino_pfad, "bin")
    ml_exe = os.path.join(bin_pfad, "musicXMLtoLabel.exe")
    neu_exe = os.path.join(bin_pfad, "neutrino.exe")
    
    xml_pfad = os.path.join(neutrino_pfad, "score", "musicxml", "sample1.musicxml")
    
    td = r"c:\Users\cilli\OneDrive\Desktop\vocaloid_musik\.agents\worker_m2_gen2"
    full_l   = os.path.join(td, "temp_vocals.lab")
    mono_l   = os.path.join(td, "temp_vocals_mono.lab")
    tim_l    = os.path.join(td, "temp_vocals_timing.lab")
    f0_f     = os.path.join(td, "temp_vocals.f0")
    mel_f    = os.path.join(td, "temp_vocals.melspec")
    
    # Run musicXMLtoLabel
    print("Running musicXMLtoLabel...")
    subprocess.run(
        [ml_exe, os.path.abspath(xml_pfad), os.path.abspath(full_l), os.path.abspath(mono_l)],
        check=True, cwd=neutrino_pfad
    )
    
    print("Running neutrino...")
    model_pfad = os.path.join(neutrino_pfad, "model", "MERROW")
    subprocess.run(
        [neu_exe, os.path.abspath(full_l), os.path.abspath(tim_l), os.path.abspath(f0_f),
         os.path.abspath(mel_f), model_pfad, "-n", "4", "-t"],
        check=True, cwd=neutrino_pfad
    )
    
    print("Files exists:")
    print("f0:", os.path.exists(f0_f))
    print("melspec:", os.path.exists(mel_f))
    
    if os.path.exists(f0_f):
        f0_data = np.fromfile(f0_f, dtype=np.float32)
        print("f0 shape:", f0_data.shape, "dtype:", f0_data.dtype)
        print("f0 min:", f0_data.min(), "max:", f0_data.max())
    
    if os.path.exists(mel_f):
        mel_data = np.fromfile(mel_f, dtype=np.float32)
        print("mel shape:", mel_data.shape, "dtype:", mel_data.dtype)
        
if __name__ == "__main__":
    test_run()
