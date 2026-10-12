# test_reference.py – Vorbild-Songs: messen, zusammenfassen, Mastering, Lautstärke-Verlauf und Gesangspegel
import os

import numpy as np
import pytest
import soundfile as sf

import mixer
import pipeline
import reference
from settings import ReferenceTrack, SongSettings

RATE = 22050


def song(path, bpm=120.0, seconds=24.0, chords=((57, 60, 64), (62, 65, 69), (64, 68, 71), (57, 60, 64)),
         drums=True, loud_from=None, rate=RATE):
    """Ein kleiner Test-Song: Akkorde als Sinustöne, Klicks auf jedem Schlag; ab loud_from Sekunden 8 dB lauter."""
    n = int(seconds * rate)
    t = np.arange(n) / rate
    y = np.zeros(n)
    beat = 60.0 / bpm
    for i, start in enumerate(np.arange(0, seconds, beat * 4)):
        chord = chords[i % len(chords)]
        a, b = int(start * rate), min(n, int((start + beat * 4) * rate))
        for pitch in chord:
            y[a:b] += 0.08 * np.sin(2 * np.pi * 440 * 2 ** ((pitch - 69) / 12) * t[a:b])
    if drums:
        click = np.exp(-np.arange(int(0.03 * rate)) / (0.005 * rate)) * np.random.default_rng(1).standard_normal(
            int(0.03 * rate))
        for start in np.arange(0, seconds, beat):
            a = int(start * rate)
            y[a:a + len(click)] += 0.5 * click[:n - a]
    if loud_from is not None:
        y[int(loud_from * rate):] *= 10 ** (8 / 20)
    sf.write(path, np.stack([y, y], axis=1).astype(np.float32), rate)
    return str(path)


# ── Messen ────────────────────────────────────────────────────────────────────────
def test_tempo_and_key_of_a_reference_are_measured(tmp_path):
    a = reference.analyse(song(tmp_path / "a.wav", bpm=128))
    assert abs(a.bpm - 128) < 4
    assert (a.key, a.scale) == ("A", "minor")
    assert len(a.key_scores) == 24


def test_measurements_come_from_the_cache_the_second_time(tmp_path, monkeypatch):
    path = song(tmp_path / "a.wav")
    first = reference.analyse(path)
    monkeypatch.setattr(reference, "_tempo", lambda *a: pytest.fail("neu gemessen"))
    assert reference.analyse(path) == first


def test_changed_file_is_measured_again(tmp_path):
    path = song(tmp_path / "a.wav", bpm=100)
    reference.analyse(path)
    os.utime(path, ns=(1, 1))
    song(tmp_path / "a.wav", bpm=140)
    assert abs(reference.analyse(path).bpm - 140) < 4


def test_contrast_tells_quiet_verse_from_loud_chorus(tmp_path):
    flat = reference.analyse(song(tmp_path / "flat.wav", seconds=30))
    dynamic = reference.analyse(song(tmp_path / "dynamic.wav", seconds=30, loud_from=15))
    assert dynamic.contrast_db > flat.contrast_db + 5


def test_several_references_are_summarized_by_weight(tmp_path):
    refs = [ReferenceTrack(path=song(tmp_path / "a.wav", bpm=120)),
            ReferenceTrack(path=song(tmp_path / "b.wav", bpm=140), weight=3.0),
            ReferenceTrack(path=song(tmp_path / "off.wav", bpm=60), enabled=False)]
    summary = reference.summarize(refs)
    assert 130 <= summary.bpm <= 140
    assert summary.names == ["a.wav", "b.wav"]
    assert summary.key == "A"


def test_tempo_twice_as_fast_counts_as_the_same_tempo():
    assert reference._combine_tempi([(80, 1.0), (162, 3.0)]) == pytest.approx(161.5, abs=1)


def test_missing_reference_is_skipped(tmp_path):
    assert reference.summarize([ReferenceTrack(path=str(tmp_path / "fehlt.mp3"))]) is None


