# test_video_172.py – „IndexError: index 9110896 is out of bounds for axis 0 with size 9110896“ (1.7.2)
#
# musikvideo.render misst das Spektrum für ceil(Länge × 30) + 1 Bilder, das letzte liegt also bis zu zwei Bilder
# hinter dem Ende des Songs. analyse hatte dahinter nur 2048 Samples Stille; bei 44,1 und 48 kHz liest das letzte
# Bild weiter, und je nach Länge des Songs brach jedes Video ab (seit 1.5.0, bei etwa jedem dritten Song).
import math

import numpy as np
import pytest

import musikvideo


def _frames(samples: int, rate: int) -> int:
    """So viele Bilder misst render für einen Song dieser Länge."""
    return int(math.ceil(samples / rate * musikvideo.FPS)) + 1


@pytest.mark.parametrize("rate", [22050, 44100, 48000])
def test_every_song_length_reaches_its_last_frame(rate):
    step = rate // musikvideo.FPS                 # Samples pro Bild: alle Reste innerhalb eines Bildes durchgehen
    for extra in range(0, step, max(1, step // 40)):
        samples = rate * 3 + extra
        frames = _frames(samples, rate)
        sound = musikvideo.analyse(np.zeros(samples, np.float32), rate, frames)
        assert sound.bands.shape == (frames, musikvideo.BANDS) and len(sound.level) == frames


def test_the_lofi_song_from_the_error_report():
    samples, rate = 9106800, 44100                # 206,5 s; mit 2 × 2048 Samples Stille genau die 9110896
    tone = np.sin(np.arange(samples, dtype=np.float32) * (2 * np.pi * 440 / rate)).astype(np.float32)
    sound = musikvideo.analyse(tone, rate, _frames(samples, rate))
    assert sound.level[len(sound.level) // 2] > 0.5         # der Song selbst wird gemessen wie bisher
    assert sound.level[-1] < sound.level[len(sound.level) // 2]
