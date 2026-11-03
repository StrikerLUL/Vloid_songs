"""Phrase repair: scoped work, exact preservation, transactional failure and cancel."""
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from test_sektions_stil import singing_neutrino  # noqa: F401

import cancel
import exporter
import mixer
import pipeline
import singing
import vocal_repair as repair
from settings import SongSettings


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "song"
    root.mkdir()
    settings = SongSettings(seed=42, bpm=120, output_ordner=str(root), vocal_engine="Vorschau",
                            vocal_versions=False, vocal_chops=False, id3_tags=False, own_vocal="",
                            duet_singer="", group_vocals=0)
    section = SimpleNamespace(start=0., end=16., resume=None, chords=[], kind="Verse")
    tracks = dict(melody_data=[(None, 2), (60, 1), (None, 3), (62, 1), (None, 3), (64, 1)],
                  silben=["あ", "い", "う"],
                  plan=SimpleNamespace(sections=[section], bar_beats=4., seconds_per_beat=.5, progressions={}, style=SimpleNamespace(name="test")))
    rng = np.random.default_rng(42)
    original = rng.normal(0, .05, (7000, 2))
    sf.write(root / "vocals.wav", original, 1000, subtype="FLOAT")
    sf.write(root / "bass.wav", np.zeros((7000, 2)), 1000, subtype="FLOAT")
    sf.write(root / "vocals_harmony.wav", original * .2, 1000, subtype="FLOAT")
    sf.write(root / "final_mix.wav", original, 1000, subtype="FLOAT")
    result = pipeline.SongResult(42, str(root), settings=settings, repair_tracks=tracks,
                                 vocals_wav=str(root / "vocals.wav"), mix_wav=str(root / "final_mix.wav"),
                                 harmony_wav=str(root / "vocals_harmony.wav"), wav_files={"bass": str(root / "bass.wav")})
    import vocal_check
    vocal_check.record(str(root), settings, "Vorschau")
    result.repair_sources = repair.source_signature(result)
    monkeypatch.setattr(pipeline.mixdown, "mix_arguments", lambda *a, **k: {})
    monkeypatch.setattr(mixer, "mische_spuren", lambda **kw: sf.write(kw["output_pfad"], original, 1000, subtype="FLOAT"))
    monkeypatch.setattr(exporter, "exportiere_song", lambda *a: None)
    monkeypatch.setattr(singing, "vocal_key", lambda *a: "repaired")
    monkeypatch.setattr(pipeline, "compose", lambda *a, **k: pytest.fail("must not compose"))
    monkeypatch.setattr(pipeline.rendering, "_render_instruments", lambda *a: pytest.fail("must not render band"))
    def synth(settings, scoped, out):
        assert sum(p is not None for p, _ in scoped["melody_data"]) == 1
        assert scoped["silben"] == ["い"]
        assert sum(d for _, d in scoped["melody_data"]) <= 4
        path = str(Path(out) / "vocals.wav")
        sf.write(path, np.ones((3000, 1)) * .3, 1000, subtype="FLOAT")
        return path
    monkeypatch.setattr(repair, "_synthesize", synth)
    cancel.reset()
    yield settings, result
    cancel.reset()


def test_lists_stable_phrases_without_composition(source):
    settings, result = source
    phrases = pipeline.list_vocal_phrases(result)
    assert [(p.index, p.start, p.end, p.text, p.section) for p in phrases] == [
        (0, 1., 1.5, "あ", "Verse"), (1, 3., 3.5, "い", "Verse"), (2, 5., 5.5, "う", "Verse")]
    assert pipeline.list_vocal_phrases(pipeline.SongResult(1, "missing")) == []


