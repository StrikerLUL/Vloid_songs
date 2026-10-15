# test_schlagzeug.py – Das echte Schlagzeug: Laden und Mischen (setup_drums.py) und Spielen (drum_kit.py)
import os
import sys

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
import drum_kit
import einrichten
import mixer
import rendering
import systemcheck
from settings import SongSettings

sys.path.insert(0, config.REPO_ROOT)
import setup_drums  # noqa: E402

MACRO = "#define $v41l 1        #define $v41h 63\n#define $v42l 64      #define $v42h 127\n"


def _region_text(count: int) -> str:
    """Zwei Anschlag-Schichten, in jeder count // 2 wechselnde Aufnahmen, wie in den Dateien des DRS Kits."""
    lines = ["#define $instr X", "group_label=$instr"]
    half = count // 2
    for n in range(1, count + 1):
        layer, pos = ("v41", n) if n <= half else ("v42", n - half)
        lines.append(f"<region> lovel=${layer}l hivel=${layer}h amp_velcurve_${layer}h=1 region_label={n} "
                     f"sample=$instr/{n}-$instr-$mic.$ext seq_length={half} seq_position={pos}")
    return "\n".join(lines) + "\n"


def _hit(path, level: float, seconds: float = 0.3, flip: bool = False) -> None:
    t = np.arange(int(seconds * 44100)) / 44100
    audio = level * np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.08)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(str(path), -audio if flip else audio, 44100, subtype="PCM_24", format="FLAC")


@pytest.fixture
def quelle(tmp_path):
    """Ein nachgebautes DRS Kit mit Bassdrum, Snare und offenem Hi-Hat, je vier Schläge."""
    src = tmp_path / "DRSKit"
    (src / "Data" / "region").mkdir(parents=True)
    (src / "Data" / "macro.txt").write_text(MACRO)
    for piece in drum_kit.PIECES:
        if piece.name not in ("Kdrum_with_contact", "Snare", "Hihat_open", "Hihat_closed"):
            continue
        (src / "Data" / "region" / f"{piece.name}.txt").write_text(_region_text(4))
        mics = [m for m, _, _ in piece.close] + [m for m, _ in drum_kit.ROOM]
        for n in range(1, 5):
            for mic in mics:
                _hit(src / "Samples" / piece.name / f"{n}-{piece.name}-{mic}.flac", 0.1 * n,
                     seconds=1.5 if piece.name == "Hihat_open" else 0.3, flip=mic == "Snare_bottom")
    return src.as_uri() + "/"


def _setup(tmp_path, quelle, nur=("Kdrum", "Snare", "Hihat_open", "Hihat_closed")):
    ordner = tmp_path / "kit"
    ok = setup_drums.setup(list(nur), str(ordner), quelle)
    return ok, ordner


def test_layers_and_hits_are_read_like_the_drs_files():
    layers = setup_drums.anschlag_schichten(MACRO)
    assert layers == {"v41": (1, 63), "v42": (64, 127)}
    hits = setup_drums.schlaege(_region_text(4), layers)
    assert [h["n"] for h in hits] == [1, 2, 3, 4]
    assert hits[2] == {"n": 3, "lovel": 64, "hivel": 127, "seq_length": 2, "seq_position": 1}


def test_close_mics_are_turned_the_same_way_before_mixing():
    t = np.arange(4000) / 44100
    top = np.sin(2 * np.pi * 200 * t).astype(np.float32)
    stereo = setup_drums.mischen([(top, 0.0, True), (-top, 0.0, True), (top, -1.0, False)])
    assert stereo.shape == (2, 4000)
    assert np.allclose(stereo[1], 2 * top, atol=1e-5)               # unten umgedreht: verstärkt statt ausgelöscht
    assert np.allclose(stereo[0], 2 * top + np.sqrt(2) * top, atol=1e-5)   # Overhead links nur links


def test_setup_mixes_every_hit_and_writes_the_kit(tmp_path, quelle):
    ok, ordner = _setup(tmp_path, quelle)
    assert ok
    assert (ordner / "DRSKit.sfz").is_file() and (ordner / "LIZENZ.txt").is_file()
    assert sorted(os.listdir(ordner / "Snare")) == ["1.flac", "2.flac", "3.flac", "4.flac", "pegel.json"]
    assert not (ordner / ".laden").exists()                          # die einzelnen Mikrofone sind wieder weg
    audio, rate = sf.read(str(ordner / "Snare" / "1.flac"))
    assert audio.shape[1] == 2 and rate == 44100 and np.abs(audio).max() > 0.9
    text = (ordner / "DRSKit.sfz").read_text()
    assert "<group> key=38" in text and "<group> key=36" in text and text.count("<region>") == 16
    import sfz
    kit = sfz.load(str(ordner / "DRSKit.sfz"))
    soft, loud = kit.pick(38, 30), kit.pick(38, 110)
    assert soft[0].sample.endswith(os.path.join("Snare", "1.flac"))
    assert loud[0].sample.endswith(os.path.join("Snare", "3.flac"))
    assert loud[0].volume > soft[0].volume                           # laute Schläge bleiben lauter
    assert kit.pick(38, 110, turn=1)[0].sample.endswith(os.path.join("Snare", "4.flac"))   # wechselnde Aufnahmen


