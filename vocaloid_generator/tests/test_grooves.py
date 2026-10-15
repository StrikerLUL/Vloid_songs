# test_grooves.py – Grooves und Fills echter Schlagzeuger (setup_grooves.py, grooves.py, drums.py)
import io
import json
import random
import sys
import zipfile

import pretty_midi
import pytest

import config
import drums
import einrichten
import grooves
import orchestrator
import systemcheck
from orchestrator import orchestrate_song
from settings import SongSettings
from song_plan import Section

sys.path.insert(0, config.REPO_ROOT)
import setup_grooves  # noqa: E402

BPM = 120


def _midi(hits) -> bytes:
    """hits: [(Schlag, TD-11-Ton, Anschlag)] bei 120 BPM."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=BPM)
    inst = pretty_midi.Instrument(program=0, is_drum=True)
    inst.notes = [pretty_midi.Note(v, p, b * 0.5, b * 0.5 + 0.05) for b, p, v in hits]
    midi.instruments.append(inst)
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


def _rock_bar(start: float, offset: float = 0.02) -> list:
    """Bassdrum auf 1 und 3, Snare (Rand) auf 2 und 4, Hi-Hat-Kante in Achteln, knapp hinter dem Raster."""
    hits = [(start + s / 2 + offset, 22, 80) for s in range(8)]
    hits += [(start + offset, 36, 110), (start + 2 + offset, 36, 100), (start + 1, 40, 120), (start + 3, 40, 118)]
    return hits


def _fill_take() -> list:
    """Ein Takt Groove, dann ein Takt mit Toms auf den Schlägen 3 und 4."""
    hits = _rock_bar(0)
    hits += [(4, 36, 100), (5, 38, 100), (6, 48, 110), (6.5, 50, 105), (7, 45, 112), (7.5, 43, 120)]
    return hits


@pytest.fixture
def dataset(tmp_path):
    files = {
        "a/1_rock-straight_120_beat_4-4.mid": (_midi([h for b in range(9) for h in _rock_bar(b * 4)]), "rock", "beat",
                                               "4-4", 18.0),
        "a/2_rock-shuffle_120_beat_4-4.mid": (_midi([(b * 4 + k / 3, 42, 80) for b in range(4) for k in range(12)]
                                                    + [(b * 4, 36, 100) for b in range(4)]
                                                    + [(b * 4 + 1, 38, 100) for b in range(4)]),
                                              "rock", "beat", "4-4", 8.0),
        "a/3_jazz-swing_120_beat_4-4.mid": (_midi([h for b in range(4) for h in _rock_bar(b * 4)]), "jazz", "beat",
                                            "4-4", 8.0),
        "a/4_rock-waltz_120_beat_3-4.mid": (_midi([h for b in range(4) for h in _rock_bar(b * 4)]), "rock", "beat",
                                            "3-4", 8.0),
        "a/5_rock-fill_120_fill_4-4.mid": (_midi(_fill_take()), "rock", "fill", "4-4", 3.9),
    }
    path = tmp_path / "groove.zip"
    with zipfile.ZipFile(path, "w") as z:
        rows = ["drummer,session,id,style,bpm,beat_type,time_signature,midi_filename,audio_filename,duration,split"]
        for name, (data, style, kind, sig, duration) in files.items():
            z.writestr(f"groove/{name}", data)
            rows.append(f"d,s,i,{style}/x,{BPM},{kind},{sig},{name},,{duration},train")
        z.writestr("groove/info.csv", "\n".join(rows) + "\n")
    return path.as_uri()


def test_setup_keeps_straight_bars_and_real_fills(tmp_path, dataset):
    ordner = tmp_path / "grooves"
    assert setup_grooves.setup(str(ordner), dataset)
    data = json.loads((ordner / "grooves.json").read_text())
    assert (ordner / "LIZENZ.txt").is_file() and not (ordner / "groove-midionly.zip").exists()
    assert len(data["phrases"]) == 2                                  # neun gerade Takte: zwei Phrasen zu vier
    assert all(p["style"] == "rock" and len(p["bars"]) == 4 for p in data["phrases"])   # kein Shuffle, Jazz, 3/4
    pitches = {pitch for p in data["phrases"] for bar in p["bars"] for _, pitch, _ in bar}
    assert pitches == {36, 38, 42}                                   # Kante und Rand auf General MIDI
    first = data["phrases"][0]["bars"][0]
    assert min(pos for pos, _, _ in first) == pytest.approx(0.02, abs=3e-3)   # das Timing des Schlagzeugers
    assert len(data["fills"]) == 1
    assert {pitch for _, pitch, _ in data["fills"][0]["hits"]} >= {48, 45, 43}


def test_setup_with_a_broken_download(tmp_path):
    broken = tmp_path / "kaputt.zip"
    broken.write_bytes(b"kein zip")
    assert not setup_grooves.setup(str(tmp_path / "grooves"), broken.as_uri())
    assert not setup_grooves.setup(str(tmp_path / "grooves"), (tmp_path / "fehlt.zip").as_uri())


def _phrase(density: int, style: str = "rock", bpm: float = BPM) -> dict:
    bar = [[s / 4 + 0.01, 42, 70] for s in range(0, 16, 16 // density)] + [[0.0, 36, 100], [1.0, 38, 100]]
    return {"style": style, "bpm": bpm, "bars": [bar] * 4}


@pytest.fixture
def library(tmp_path, monkeypatch):
    folder = tmp_path / "grooves"
    folder.mkdir()
    data = {"version": 1, "phrases": [_phrase(d) for d in (2, 4, 8, 16)] + [_phrase(4, "hiphop", 90)],
            "fills": [{"style": "rock", "bpm": BPM, "hits": [[2.0, 48, 100], [2.5, 45, 100], [3.0, 43, 110]]}]}
    (folder / "grooves.json").write_text(json.dumps(data))
    monkeypatch.setattr(grooves, "FOLDER", str(folder))
    monkeypatch.setattr(grooves, "PICK_SPREAD", 0.0)
    return data


def test_quiet_parts_get_loose_phrases_and_loud_parts_dense_ones(library):
    drummer = grooves.for_song(BPM, "seed")
    assert drummer.plays("pop_verse") and not drummer.plays("four_floor") and not drummer.plays("fb_verse")
    assert len(drummer.bar("rock_verse", 0.0, 0)) == 4                # zwei Hi-Hats, Bassdrum, Snare
    assert len(drummer.bar("rock_chorus", 1.0, 0)) == 18
    assert len(drummer.bar("rock_verse", 1.0, 1)) == 4                # einmal gewählt, bleibt die Phrase
    pos = sorted(p for p, pitch, _ in drummer.bar("rock_chorus", 1.0, 0) if pitch == 42)[1]
    assert pos == pytest.approx(0.25 + 0.01 * grooves.FEEL)           # näher am Raster, aber nicht ganz
    loud = max(v for _, _, v in drummer.bar("rock_chorus", 1.0, 0))
    soft = max(v for _, _, v in grooves.Drummer(library, BPM, "x").bar("rock_chorus", 0.0, 0))
    assert loud > soft


def test_halftime_uses_the_phrase_closest_in_tempo(library):
    drummer = grooves.Drummer(library, 90, "seed")
    assert drummer.phrase("halftime", 0.5)["style"] == "hiphop"


def _section(kind="Verse", next_kind="Chorus", bars=4, energy=0.6, index=1) -> Section:
    return Section(kind=kind, occurrence=1, index=index, start=0.0, bars=bars, tonic=0, mode="major", energy=energy,
                   has_vocals=True, next_kind=next_kind)


def test_sections_play_the_phrase_and_end_with_a_real_fill(library):
    drummer = grooves.for_song(BPM, "seed")
    events = drums.drum_section(_section(), "pop_verse", random.Random(1), drummer)
    last_bar = [e for e in events if e.start >= 12]
    assert {e.pitch for e in last_bar} >= {48, 45, 43}                # der echte Fill
    assert any(abs(e.start - round(e.start * 4) / 4) > 1e-6 for e in events if e.start < 12)   # echtes Timing
    assert sum(e.pitch == drums.CRASH for e in events if e.start < 0.1) == 1
    assert sum(e.pitch == drums.KICK for e in events if e.start < 0.1) == 1     # keine doppelte Bassdrum


def test_built_in_rolls_tambourine_and_electronic_grooves_stay(library):
    drummer = grooves.for_song(BPM, "seed")
    pre = drums.drum_section(_section("PreChorus"), "pop_pre", random.Random(1), drummer)
    assert any(e.pitch == drums.TAMBOURINE for e in pre)
    roll = [e for e in pre if e.start >= 12]
    assert {e.pitch for e in roll} <= {drums.SNARE, drums.KICK, drums.CRASH}   # der Wirbel in den Refrain
    edm = drums.drum_section(_section(), "four_floor", random.Random(1), drummer)
    assert edm == drums.drum_section(_section(), "four_floor", random.Random(1))


def test_without_library_drums_stay_built_in(tmp_path):
    assert grooves.for_song(BPM, "seed") is None and "fehlen" in grooves.status()
    assert systemcheck.check_grooves(SongSettings(), str(tmp_path)) == (None, "Echte Grooves nicht geladen")


def _song(tmp_path, name, **kwargs) -> list:
    random.seed(5)
    tracks = orchestrate_song("pop", BPM, ["Verse", "Chorus"], "C", "major",
                              {"Verse": {"bars": 4}, "Chorus": {"bars": 4}}, output_dir=str(tmp_path / name),
                              style="J-Pop Energy", **kwargs)
    return [(round(n.start, 4), n.pitch) for n in tracks["drums"]]


def test_songs_use_real_grooves_only_when_switched_on_and_straight(library, tmp_path):
    built_in = _song(tmp_path, "a")
    assert _song(tmp_path, "b", real_grooves=True) != built_in
    assert _song(tmp_path, "c", real_grooves=True, swing=0.4) == _song(tmp_path, "d", swing=0.4)


def test_the_default_light_swing_keeps_the_real_drummer(library, tmp_path):
    # Der Grundwert des Swing-Reglers (0,12) ist nur ein Hauch: der echte Schlagzeuger spielt trotzdem, mit seinem
    # eigenen Timing (bis 1.1 blieben die Grooves dadurch fast immer aus)
    light = SongSettings().swing
    assert 0 < light < orchestrator.GROOVE_SWING_UNTIL
    assert _song(tmp_path, "e", real_grooves=True, swing=light) != _song(tmp_path, "f", swing=light)
    assert _song(tmp_path, "g", real_grooves=True, swing=light) == _song(tmp_path, "h", real_grooves=True)


def test_setup_and_systemcheck_know_the_grooves(library, tmp_path):
    assert einrichten.is_installed(einrichten.find("grooves"))
    ok, message = systemcheck.check_grooves(SongSettings(), str(tmp_path))
    assert ok and "5 Phrasen und 1 Fills" in message
    assert SongSettings().real_grooves and not SongSettings(real_grooves=False).real_grooves