def test_repair_preserves_unselected_samples_and_backing_bytes(source):
    settings, result = source
    before = {p.name: p.read_bytes() for p in Path(result.output_dir).iterdir()}
    updated = pipeline.repair_vocal_phrase(settings, result, 1, keep_history=False)
    original, rate = sf.read(result.vocals_wav, always_2d=True)
    fixed, _ = sf.read(updated.vocals_wav, always_2d=True)
    assert fixed.shape == original.shape
    assert np.array_equal(fixed[:2800], original[:2800])
    assert np.array_equal(fixed[3750:], original[3750:])
    assert not np.array_equal(fixed[3000:3500], original[3000:3500])
    assert updated is not result and updated.output_dir != result.output_dir
    assert updated.audio == updated.mix_wav and updated.history is None
    assert Path(updated.wav_files["bass"]).read_bytes() == before["bass.wav"]
    assert Path(updated.harmony_wav).read_bytes() == before["vocals_harmony.wav"]
    assert {p.name: p.read_bytes() for p in Path(result.output_dir).iterdir()} == before
    assert singing._sung_before(updated.output_dir, "repaired")
    assert updated.repair_sources == repair.source_signature(updated)


@pytest.mark.parametrize("phase", ["synthesis", "mix", "export", "cancel"])
def test_failure_or_cancel_preserves_original_and_leaves_no_stage(source, monkeypatch, phase):
    settings, result = source
    before = {p.name: p.read_bytes() for p in Path(result.output_dir).iterdir()}
    def fail(*a, **k):
        if phase == "cancel":
            cancel.request()
            cancel.check()
        raise RuntimeError("failure")
    if phase in ("synthesis", "cancel"):
        monkeypatch.setattr(repair, "_synthesize", fail)
    elif phase == "mix":
        monkeypatch.setattr(mixer, "mische_spuren", fail)
    else:
        monkeypatch.setattr(exporter, "exportiere_song", fail)
    with pytest.raises(cancel.Cancelled if phase == "cancel" else RuntimeError):
        pipeline.repair_vocal_phrase(settings, result, 1)
    assert {p.name: p.read_bytes() for p in Path(result.output_dir).iterdir()} == before
    assert list(Path(result.output_dir).parent.iterdir()) == [Path(result.output_dir)]


@pytest.mark.parametrize("index", [-1, 3, True, "1"])
def test_invalid_selection_is_rejected(source, index):
    settings, result = source
    with pytest.raises(ValueError):
        pipeline.repair_vocal_phrase(settings, result, index, keep_history=False)


def test_unrelated_edits_and_overwritten_stems_are_rejected(source):
    settings, result = source
    with pytest.raises(ValueError, match="einzelne Phrase"):
        pipeline.repair_vocal_phrase(settings.with_updates(bpm=130), result, 1)
    with pytest.raises(ValueError, match="gewählte Phrase"):
        pipeline.repair_vocal_phrase(settings.with_updates(phrase_fixes={"2": {"style_shift": 2}}), result, 1)
    Path(result.wav_files["bass"]).write_bytes(b"different song")
    with pytest.raises(ValueError, match="überschrieben"):
        pipeline.repair_vocal_phrase(settings, result, 1)


def test_history_is_recorded_once_after_publication(source, monkeypatch):
    import history
    import project
    settings, result = source
    recorded = []
    def record(path, used, folder, **kwargs):
        assert Path(path).is_file() and ".vocal-repair-" not in path
        assert folder == settings.output_dir()
        recorded.append(path)
        return SimpleNamespace(audio=path + ".history")
    monkeypatch.setattr(history, "record", record)
    monkeypatch.setattr(project, "save", lambda *a: None)
    monkeypatch.setattr(project, "keep_map", lambda *a: None)
    updated = pipeline.repair_vocal_phrase(settings, result, 1)
    assert len(recorded) == 1 and updated.history == recorded[0] + ".history"


