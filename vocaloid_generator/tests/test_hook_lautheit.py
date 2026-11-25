from types import SimpleNamespace
import random

import numpy as np
import soundfile as sf

import hoer_duell
import pipeline


def test_hook_previews_have_a_shared_loudness_without_boosting(tmp_path):
    rate = 44100
    t = np.arange(rate * 2) / rate
    paths = [tmp_path / "a.wav", tmp_path / "b.wav"]
    for path, amplitude in zip(paths, (0.6, 0.15)):
        sf.write(path, amplitude * np.sin(2 * np.pi * 440 * t), rate, subtype="FLOAT")
    pipeline._match_hook_loudness([SimpleNamespace(preview=str(path)) for path in paths])
    a, _ = sf.read(paths[0], always_2d=True)
    b, _ = sf.read(paths[1], always_2d=True)
    assert abs(hoer_duell._loudness(a, rate) - hoer_duell._loudness(b, rate)) < 0.01
    assert np.max(np.abs(a)) <= 0.151 and np.max(np.abs(b)) <= 0.151


def test_blind_order_preserves_the_original_choices_and_their_identity():
    choices = [SimpleNamespace(number=n) for n in range(1, 4)]
    shuffled = pipeline.blind_hook_choices(choices, random.Random(7))
    assert [choice.number for choice in shuffled] != [1, 2, 3]
    assert {id(choice) for choice in shuffled} == {id(choice) for choice in choices}
    assert [choice.number for choice in choices] == [1, 2, 3]
