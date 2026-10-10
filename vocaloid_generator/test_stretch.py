import numpy as np
import soundfile as sf
import pyworld as pw
from scipy.interpolate import interp1d

data, fs = sf.read('test_tts.wav')
if len(data.shape) > 1: data = data[:, 0]
data = data.astype(np.float64)

_f0, t = pw.dio(data, fs)
f0 = pw.stonemask(data, _f0, t, fs)
sp = pw.cheaptrick(data, f0, t, fs)
ap = pw.d4c(data, f0, t, fs)

# Ziel-Dauer 2.0 Sekunden
target_duration = 2.0
frame_period = 0.005 # pyworld default is 5ms
target_frames = int(target_duration / frame_period)

orig_len = len(f0)
orig_indices = np.linspace(0, 1, orig_len)
target_indices = np.linspace(0, 1, target_frames)

# Interpoliere F0, SP, AP
f0_stretched = interp1d(orig_indices, f0)(target_indices)
sp_stretched = interp1d(orig_indices, sp, axis=0)(target_indices)
ap_stretched = interp1d(orig_indices, ap, axis=0)(target_indices)

# Flat pitch C4
target_f0 = 261.63
f0_stretched = np.where(f0_stretched > 0, target_f0, 0.0).astype(np.float64)

synthesized = pw.synthesize(f0_stretched, np.ascontiguousarray(sp_stretched), np.ascontiguousarray(ap_stretched), fs)
sf.write('test_tts_stretched.wav', synthesized, fs)
print("Stretch done!")