@pytest.mark.parametrize("subtype", ["PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"])
def test_splice_keeps_exact_unselected_samples_and_format(tmp_path, subtype):
    source, fresh, target = [str(tmp_path / n) for n in ("source.wav", "fresh.wav", "target.wav")]
    sf.write(source, np.random.default_rng(1).uniform(-.8, .8, (2000, 2)), 1000, subtype=subtype)
    sf.write(fresh, np.full(1000, .2), 500, subtype="FLOAT")
    repair._splice(source, fresh, target, .5, 1.5, .2)
    before, _ = sf.read(source, always_2d=True)
    after, _ = sf.read(target, always_2d=True)
    assert np.array_equal(before[:500], after[:500])
    assert np.array_equal(before[1500:], after[1500:])
    assert sf.info(target).subtype == subtype


def test_real_neutrino_path_receives_only_compact_selected_score(tmp_path, singing_neutrino):
    from test_sektions_stil import song
    from settings import edit_key
    root, calls, _ = singing_neutrino
    settings = song(tmp_path, root, section_style=False, vocal_takes=1)
    tracks, _ = pipeline.compose(settings)
    result = pipeline.SongResult(settings.seed, settings.output_dir(), settings=settings,
                                 repair_tracks=tracks, vocals_wav=str(tmp_path / "source.wav"))
    sf.write(result.vocals_wav, np.zeros(48000), 48000)
    phrases = repair.list_phrases(result)
    phrase = phrases[-1]
    edited = settings.with_updates(phrase_fixes={edit_key(phrase.start * settings.bpm / 60):
                                                {"style_shift": 3, "singer": "REINA"}})
    scoped, selected, offset = repair._scoped(edited, tracks, phrase)
    assert offset > 0
    assert sum(d for _, d in selected["melody_data"]) < sum(d for _, d in tracks["melody_data"])
    assert selected["silben"] == tracks["silben"][-len(selected["silben"]):]
    out = tmp_path / "short"
    out.mkdir()
    wav = repair._synthesize(scoped, selected, str(out))
    assert calls == [("vocals.xml", "REINA", 3)]
    assert sf.info(wav).duration < (phrase.end - phrase.start) + 5
    assert np.any(sf.read(wav)[0])



def test_chops_are_preserved_not_regenerated(source, monkeypatch):
    settings, result = source
    path = Path(result.output_dir) / "chops.wav"
    sf.write(path, np.linspace(-.2, .2, 7000), 1000, subtype="FLOAT")
    result.repair_sources = repair.source_signature(result)
    monkeypatch.setattr(pipeline, "_vocal_chops", lambda *a: pytest.fail("chops must not be regenerated"))
    updated = pipeline.repair_vocal_phrase(settings, result, 1, keep_history=False)
    assert (Path(updated.output_dir) / "chops.wav").read_bytes() == path.read_bytes()


@pytest.mark.parametrize("engine", ["NEUTRINO", "VOICEVOX", None])
def test_fallback_or_missing_provenance_rejected_before_synthesis(source, monkeypatch, engine):
    import json
    settings, result = source
    path = Path(result.output_dir) / "gesang.json"
    if engine:
        path.write_text(json.dumps({"engine": engine}), encoding="utf-8")
    else:
        path.unlink()
    result.repair_sources = repair.source_signature(result)
    monkeypatch.setattr(repair, "_synthesize", lambda *a: pytest.fail("must not synthesize fallback source"))
    with pytest.raises(ValueError, match="Ersatzstimme"):
        pipeline.repair_vocal_phrase(settings, result, 1)


@pytest.mark.parametrize("field", ["harmony_wav", "choir_wav"])
def test_missing_secondary_stem_fails_before_publication(source, field):
    settings, result = source
    setattr(result, field, str(Path(result.output_dir) / "missing.wav"))
    with pytest.raises(ValueError, match="Begleitstimme"):
        pipeline.repair_vocal_phrase(settings, result, 1)
    assert list(Path(result.output_dir).parent.iterdir()) == [Path(result.output_dir)]


