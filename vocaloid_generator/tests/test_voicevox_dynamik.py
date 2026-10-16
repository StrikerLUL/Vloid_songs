# test_voicevox_dynamik.py – VOICEVOX singt die Lautstärke pro Silbe und Phrase selbst (F2)
import numpy as np
import pytest

import main
import pipeline
import singing
import voice_fx
import voicevox
from settings import SongSettings
from test_voice import FakeVoicevox, fake_voicevox  # noqa: F401 – fake_voicevox ist eine Fixture


def synthesis_volume():
    return [r[2]["volume"] for r in FakeVoicevox.requests if r[0] == "/frame_synthesis"]


def test_the_volume_goes_into_the_synthesis(tmp_path, fake_voicevox):  # noqa: F811
    seen = []

    def volume(loud, frame, offset):
        seen.append((frame, offset))
        return loud * np.linspace(0.5, 1.5, len(loud))

    voicevox.sing([(None, 1.0), (64, 2.0)], ["か"], 120, str(tmp_path / "v.wav"), fake_voicevox, singer=3002,
                  volume=volume)
    assert seen == [(1 / 93.75, -voicevox.PAD_FRAMES / 93.75)]
    sent = synthesis_volume()[0]
    assert sent[0] == pytest.approx(0.25) and sent[-1] == pytest.approx(0.75)


def test_the_curve_is_louder_on_stressed_syllables_and_soft_at_the_start():
    data = [(None, 1.0), (60, 1.0), (60, 1.0), (60, 1.0), (60, 1.0)]       # Töne auf Schlag 2, 3, 4 und 1
    times = np.array([0.505, 0.75, 1.25, 1.75])          # Einsatz, Mitte Schlag 2, Schlag 3 (betont), Schlag 4
    db = voice_fx.dynamics_db(data, ["ら"] * 4, 120, [], times, expression=False)
    assert db[0] < db[1] - 3                                              # weicher Einsatz
    assert db[2] > db[1] and db[2] > db[3]                                # Schlag 3 betont


def test_with_voicevox_the_dynamics_are_sung_not_turned_afterwards(tmp_path, fake_voicevox, monkeypatch):  # noqa: F811
    after = []
    monkeypatch.setattr(voice_fx, "syllable_dynamics", lambda *a: after.append("silbe") or True)
    monkeypatch.setattr(voice_fx, "express", lambda *a, **k: after.append("phrase") or True)
    s = SongSettings(active_sections=["Verse", "Chorus"], output_ordner=str(tmp_path / "out"),
                     vocal_engine="VOICEVOX", voicevox_url=fake_voicevox, harmonies=False, final_choir=False)
    tracks, _ = pipeline.compose(s, seed=4)
    singing._synthesize_vocals(s, tracks, s.output_dir())
    sung = np.asarray(synthesis_volume()[0])
    assert after == [] and np.ptp(sung[sung > 0]) > 0.05
    FakeVoicevox.requests.clear()
    singing._synthesize_vocals(s.with_updates(voicevox_dynamics=False), tracks, s.output_dir())
    assert after == ["silbe", "phrase"] and set(synthesis_volume()[0]) == {0.5}
    assert main.parse_args(["--ohne-voicevox-dynamik"]).ohne_voicevox_dynamik
