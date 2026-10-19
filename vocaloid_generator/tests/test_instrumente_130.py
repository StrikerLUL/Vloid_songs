# test_instrumente_130.py – Instrumente 1.3.0: Surge-XT-Klänge (I8), Verstärker (I9), Druck im Mix (I10)
import numpy as np
import pytest
import soundfile as sf

import mixdown
import mixer
from settings import SongSettings

SR = mixer.SAMPLE_RATE


def _drums(seconds=4.0):
    """Laute Schläge mit leisem Nachklang: Bassdrum auf jedem Schlag, dazwischen leise Ghost-Notes."""
    t = np.arange(int(SR * seconds)) / SR
    out = np.zeros_like(t)
    for k in range(int(seconds * 2)):
        start = int(k * 0.5 * SR)
        n = int(0.2 * SR)
        hit = (1.0 if k % 2 == 0 else 0.08) * np.exp(-np.arange(n) / (0.03 * SR)) * np.sin(2 * np.pi * 60 *
                                                                                          np.arange(n) / SR)
        out[start:start + n] += hit[:len(out) - start]
    return np.stack([out, out]).astype(np.float32) * 0.5


def test_parallel_bus_and_multiband_compression_add_punch(tmp_path):
    drums = _drums()
    punchy = mixer.parallel_compress(drums)
    assert mixer._loudness(punchy) == pytest.approx(mixer._loudness(drums), abs=0.6), "gleich laut"
    ghost = slice(int(0.5 * SR), int(0.6 * SR))
    hit = slice(0, int(0.1 * SR))
    ratio = lambda x: np.abs(x[0, ghost]).max() / np.abs(x[0, hit]).max()      # noqa: E731
    assert ratio(punchy) > 1.3 * ratio(drums), "leise Schläge kommen nach vorn"
    # Bus-Kompressor: alle Spuren der Band werden gemeinsam leiser, wo die Summe laut ist; der Gesang nicht
    loud, quiet = np.ones((2, SR), np.float32) * 0.5, np.ones((2, SR), np.float32) * 0.5
    loud[:, SR // 2:] *= 0.05
    quiet[:, SR // 2:] *= 0.05
    voice = np.ones((2, SR), np.float32) * 0.3
    tracks = {"a": ("drums", loud.copy()), "b": ("piano", quiet.copy()), "c": ("vocals", voice.copy())}
    mixer.glue_band(tracks)
    early, late = slice(SR // 4, SR // 2 - 100), slice(3 * SR // 4, SR - 1)
    for path, before in (("a", loud), ("b", quiet)):
        cut_early = tracks[path][1][0, early].mean() / before[0, early].mean()
        cut_late = tracks[path][1][0, late].mean() / before[0, late].mean()
        assert cut_early < 0.95 and cut_late == pytest.approx(1.0, abs=0.02)
    assert np.array_equal(tracks["c"][1], voice)
    # Mehrband: still bleibt alles, wie es war; laute Bässe werden für sich verdichtet
    noise = np.random.default_rng(1).standard_normal((2, SR)).astype(np.float32) * 1e-3
    assert np.allclose(mixer.multiband(noise), noise, atol=1e-5)
    t = np.arange(SR) / SR
    boom = np.stack([np.sin(2 * np.pi * 60 * t) * 0.9 + np.sin(2 * np.pi * 5000 * t) * 0.01] * 2).astype(np.float32)
    squeezed = mixer.multiband(boom)

    def band(x, lo, hi):
        spec = np.abs(np.fft.rfft(x[0]))
        freqs = np.fft.rfftfreq(len(x[0]), 1 / SR)
        return spec[(freqs > lo) & (freqs < hi)].max()
    assert band(squeezed, 50, 70) < 0.8 * band(boom, 50, 70)
    assert band(squeezed, 4900, 5100) == pytest.approx(band(boom, 4900, 5100), rel=0.1), "die Höhen bleiben"
    # in der App: der Schalter kommt beim Mix an, aus klingt es wie bisher
    s = SongSettings(output_ordner=str(tmp_path))
    tracks = {"plan": None}
    assert mixdown.mix_arguments(s, tracks, str(tmp_path), has_vocals=False)["punch"] is True
    assert mixdown.mix_arguments(s.with_updates(mix_punch=False), tracks, str(tmp_path), has_vocals=False)["punch"] \
        is False
    paths = []
    for name, audio in (("drums", drums), ("piano", boom[:, :len(drums[0])] if boom.shape[1] >= drums.shape[1]
                                           else np.pad(boom, ((0, 0), (0, drums.shape[1] - boom.shape[1]))))):
        path = tmp_path / f"{name}.wav"
        sf.write(path, audio.T, SR, subtype="FLOAT")
        paths.append(str(path))
    on, off = tmp_path / "an.wav", tmp_path / "aus.wav"
    mixer.mische_spuren(paths, output_pfad=str(on), punch=True)
    mixer.mische_spuren(paths, output_pfad=str(off), punch=False)
    assert not np.allclose(sf.read(on)[0], sf.read(off)[0], atol=1e-3)