def test_setup_continues_where_it_stopped(tmp_path, quelle):
    src = tmp_path / "DRSKit" / "Samples" / "Snare"
    moved = tmp_path / "beiseite.flac"
    os.replace(src / "3-Snare-OHL.flac", moved)
    ok, ordner = _setup(tmp_path, quelle, ["Snare"])
    assert not ok
    assert not (ordner / "DRSKit.sfz").exists()                       # halbe Snare: kein Kit
    assert (ordner / "Snare" / "1.flac").is_file() and not (ordner / "Snare" / "3.flac").exists()
    os.replace(moved, src / "3-Snare-OHL.flac")
    os.remove(src / "1-Snare-OHL.flac")                               # schon gemischt: wird nicht neu geladen
    ok, ordner = _setup(tmp_path, quelle, ["Snare"])
    assert ok and (ordner / "Snare" / "3.flac").is_file() and (ordner / "DRSKit.sfz").is_file()
    assert not setup_drums.setup(["Gibtsnicht"], str(ordner), quelle)


def test_setup_without_the_internet_says_so(tmp_path, capsys):
    assert not setup_drums.setup(["Snare"], str(tmp_path / "kit"), (tmp_path / "nichts").as_uri() + "/")
    assert "nicht erreichen" in capsys.readouterr().out


@pytest.fixture
def kit(tmp_path, quelle, monkeypatch):
    ok, ordner = _setup(tmp_path, quelle)
    assert ok
    monkeypatch.setattr(drum_kit, "FOLDER", str(ordner))
    return ordner


def _drums(notes, program=0) -> pretty_midi.PrettyMIDI:
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program, is_drum=True, name="Drums")
    inst.notes = [pretty_midi.Note(v, p, s, s + 0.1) for p, s, v in notes]
    midi.instruments.append(inst)
    return midi


def test_kit_plays_what_it_has_and_leaves_the_rest(kit):
    assert drum_kit.installed() and not drum_kit.complete()
    assert drum_kit.keys() == {36, 38, 42, 46}
    midi = _drums([(36, 0.0, 100), (38, 0.5, 100), (39, 0.5, 100), (54, 1.0, 80), (40, 1.0, 90)])
    audio, rest = drum_kit.render(midi)
    assert audio.shape[0] == 2 and np.abs(audio).max() > 0.01
    assert sorted(n.pitch for n in rest[0].notes) == [39, 54]        # Clap und Tamburin spielt der SoundFont
    hit = int(0.5 * 44100)
    assert np.abs(audio[:, hit:hit + 2000]).max() > 0.01


def test_electronic_kits_stay_with_the_soundfont(kit):
    audio, rest = drum_kit.render(_drums([(36, 0.0, 100)], program=25))
    assert audio is None and len(rest) == 1 and rest[0].notes[0].pitch == 36


def test_without_kit_nothing_changes(tmp_path):
    midi = _drums([(36, 0.0, 100)])
    audio, rest = drum_kit.render(midi)
    assert audio is None and rest == midi.instruments
    assert "fehlt" in drum_kit.status()


def test_hits_ring_until_the_second_next_and_open_hats_close():
    notes = [pretty_midi.Note(100, p, s, s + 0.1) for p, s in
             ((38, 0.0), (38, 0.5), (38, 1.0), (46, 2.0), (42, 2.25), (49, 3.0), (35, 3.0))]
    shaped = {(n.pitch, n.start): n.end for n in drum_kit.shaped(notes)}
    assert shaped[(38, 0.0)] == 1.0                                  # klingt durch den nächsten Schlag hindurch
    assert shaped[(38, 1.0)] == 1.0 + drum_kit.LONGEST
    assert shaped[(46, 2.0)] == 2.25                                 # das Hi-Hat geht zu
    assert shaped[(36, 3.0)] == 3.0 + drum_kit.LONGEST               # 35 spielt die Bassdrum des Kits


def test_mixer_takes_the_kit_for_drum_tracks(kit, tmp_path):
    mid, wav = tmp_path / "drums.mid", tmp_path / "drums.wav"
    _drums([(36, 0.0, 100), (42, 0.25, 80), (38, 0.5, 100)]).write(str(mid))
    mixer.midi_zu_wav(str(mid), str(wav), is_drum=True, real_drums=True)
    audio, _ = sf.read(str(wav))
    assert np.abs(audio).max() > 0.01


def test_switch_and_own_soundfont_decide(tmp_path):
    job = rendering._render_job(SongSettings(), str(tmp_path), "drums")
    assert job["real_drums"] is True
    assert rendering._render_job(SongSettings(), str(tmp_path), "perc")["real_drums"] is False
    assert rendering._render_job(SongSettings(real_drums=False), str(tmp_path), "drums")["real_drums"] is False
    own = tmp_path / "mein.sf2"
    own.write_bytes(b"x")
    assert rendering._render_job(SongSettings(soundfont_pfad=str(own)), str(tmp_path), "drums")["real_drums"] is False


def test_setup_and_systemcheck_know_the_kit(kit, tmp_path):
    component = einrichten.find("drums")
    assert component and os.path.isfile(os.path.join(config.REPO_ROOT, component.script))
    assert not einrichten.is_installed(component)                    # erst wenn alle Trommeln da sind
    ok, message = systemcheck.check_drums(SongSettings(), str(tmp_path))
    assert ok is False and "4 von 13" in message


def test_systemcheck_without_kit(tmp_path):
    assert systemcheck.check_drums(SongSettings(), str(tmp_path)) == (None, "Echtes Schlagzeug nicht geladen")


def test_only_picks_exact_names_first():
    assert [p.name for p in setup_drums.auswahl(["snare"])] == ["Snare"]
    assert [p.name for p in setup_drums.auswahl(["Tom"])] == ["Tom1", "Tom2", "Tom3"]
    assert len(setup_drums.auswahl([])) == len(drum_kit.PIECES)
