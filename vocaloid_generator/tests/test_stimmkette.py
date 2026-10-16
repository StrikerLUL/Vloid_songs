# test_stimmkette.py – Kette pro Stimme und Stil (D5): helle Stimmen weniger spitz, tiefe klarer, Ballade weicher,
# Rock mit mehr Sättigung
import numpy as np
import pytest

import main
import mixer
import mixdown
import separation
import vocal_check
import vocal_tone
from settings import SongSettings

RATE = mixer.SAMPLE_RATE


def test_voices_are_sorted_by_how_high_they_sing():
    assert vocal_tone.voice_kind("MERROW") == "hell" and vocal_tone.voice_kind("merrow") == "hell"
    assert vocal_tone.voice_kind("REINA") == "mittel" and vocal_tone.voice_kind("NAKUMO") == "tief"
    assert vocal_tone.voice_kind(None) == "mittel" and vocal_tone.voice_kind("UNBEKANNT") == "mittel"


def test_the_style_changes_the_voice_tone():
    bright, deep = vocal_tone.for_song("MERROW", "J-Pop Energy"), vocal_tone.for_song("NAKUMO", "J-Pop Energy")
    assert bright.presence_db < vocal_tone.STANDARD.presence_db < deep.presence_db
    assert deep.highpass < bright.highpass
    ballad, rock = vocal_tone.for_song("REINA", "Ballade"), vocal_tone.for_song("REINA", "Rock")
    assert ballad.drive_mix < vocal_tone.STANDARD.drive_mix < rock.drive_mix
    assert ballad.ratio < rock.ratio and ballad.presence_db == pytest.approx(2.0)
    assert vocal_tone.for_song("REINA", "J-Pop Energy") == vocal_tone.STANDARD


def test_a_bright_voice_gets_less_presence_than_a_deep_one():
    rng = np.random.default_rng(0)
    noise = (0.05 * rng.standard_normal((2, 4 * RATE))).astype(np.float32)
    bands = {}
    for singer in ("MERROW", "NAKUMO"):
        out = mixer._channel_chain("vocals", vocal_tone.for_song(singer, "J-Pop Energy"))(noise, RATE)
        bands[singer] = separation.bands_db(out)
    k = min(range(len(separation.BAND_CENTERS)), key=lambda i: abs(separation.BAND_CENTERS[i] - 3150))
    assert bands["MERROW"][k] < bands["NAKUMO"][k] - 1.0


def test_the_pipeline_picks_the_tone_from_who_sang(tmp_path):
    s = SongSettings(style="Rock", singer="NAKUMO")
    vocal_check.record(str(tmp_path), s, "NEUTRINO", "NAKUMO")
    tone = mixdown._vocal_tone(s, str(tmp_path))
    assert tone == vocal_tone.for_song("NAKUMO", "Rock")
    vocal_check.record(str(tmp_path), s, "VOICEVOX", "四国めたん")
    assert mixdown._vocal_tone(s, str(tmp_path)) == vocal_tone.for_song(None, "Rock")
    assert mixdown._vocal_tone(s.with_updates(vocal_tone=False), str(tmp_path)) is None
    assert main.parse_args(["--ohne-stimmkette"]).ohne_stimmkette
