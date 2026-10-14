# test_singing.py – Gesang: Tonhöhenakzent, Melisma, UST für OpenUtau und Duett mit zwei Stimmen
import os
import zipfile

import numpy as np
import pytest
import soundfile as sf

import config
import vocal_synthesizer
from lyrics import Mora, syllables, vowel
from melody_writer import accent_moves, duet_voice, split_for_duet
from orchestrator import orchestrate_song
from exporter import exportiere_projekt
from pipeline import UST_FILES, SongResult, _synthesize_vocals, _write_ust, compose, seed_everything
from settings import SongSettings
from ust_export import TICKS_PER_QUARTER, lies_ust, schreibe_ust

STRUCTURE = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Bridge", "Chorus", "Outro"]


def song(tmp_path, seed=4, style="J-Pop Energy", structure=STRUCTURE):
    seed_everything(seed)
    return orchestrate_song(genre=style, bpm=160, structure=structure, key="A", mode="minor",
                            section_config=config.SECTION_CONFIG, output_dir=str(tmp_path), style=style)


def sung_notes(tracks):
    return [(p, d) for p, d in tracks["melody_data"] if p is not None]


# ── Tonhöhenakzent ──────────────────────────────────────────────────────────────
def test_lyrics_know_the_pitch_accent_of_their_words():
    kimi_no_koe = syllables("君の声")
    assert [(str(m), m.tone, m.word_start) for m in kimi_no_koe] == [
        ("き", "L", True), ("み", "H", False), ("の", "H", False), ("こ", "H", True), ("え", "L", False)]
    # Kana mit Leerzeichen werden als Satz gelesen, die Silben bleiben dieselben
    spaced = syllables("よ る の ま ち")
    assert spaced == ["よ", "る", "の", "ま", "ち"] and [m.tone for m in spaced] == ["H", "L", "L", "L", "H"]
    assert accent_moves(spaced) == [0, -1, 0, 0, 1]


def test_melody_mostly_follows_the_accent(tmp_path):
    follows = against = 0
    for seed in range(4):
        tracks = song(tmp_path / str(seed), seed)
        pitches = [p for p, _ in sung_notes(tracks)]
        for i, move in enumerate(accent_moves(tracks["silben"])):
            if i and move:
                step = (pitches[i] - pitches[i - 1]) * move
                follows += step > 0
                against += step < 0
    assert follows > 2 * against, (follows, against)


# ── Melisma ─────────────────────────────────────────────────────────────────────
def test_some_phrases_end_with_a_melisma_on_the_same_vowel(tmp_path):
    tracks = song(tmp_path, style="Ballade")
    silben, notes = tracks["silben"], sung_notes(tracks)
    melismas = [i for i, s in enumerate(silben) if getattr(s, "melisma", False)]
    assert melismas and len(silben) == len(notes)
    for i in melismas:
        assert str(silben[i]) == vowel(str(silben[i - 1]))
        assert 1 <= abs(notes[i][0] - notes[i - 1][0]) <= 5      # ein kleiner Schritt, kein Sprung


def test_melisma_lands_on_a_chord_tone(tmp_path):
    tracks = song(tmp_path, style="Ballade", seed=6)
    plan = tracks["plan"]
    beat, i, checked = 0.0, 0, 0
    for pitch, dur in tracks["melody_data"]:
        if pitch is not None:
            if getattr(tracks["silben"][i], "melisma", False):
                assert pitch % 12 in plan.chord_at(beat + 0.01).pcs
                checked += 1
            i += 1
        beat += dur
    assert checked


def test_chiptune_sings_fewer_melismas_than_the_ballad(tmp_path):
    def count(style):
        return sum(sum(getattr(s, "melisma", False) for s in song(tmp_path / f"{style}{k}", k, style)["silben"])
                   for k in range(4))
    assert count("Kawaii Chiptune") < count("Ballade")


def test_moras_survive_copying_and_pickling():
    import copy
    import pickle
    m = Mora("あ", "H", True, True)
    for other in (copy.deepcopy(m), pickle.loads(pickle.dumps(m))):
        assert other == "あ" and other.tone == "H" and other.word_start and other.melisma


# ── UST für OpenUtau ─────────────────────────────────────────────────────────────
def test_ust_has_tempo_rests_and_every_note(tmp_path):
    path = schreibe_ust([(None, 4.0), (60, 1.0), (62, 0.5), (None, 0.25), (None, 0.25), (64, 2.0)],
                        ["き", "み", "お"], 150, str(tmp_path / "a.ust"), transpose=-12)
    text = open(path, encoding="cp932").read()
    assert "Tempo=150.00" in text and text.startswith("[#VERSION]") and text.rstrip().endswith("[#TRACKEND]")
    assert lies_ust(path) == [(4 * TICKS_PER_QUARTER, "R", 60), (480, "き", 48), (240, "み", 50),
                              (240, "R", 60), (960, "お", 52)]


