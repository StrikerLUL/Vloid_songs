# test_alles_130.py – alle Neuerungen aus 1.3.0 zusammen: jeder Stil schreibt einen ganzen Song, der stimmt
import pytest

import melody_writer
import pipeline
from settings import SongSettings
from styles import STYLES

SECTIONS = ["Intro", "Verse", "PreChorus", "Chorus", "Verse", "PreChorus", "Chorus", "Spoken", "Bridge", "Chorus",
            "Outro"]


@pytest.mark.parametrize("style", list(STYLES))
def test_every_style_writes_a_whole_song_with_everything_new_switched_on(tmp_path, style, new_composition):
    s = SongSettings(output_ordner=str(tmp_path), style=style, active_sections=SECTIONS)
    assert all(getattr(s, name) for name in pipeline.NEW_COMPOSITION), "ab Werk ist alles an"
    tracks, _ = pipeline.compose(s, seed=5)
    plan = tracks["plan"]
    end = plan.total_beats * plan.seconds_per_beat
    for inst, notes in tracks.items():
        if not (isinstance(notes, list) and notes and hasattr(notes[0], "velocity")):
            continue
        for n in notes:
            assert 0 <= n.pitch <= 127 and 1 <= n.velocity <= 127, (inst, n)
            assert -1e-6 <= n.start < n.end <= end + 8.0, (inst, n)
    # der Gesang: einstimmig, in der Lage der Stimme (der Höhepunkt darf ein wenig darüber), eine Silbe je Ton
    sung = sorted(tracks["vocal_melody"], key=lambda n: n.start)
    assert all(b.start >= a.end - 1e-6 for a, b in zip(sung, sung[1:]))
    lo, hi = plan.vocal_range
    assert lo - 3 <= min(n.pitch for n in sung) and max(n.pitch for n in sung) <= hi + melody_writer.CLIMAX_ABOVE
    assert len(tracks["silben"]) == sum(1 for pitch, _ in tracks["melody_data"] if pitch is not None)
    assert sum(d for _, d in tracks["melody_data"]) <= plan.total_beats + 1e-6