def test_choir_and_harmony_paths_remapped_and_followup_repair_is_safe(source):
    settings, result = source
    result.choir_wav = str(Path(result.output_dir) / "vocals_chor.wav")
    sf.write(result.choir_wav, np.ones(7000) * .02, 1000)
    result.repair_sources = repair.source_signature(result)
    first = pipeline.repair_vocal_phrase(settings, result, 1, keep_history=False)
    second = pipeline.repair_vocal_phrase(first.settings, first, 1, keep_history=False)
    for updated in (first, second):
        assert Path(updated.harmony_wav).parent == Path(updated.output_dir)
        assert Path(updated.choir_wav).parent == Path(updated.output_dir)
        assert Path(updated.choir_wav).read_bytes() == Path(result.choir_wav).read_bytes()


@pytest.mark.parametrize("length", [100, 1000])
def test_truncated_engine_output_cannot_erase_phrase(source, monkeypatch, length):
    settings, result = source
    def truncated(settings, tracks, out):
        path = str(Path(out) / "truncated.wav")
        sf.write(path, np.ones(length) * .2, 1000, subtype="FLOAT")
        return path
    monkeypatch.setattr(repair, "_synthesize", truncated)
    original = Path(result.vocals_wav).read_bytes()
    with pytest.raises(RuntimeError, match="abgeschnitten"):
        pipeline.repair_vocal_phrase(settings, result, 1)
    assert Path(result.vocals_wav).read_bytes() == original
    assert list(Path(result.output_dir).parent.iterdir()) == [Path(result.output_dir)]


def test_prepublication_cancellation_saves_no_history(source, monkeypatch):
    import history
    settings, result = source
    monkeypatch.setattr(history, "record", lambda *a, **k: pytest.fail("cancel must not record history"))
    def progress(fraction, message):
        if fraction >= .98:
            cancel.request()
    with pytest.raises(cancel.Cancelled):
        pipeline.repair_vocal_phrase(settings, result, 1, progress)
    assert list(Path(result.output_dir).parent.iterdir()) == [Path(result.output_dir)]


def test_project_reopening_recaptures_repair_metadata(tmp_path, singing_neutrino, monkeypatch):
    import project
    import vocal_check
    from test_sektions_stil import song
    root, _, _ = singing_neutrino
    settings = song(tmp_path, root, section_style=False, vocal_takes=1, vocal_versions=False,
                    vocal_chops=False, id3_tags=False)
    tracks, _ = pipeline.compose(settings)
    vocal = singing._synthesize_vocals(settings, tracks, settings.output_dir())
    history_audio = tmp_path / "saved.wav"
    shutil.copyfile(vocal, history_audio)
    assert project.save(settings.output_dir(), tracks, str(history_audio))
    Path(vocal).unlink()
    assert project.unpack(str(history_audio), settings, settings.output_dir())[0]
    monkeypatch.setattr(singing, "_sing_preview", lambda *a: pytest.fail("reopened cached vocals should not synthesize"))
    monkeypatch.setattr(singing, "_sing_neutrino", lambda *a, **k: pytest.fail("must reuse restored vocals"))
    monkeypatch.setattr(pipeline.rendering, "_render_instruments", lambda *a: {})
    monkeypatch.setattr(pipeline.rendering, "_render_fx", lambda *a: None)
    monkeypatch.setattr(pipeline, "_hearing_check", lambda *a: None)
    monkeypatch.setattr(pipeline, "_polish", lambda *a: None)
    monkeypatch.setattr(pipeline.mixdown, "mix_arguments", lambda *a, **k: {})
    monkeypatch.setattr(mixer, "mische_spuren", lambda **k: shutil.copyfile(k["spur_pfade"][0], k["output_pfad"]))
    monkeypatch.setattr(exporter, "exportiere_song", lambda *a, **k: None)
    reopened = pipeline.generate_song(settings.with_updates(reuse_steps=True), keep_history=False)
    assert reopened.repair_tracks and reopened.repair_sources
    assert pipeline.list_vocal_phrases(reopened)
    assert reopened.repair_sources == repair.source_signature(reopened)
    assert vocal_check.read(reopened.output_dir)["engine"] == "NEUTRINO"