def test_ust_keeps_the_timing_of_the_whole_song(tmp_path):
    tracks = song(tmp_path)
    path = schreibe_ust(tracks["melody_data"], tracks["silben"], 160, str(tmp_path / "v.ust"))
    notes = lies_ust(path)
    total = sum(d for _, d in tracks["melody_data"])
    assert sum(length for length, _, _ in notes) == round(total * TICKS_PER_QUARTER)
    assert [lyric for _, lyric, _ in notes if lyric != "R"] == [str(s) for s in tracks["silben"]]


# ── Duett ────────────────────────────────────────────────────────────────────────
def test_duet_splits_verses_bridge_and_chorus(tmp_path):
    tracks = song(tmp_path)
    plan = tracks["plan"]
    kinds = {(s.kind, s.occurrence): duet_voice(s) for s in plan.sections if s.has_vocals}
    assert kinds[("Verse", 1)] == 0 and kinds[("Verse", 2)] == 1 and kinds[("Bridge", 1)] == 1
    assert {v for (k, _), v in kinds.items() if k == "Chorus"} == {0}
    (a, sa), (b, sb) = split_for_duet(plan, tracks["melody_data"], tracks["silben"])
    total = sum(d for _, d in tracks["melody_data"])
    assert sum(d for _, d in a) == pytest.approx(total) and sum(d for _, d in b) == pytest.approx(total)
    assert len(sa) + len(sb) == len(tracks["silben"])
    assert len(sa) == sum(p is not None for p, _ in a) and len(sb) == sum(p is not None for p, _ in b)


@pytest.fixture
def fake_neutrino(tmp_path, monkeypatch):
    """NEUTRINO mit zwei Stimmen, das jede Partitur als Sinus singt und sich merkt, wer was gesungen hat."""
    root = tmp_path / "NEUTRINO"
    for singer in ("MERROW", "REINA"):
        (root / "model" / singer).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "NEUTRINO.exe").write_text("")
    calls = []

    def sing(xml, wav, neutrino_dir, model_dir, style_shift=0, **kw):
        calls.append((os.path.basename(xml), os.path.basename(model_dir)))
        t = np.arange(48000 * 3) / 48000
        sf.write(wav, 0.2 * np.sin(2 * np.pi * 440 * t), 48000)
        return True

    monkeypatch.setattr(vocal_synthesizer, "neutrino_synthese", sing)
    return root, calls


def duet_settings(tmp_path, root, partner="REINA", sections=("Verse", "Chorus", "Verse", "Chorus")):
    return SongSettings(active_sections=list(sections), output_ordner=str(tmp_path / "out"), neutrino_pfad=str(root),
                        singer="MERROW", duet_singer=partner, harmonies=False, final_choir=False, section_style=False)


def test_duet_sings_with_both_voices(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    s = duet_settings(tmp_path, root)
    tracks, _ = compose(s, seed=3)
    vocals = _synthesize_vocals(s, tracks, s.output_dir())
    assert ("vocals_duett_1.xml", "MERROW") in calls and ("vocals_duett_2.xml", "REINA") in calls
    assert ("vocals_harmony.xml", "REINA") in calls          # im Refrain singt die zweite Stimme die zweite Stimme
    audio, _ = sf.read(vocals)
    left, right = np.sqrt(np.mean(audio ** 2, axis=0))
    assert 0.5 < left / right < 2.0


def test_duet_partner_missing_falls_back_to_one_voice(tmp_path, fake_neutrino):
    root, calls = fake_neutrino
    s = duet_settings(tmp_path, root, partner="NAKUMO", sections=("Verse", "Chorus"))
    tracks, _ = compose(s, seed=3)
    _synthesize_vocals(s, tracks, s.output_dir())
    assert [c[0] for c in calls] == ["vocals.xml"]


def test_zip_carries_the_ust_files(tmp_path):
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"), duet_singer="REINA")
    tracks, seed = compose(s, seed=2)
    _write_ust(s, tracks, s.output_dir())
    result = SongResult(seed=seed, output_dir=s.output_dir(), settings=s)
    with zipfile.ZipFile(exportiere_projekt(result, str(tmp_path / "song.zip"))) as z:
        assert {f"Gesang/{name}" for name in UST_FILES} <= set(z.namelist())


def test_ust_files_are_written_without_neutrino(tmp_path):
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"))
    tracks, _ = compose(s, seed=2)
    written = _write_ust(s, tracks, s.output_dir())
    assert [os.path.basename(p) for p in written] == ["vocals.ust", "vocals_harmony.ust"]
    duet = _write_ust(s.with_updates(duet_singer="REINA"), tracks, s.output_dir())
    assert [os.path.basename(p) for p in duet] == list(UST_FILES)
