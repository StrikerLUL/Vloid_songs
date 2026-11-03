"""Audio diagnostics and strict, matched-case comparisons for benchmark_music."""
import hashlib

import numpy as np


def audio_metrics(audio, sample_rate):
    """Measure channel-first floating audio; silence has zero centroid and RMS."""
    audio = np.asarray(audio, dtype=np.float64)
    if sample_rate <= 0 or audio.ndim != 2 or not audio.size or not np.isfinite(audio).all():
        raise ValueError("Expected finite, nonempty channel-first audio and a positive sample rate")
    # Average magnitudes after the FFT so opposite channel phases cannot cancel.
    spectrum = np.abs(np.fft.rfft(audio, axis=1)).mean(axis=0)
    energy = float(spectrum.sum())
    return {
        "audio_seconds": audio.shape[1] / sample_rate,
        "audio_rms": float(np.sqrt(np.mean(audio ** 2))),
        "audio_peak": float(np.abs(audio).max()),
        "audio_clip_fraction": float(np.mean(np.abs(audio) >= 1)),
        "audio_centroid_hz": float(np.dot(np.fft.rfftfreq(audio.shape[1], 1 / sample_rate), spectrum) / energy)
        if energy else 0.0,
        "audio_sha256": hashlib.sha256(audio.astype("<f4").tobytes()).hexdigest(),
    }


def compare_reports(current, baseline):
    """Reject incompatible suites rather than silently comparing different cases."""
    if current.get("suite") != baseline.get("suite") or current.get("schema_version") != baseline.get("schema_version"):
        raise ValueError("Incompatible benchmark suite/schema")

    def index(report):
        rows = report["rows"]
        keyed = {(r["style"], r["seed"], r["coherent"]): r for r in rows}
        if len(keyed) != len(rows):
            raise ValueError("Duplicate benchmark cases")
        return keyed

    now, before = index(current), index(baseline)
    if now.keys() != before.keys():
        raise ValueError("Baseline cases must match styles, seeds and coherence modes exactly")
    deltas = []
    for key, row in now.items():
        old = before[key]
        if row.keys() != old.keys():
            raise ValueError("Baseline metrics do not match (use the same audio options)")
        deltas.append({"style": key[0], "seed": key[1], "coherent": key[2],
                       "delta": {k: row[k] - old[k] for k in row
                                 if k not in ("seed", "coherent") and type(row[k]) in (int, float)},
                       **({"audio_changed": row["audio_sha256"] != old["audio_sha256"]}
                          if "audio_sha256" in row else {})})
    return deltas