@pytest.mark.parametrize("measured, style", [
    ((76, "major", 0.09, 0.19), "Ballade"),
    ((112, "major", 0.38, 0.55), "City Pop"),
    ((172, "minor", 0.63, 0.44), "Dark Vocaloid"),
    ((162, "minor", 0.56, 0.63), "J-Pop Energy"),
    ((172, "major", 0.70, 0.57), "Kawaii Chiptune"),
    ((152, "major", 0.73, 0.60), "Rock"),
])
def test_style_suggestion_finds_the_style_of_our_own_demos(measured, style):
    # die Werte hat reference.analyse an den Hörbeispielen der App gemessen
    assert reference.suggest_style(*measured, styles=["J-Pop Energy", "Dark Vocaloid", "Kawaii Chiptune", "Rock",
                                                      "Ballade", "City Pop"]) == style


def test_library_lists_audio_files(tmp_path):
    os.makedirs(reference.LIBRARY)
    for name in ("b.mp3", "a.wav", "notiz.txt", ".versteckt.wav"):
        open(os.path.join(reference.LIBRARY, name), "w").close()
    assert [os.path.basename(f) for f in reference.library_files()] == ["a.wav", "b.mp3"]


# ── Mastering nach mehreren Vorbildern ─────────────────────────────────────────────
def test_one_reference_is_used_as_it_is(tmp_path):
    path = song(tmp_path / "a.wav")
    assert reference.mastering_reference([ReferenceTrack(path=path)], str(tmp_path)) == path


def test_several_references_are_cut_together_at_the_same_loudness(tmp_path):
    quiet = song(tmp_path / "quiet.wav", seconds=30)
    data, rate = sf.read(quiet)
    sf.write(tmp_path / "loud.wav", data * 4, rate)
    path = reference.mastering_reference([ReferenceTrack(path=quiet), ReferenceTrack(path=str(tmp_path / "loud.wav"))],
                                         str(tmp_path))
    audio, rate = sf.read(path, always_2d=True)
    half = len(audio) // 2
    first, second = (mixer._loudness(part.T.astype(np.float32)) for part in (audio[:half], audio[half:]))
    assert abs(first - second) < 1.0
    assert rate == mixer.SAMPLE_RATE


# ── Mix ───────────────────────────────────────────────────────────────────────────
def noise_track(seconds=20.0, key="drums"):
    rng = np.random.default_rng(3)
    return key, (0.1 * rng.standard_normal((2, int(seconds * mixer.SAMPLE_RATE)))).astype(np.float32)


def test_quiet_sections_get_quieter_for_a_dynamic_reference():
    tracks = {"drums.wav": noise_track(), "vocals.wav": noise_track(key="vocals")}
    length = tracks["drums.wav"][1].shape[1]
    sections = [(0.0, 10.0, 0.4), (10.0, 20.0, 1.0)]
    mixer._shape_energy(tracks, sections, target_db=6.0, length=length)
    band = tracks["drums.wav"][1]
    verse = 20 * np.log10(np.std(band[:, :8 * mixer.SAMPLE_RATE]))
    chorus = 20 * np.log10(np.std(band[:, 12 * mixer.SAMPLE_RATE:]))
    assert chorus - verse > 4
    # der Gesang bleibt, wie er ist
    assert np.std(tracks["vocals.wav"][1]) == pytest.approx(np.std(noise_track(key="vocals")[1]), rel=1e-3)


def test_vocals_are_turned_up_until_they_match_the_reference(monkeypatch):
    import reference as ref_module

    def true_ratio(y, rate):       # eine perfekte Schätzung: Gesang ist der Teil über 1 kHz
        spectrum = np.abs(np.fft.rfft(y)) ** 2
        freqs = np.fft.rfftfreq(len(y), 1 / rate)
        return 10 * np.log10(spectrum[freqs > 1000].sum() / spectrum[freqs <= 1000].sum())

    monkeypatch.setattr(ref_module, "vocal_ratio_db", true_ratio)
    t = np.arange(10 * mixer.SAMPLE_RATE) / mixer.SAMPLE_RATE
    band = np.stack([0.3 * np.sin(2 * np.pi * 200 * t)] * 2).astype(np.float32)
    voice = np.stack([0.19 * np.sin(2 * np.pi * 2000 * t)] * 2).astype(np.float32)   # 4 dB zu leise
    tracks = {"bass.wav": ("bass", band), "vocals.wav": ("vocals", voice)}
    mixer._match_vocal_level(tracks, target_db=0.0)
    ratio = 20 * np.log10(np.std(tracks["vocals.wav"][1]) / np.std(band))
    assert ratio == pytest.approx(0.0, abs=0.6)


