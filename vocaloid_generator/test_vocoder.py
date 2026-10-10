import numpy as np
import soundfile as sf
import pyworld as pw

# Lade wav
data, fs = sf.read('test_tts.wav')
if len(data.shape) > 1:
    data = data[:, 0]
data = data.astype(np.float64)

# 1. Analyse (F0, Spectral Envelope, Aperiodicity)
_f0, t = pw.dio(data, fs)
f0 = pw.stonemask(data, _f0, t, fs)
sp = pw.cheaptrick(data, f0, t, fs)
ap = pw.d4c(data, f0, t, fs)

# 2. Modifiziere F0 (Setze alles auf C4, wo Stimme ist)
target_f0 = 261.63 # C4
f0_modified = np.where(f0 > 0, target_f0, 0.0).astype(np.float64)

# 3. Synthetisiere
synthesized = pw.synthesize(f0_modified, sp, ap, fs)
sf.write('test_tts_sung.wav', synthesized, fs)
print("Done!")
