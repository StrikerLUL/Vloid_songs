# Repeatable music and audio benchmark

Run from the repository root with the locked development environment:

```powershell
uv run --frozen python scripts/benchmark_music.py --seeds 2 --audio-dir output/benchmark/before --output output/benchmark/before.json
uv run --frozen python scripts/benchmark_music.py --seeds 2 --audio-dir output/benchmark/after --output output/benchmark/after.json --baseline output/benchmark/before.json
```

The existing four-style suite uses seeds `0..N-1` in both coherence modes,
with identical lyrics, structure, key, tempo and feature selection. Without
`--audio-dir`, it retains its composition-only behavior. Parent output folders
are created automatically. Keep separate audio folders when comparing runs.

Audio consists of the generated melody at fixed velocity 100, rendered through
the style's built-in melody synth voice (or lead fallback), at 44100 Hz. It is
a diagnostic preview, not a vocal-engine, accompaniment or mastered-mix test.
No external models, SoundFonts or local sound libraries are used. FLOAT WAVs
preserve peaks above full scale so clipping is measurable rather than hidden.

JSON includes suite inputs, Python/platform and numerical-library versions,
musical scores, overlap and post-selection mutation counts, and optional audio
duration, RMS, absolute sample peak, fraction of samples at or above full scale,
centroid in Hz from averaged per-channel FFT magnitudes (preserving antiphase
signals), and SHA-256 of channel-first little-endian
float32 samples. Silence has zero centroid. These diagnostics do not measure
perceived musical quality; listen to the WAVs too.

`--baseline` adds signed deltas (current minus baseline) for every numeric metric
and an audio-hash change flag. Different suite inputs, metrics, duplicate cases
or unmatched seeds/styles/modes are rejected. Environment metadata is retained
for review, not used to reject comparisons: exact hashes are meaningful only
with matching dependency versions and platforms. Wall-clock seconds are noisy
and excluded from repeatability assertions. No score or audio-delta thresholds
are imposed; the existing exit status still fails on coherent-mode overlaps or
post-selection mutations. Reports predating schema version 1 must be regenerated.
Audio suite v2 uses the per-channel centroid; v1 audio reports must be regenerated
before comparing with v2.

Focused checks:

```powershell
.venv/Scripts/python.exe -m pytest vocaloid_generator/tests/test_benchmark.py -q
```

# Windows installer release verification

`.github/workflows/installer.yml` builds on Windows for pull requests and pushes
to main or `codex/**`, matching the Tests workflow. It requires network access for
uv, Python 3.12, locked dependencies,
and the rating environment's packages, plus Inno Setup 6 (Chocolatey fallback).
It packages Python and uv, simulates a broken managed Python installation,
installs into a path containing spaces using an empty dedicated uv cache and
isolated user-data directory, checks bundled-interpreter selection, dependency
consistency and model-environment repair, then checks uninstall success and
removal of the app and main venv. Installer logs are uploaded even on failure.
A pre-existing song sentinel in the isolated `VLOID_DATEN/Songs` directory must
retain its exact content after both installation and uninstallation.
This is a hosted-runner integration check; it does not exercise an interactive
GUI or prove installation works offline or on a pristine physical Windows PC.

Publishing requires a successful main push run, `contents: write`, a new version
in `vocaloid_generator/version.py`, and an absent `v<version>` release. The
workflow attaches Setup.exe, targets the triggering SHA, and reads notes from
the matching changelog section (falling back to the version label). Existing
releases are skipped. The separate Tests workflow should also pass before
merging; the installer job does not depend on that workflow automatically.
For release preparation, push a `codex/**` branch, wait for both Tests and
Installer to succeed, then fast-forward main to that same verified SHA. Branch
runs validate the setup without publishing; the main push runs the installer
workflow again and alone can publish the release.