def test_reference_targets_follow_the_switches(tmp_path, monkeypatch):
    path = song(tmp_path / "a.wav")
    s = SongSettings(reference_tracks=[ReferenceTrack(path=path)], ref_vocal_level=False)
    plan = type("Plan", (), {"seconds_per_beat": 0.5, "sections": []})()
    targets = pipeline._reference_targets(s, {"plan": plan}, str(tmp_path), has_vocals=True)
    assert targets["reference"] == path
    assert "energy_contrast_db" in targets and "vocal_ratio_db" not in targets
    off = s.with_updates(ref_mastering=False, ref_energy=False)
    assert pipeline._reference_targets(off, {"plan": plan}, str(tmp_path), has_vocals=True) == {}


def test_no_reference_means_no_targets(tmp_path):
    assert pipeline._reference_targets(SongSettings(), {}, str(tmp_path), has_vocals=True) == {}


# ── Einstellungen ─────────────────────────────────────────────────────────────────
def test_old_single_reference_becomes_the_first_of_the_list():
    s = SongSettings.model_validate({"reference_track": "C:/lieblingssong.mp3"})
    assert [(r.path, r.weight, r.enabled) for r in s.reference_tracks] == [("C:/lieblingssong.mp3", 1.0, True)]


def test_suggestions_are_taken_only_where_allowed(tmp_path, monkeypatch):
    summary = reference.Summary(bpm=172, key="D", scale="minor", style="Dark Vocaloid", contrast_db=4.0,
                                vocal_db=-3.0, names=["a.wav"])
    monkeypatch.setattr(reference, "summarize", lambda *a: summary)
    s = SongSettings(style="Rock", bpm=120, key="C", scale="major")
    taken = pipeline.from_references(s)
    assert (taken.style, taken.bpm, taken.key, taken.scale) == ("Dark Vocaloid", 172, "D", "minor")
    only_tempo = pipeline.from_references(s.with_updates(ref_style=False))
    assert (only_tempo.style, only_tempo.bpm) == ("Rock", 172)


def test_references_move_the_vocals_at_most_6_db(monkeypatch):
    import reference as ref_module
    monkeypatch.setattr(ref_module, "vocal_ratio_db", lambda y, rate: -20.0)
    voice = np.full((2, mixer.SAMPLE_RATE), 0.1, dtype=np.float32)
    tracks = {"vocals.wav": ("vocals", voice.copy()), "bass.wav": ("bass", voice.copy())}
    mixer._match_vocal_level(tracks, target_db=0.0)
    assert 20 * np.log10(tracks["vocals.wav"][1].max() / 0.1) == pytest.approx(mixer.MAX_REFERENCE_DB, abs=0.01)


def test_key_with_the_most_weight_wins():
    def measured(key, scale, weight):
        a = reference.Analysis(path="x", seconds=60, bpm=120, key=key, scale=scale, key_scores=[0.0] * 24,
                               brightness=0.5, drums=0.5, contrast_db=3, vocal_db=-20)
        return a, weight
    assert reference._combine_keys([measured("D", "minor", 1.0), measured("E", "major", 0.5)]) == ("D", "minor")
    assert reference._combine_keys([measured("D", "minor", 1.0), measured("E", "major", 0.5),
                                    measured("E", "major", 0.7)]) == ("E", "major")


def test_references_without_vocals_leave_the_vocal_level_alone(tmp_path):
    summary = reference.summarize([ReferenceTrack(path=song(tmp_path / "a.wav"))])
    assert summary.vocal_db is None
