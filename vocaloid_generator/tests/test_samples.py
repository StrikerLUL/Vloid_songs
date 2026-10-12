# test_samples.py – der SFZ-Sampler, die Orchester-Aufnahmen (VSCO 2) und ihr Download
import os
import sys

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import config
import pipeline
import sample_library
import sfz
from mixer import midi_zu_wav
from settings import SongSettings

sys.path.insert(0, config.REPO_ROOT)
import setup_samples  # noqa: E402

RATE = 44100


def tone(path, freq, seconds=2.0, lead=0.05, amp=0.5):
    """Eine Stereo-Aufnahme: lead Sekunden Stille, dann ein Sinuston."""
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    t = np.arange(int(seconds * RATE)) / RATE
    wave = np.where(t >= lead, amp * np.sin(2 * np.pi * freq * t), 0.0)
    sf.write(str(path), np.stack([wave, wave], axis=1), RATE, subtype="PCM_16")


def write_sfz(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return str(path)


def peak_hz(audio, start=0.0, end=None):
    mono = audio.mean(axis=0)[int(start * RATE):int(end * RATE) if end else None]
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    return np.fft.rfftfreq(len(mono), 1 / RATE)[np.argmax(spectrum)]


def note(pitch, start, end, velocity=100):
    return pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end)


# ── sfz.py ──────────────────────────────────────────────────────────────────────────

def test_sfz_file_with_headers_comments_and_note_names(tmp_path):
    path = write_sfz(tmp_path / "geige.sfz", """
<control>
default_path=Strings\\Violin Section\\
<global> ampeg_release=0.8 // ausklingen
<group> seq_length=2 seq_position=1
<region> sample=Geige A4.wav key=a4 volume=-3
<region> sample=leise.wav lokey=c4 hikey=b4 pitch_keycenter=f#4 lovel=0 hivel=62
<region> sample=umschalten.wav key=c2 sw_last=24
<group> trigger=release
<region> sample=loslassen.wav key=a4
<group>
<region> sample=hoch.wav lokey=72 hikey=84 pitch_keycenter=78 tune=-12
""")
    regions = sfz.parse(path)
    assert [os.path.basename(r.sample) for r in regions] == ["Geige A4.wav", "leise.wav", "hoch.wav"]
    first, soft, high = regions
    assert first.sample == os.path.normpath(str(tmp_path / "Strings" / "Violin Section" / "Geige A4.wav"))
    assert (first.lokey, first.hikey, first.keycenter, first.volume) == (69, 69, 69, -3.0)
    assert (soft.lokey, soft.hikey, soft.keycenter, soft.hivel) == (60, 71, 66, 62)
    assert first.release == soft.release == high.release == 0.8         # aus <global>
    assert first.seq_length == 2 and high.seq_length == 1               # ein neues <group> beginnt leer
    assert high.tune == -12.0
    assert sfz.note_number("c4") == 60 and sfz.note_number("Bb3") == 58 and sfz.note_number("c-1") == 0


def test_sampler_plays_on_the_beat_and_in_tune(tmp_path):
    tone(tmp_path / "a4.wav", 440.0, lead=0.05)
    inst = sfz.Instrument(write_sfz(tmp_path / "a.sfz", "<region> sample=a4.wav lokey=60 hikey=80 "
                                                        "pitch_keycenter=69 ampeg_release=0.2"))
    audio = sfz.render(inst, [note(72, 0.5, 1.0)])
    assert audio.shape[0] == 2 and audio.dtype == np.float32
    loud = np.flatnonzero(np.abs(audio[0]) > 0.01)
    assert abs(loud[0] / RATE - 0.5) < 0.01                             # die Stille der Aufnahme fällt weg
    assert abs(peak_hz(audio, 0.55, 0.95) - 523.25) < 3                 # C5 aus der A4-Aufnahme
    assert loud[-1] / RATE < 1.0 + 0.2 + 0.01                           # klingt in ampeg_release aus
    assert np.abs(audio[:, -50:]).max() < 0.01                          # ohne Knacks am Ende


def test_velocity_layers_round_robin_and_random_choice(tmp_path):
    for name, hz in [("leise", 440.0), ("laut", 880.0), ("zwei", 660.0)]:
        tone(tmp_path / f"{name}.wav", hz, lead=0.0)
    inst = sfz.Instrument(write_sfz(tmp_path / "x.sfz", """
<group> pitch_keycenter=69 lokey=60 hikey=80 pitch_keytrack=0
<region> sample=leise.wav lovel=0 hivel=63
<group> pitch_keycenter=69 lokey=60 hikey=80 pitch_keytrack=0 lovel=64 hivel=127 seq_length=2
<region> sample=laut.wav seq_position=1
<region> sample=zwei.wav seq_position=2
"""))
    soft = sfz.render(inst, [note(69, 0.0, 0.5, velocity=40)])
    assert abs(peak_hz(soft, 0.05, 0.45) - 440) < 5
    loud = sfz.render(inst, [note(69, 0.0, 0.5, velocity=110), note(69, 1.0, 1.5, velocity=110)])
    assert abs(peak_hz(loud, 0.05, 0.45) - 880) < 5
    assert abs(peak_hz(loud, 1.05, 1.45) - 660) < 5                     # zweiter Anschlag: die andere Aufnahme
    assert np.sqrt(np.mean(np.square(soft[:, 2205:19845]))) < np.sqrt(np.mean(np.square(loud[:, 2205:19845])))
    inst.regions = [sfz.Region("a", lorand=0.0, hirand=0.5), sfz.Region("b", lorand=0.5, hirand=1.0)]
    assert [r.sample for r in inst.pick(60, 100, chance=0.2)] == ["a"]
    assert [r.sample for r in inst.pick(60, 100, chance=0.7)] == ["b"]


def test_the_same_note_again_stops_the_old_one(tmp_path):
    tone(tmp_path / "a.wav", 440.0, lead=0.0)
    inst = sfz.Instrument(write_sfz(tmp_path / "a.sfz", "<region> sample=a.wav key=69 ampeg_release=3"))
    once = sfz.render(inst, [note(69, 0.0, 0.2)])
    twice = sfz.render(inst, [note(69, 0.0, 0.2), note(69, 0.5, 0.7)])
    assert np.abs(once[:, int(0.6 * RATE):int(0.7 * RATE)]).max() > 0.05           # ohne zweiten Ton klingt er
    # mit dem zweiten Ton ist der erste kurz danach aus: der zweite allein ist so laut wie der erste allein
    assert np.abs(twice[:, int(0.6 * RATE):int(0.7 * RATE)]).max() == pytest.approx(
        np.abs(once[:, int(0.1 * RATE):int(0.2 * RATE)]).max(), rel=0.05)


def test_missing_recordings_stay_silent(tmp_path):
    inst = sfz.Instrument(write_sfz(tmp_path / "a.sfz", "<region> sample=fehlt.wav key=60"))
    assert not np.any(sfz.render(inst, [note(60, 0.0, 0.5)]))
    with pytest.raises(ValueError):
        sfz.Instrument(write_sfz(tmp_path / "leer.sfz", "<control> default_path=x"))


# ── sample_library.py ───────────────────────────────────────────────────────────────

SECTION = {"ViolinEnsSusVib.sfz": 1000.0, "ViolaEnsSusVib.sfz": 700.0, "CelloEnsSusVib.sfz": 400.0,
           "ContrabassSusVB.sfz": 200.0, "ViolinEnsSpic.sfz": 1500.0}


def fake_library(files=SECTION):
    """SFZ-Dateien unter den Namen der echten; jede spielt einen eigenen Sinuston, egal welche Note."""
    for name, hz in files.items():
        tone(os.path.join(sample_library.FOLDER, "rec", f"{hz:.0f}.wav"), hz, seconds=3.0)
        write_sfz(sample_library.path(name), f"<region> sample=rec/{hz:.0f}.wav lokey=24 hikey=100 "
                                             "pitch_keycenter=60 pitch_keytrack=0 ampeg_release=0.1")


def strings(*notes, program=48, pan=None):
    inst = pretty_midi.Instrument(program=program, name="Strings")
    inst.notes = list(notes)
    if pan is not None:
        inst.control_changes.append(pretty_midi.ControlChange(10, pan, 0.0))
    return inst


def test_strings_are_split_into_violins_violas_cellos_and_basses():
    fake_library()
    inst = strings(note(70, 0.0, 0.8), note(55, 1.0, 1.8), note(42, 2.0, 2.8), note(30, 3.0, 3.8),
                   note(70, 4.0, 4.2))
    assert sample_library.covers(inst)
    audio = sample_library.render(inst)
    found = [peak_hz(audio, t + 0.05, t + 0.15) for t in (0.0, 1.0, 2.0, 3.0, 4.0)]
    assert found == pytest.approx([1000, 700, 400, 200, 1500], abs=15)   # der kurze Ton: Spiccato


def test_every_instrument_plays_equally_loud():
    fake_library({"ViolinEnsSusVib.sfz": 1000.0, "ViolaEnsSusVib.sfz": 700.0, "CelloEnsSusVib.sfz": 400.0,
                  "ContrabassSusVB.sfz": 200.0})
    with open(os.path.join(sample_library.FOLDER, "ViolaEnsSusVib.sfz"), "a", encoding="utf-8") as f:
        f.write(" volume=-12")                                         # leiser aufgenommen
    audio = sample_library.render(strings(note(70, 0.0, 0.8), note(55, 1.0, 1.8)))
    rms = [np.sqrt(np.mean(np.square(audio[:, int((t + 0.2) * RATE):int((t + 0.7) * RATE)]))) for t in (0.0, 1.0)]
    assert rms[0] == pytest.approx(rms[1], rel=0.1)
    assert 20 * np.log10(rms[0]) == pytest.approx(sample_library.REFERENCE_DB, abs=1.5)


def test_without_all_recordings_the_soundfont_keeps_playing():
    fake_library({"ViolinEnsSusVib.sfz": 1000.0})
    assert not sample_library.covers(strings(note(70, 0.0, 0.5)))       # Bratschen, Celli, Bässe fehlen
    assert not sample_library.covers(strings(note(70, 0.0, 0.5), program=0))
    assert sample_library.installed() == ["ViolinEnsSusVib.sfz"]
    assert "1 von" in sample_library.status()


def test_status_says_how_to_get_the_recordings():
    assert "setup_samples.py" in sample_library.status()
    assert set(sample_library.files()) >= {"ViolinEnsSusVib.sfz", "Harp.sfz", "TrumpetStac.sfz"}


def test_pan_places_a_layer_in_the_stereo_field():
    fake_library({"Harp.sfz": 500.0})
    audio = sample_library.render(strings(note(60, 0.0, 0.5), program=46, pan=20))
    assert np.abs(audio[0]).max() > 2 * np.abs(audio[1]).max()


def _midi(tmp_path, program):
    pm = pretty_midi.PrettyMIDI()
    pm.instruments.append(strings(note(72, 0.0, 1.0), note(76, 0.0, 1.0), program=program))
    path = str(tmp_path / "streicher.mid")
    pm.write(path)
    return path


def test_mixer_takes_the_recordings_and_the_switch_turns_them_off(tmp_path):
    fake_library({"SViolinVib.sfz": 1234.0})
    midi = _midi(tmp_path, 40)
    midi_zu_wav(midi, str(tmp_path / "an.wav"), samples=True)
    midi_zu_wav(midi, str(tmp_path / "aus.wav"), samples=False)
    on, _ = sf.read(str(tmp_path / "an.wav"), always_2d=True)
    off, _ = sf.read(str(tmp_path / "aus.wav"), always_2d=True)
    assert peak_hz(on.T, 0.1, 0.9) == pytest.approx(1234, abs=10)
    assert peak_hz(off.T, 0.1, 0.9) != pytest.approx(1234, abs=10)


def test_pipeline_switch_and_own_soundfont(tmp_path):
    settings = SongSettings()
    assert pipeline._render_job(settings, str(tmp_path), "strings")["samples"] is True
    assert pipeline._render_job(settings.with_updates(samples=False), str(tmp_path), "strings")["samples"] is False
    own = tmp_path / "eigener.sf2"
    own.write_bytes(b"RIFF" + bytes(64))
    job = pipeline._render_job(settings.with_updates(soundfont_pfad=str(own)), str(tmp_path), "strings")
    assert job["samples"] is False and job["library"] is False          # ein eigener SoundFont spielt alles
    assert "sfz.py" in pipeline.RENDER_CODE and "sample_library.py" in pipeline.RENDER_CODE


def test_old_settings_pointing_at_the_bundled_soundfont_keep_the_better_sounds(tmp_path):
    # wie in alten Einstellungen: der mitgelieferte SoundFont, nur in einem anderen Ordner
    elsewhere = tmp_path / "vocaloid_generator" / os.path.basename(config.SOUNDFONT_PFAD)
    elsewhere.parent.mkdir()
    with open(config.SOUNDFONT_PFAD, "rb") as src, open(elsewhere, "wb") as dst:
        dst.write(src.read())
    for path in (str(elsewhere), config.SOUNDFONT_PFAD, "C:/gibt/es/nicht/soundfont.sf2", ""):
        settings = SongSettings(soundfont_pfad=path)
        assert not settings.own_soundfont()
        job = pipeline._render_job(settings, str(tmp_path), "strings")
        assert job["samples"] is True and job["library"] is True


# ── setup_samples.py ────────────────────────────────────────────────────────────────

def _source(tmp_path, sfz_text, recordings=("Strings/Violin Section/a.wav",)):
    src = tmp_path / "quelle"
    for rel in recordings:
        tone(src / rel, 440.0, seconds=0.2)
    write_sfz(src / "Harp.sfz", sfz_text)
    return src.as_uri() + "/"


def test_setup_loads_an_instrument_with_its_recordings(tmp_path):
    quelle = _source(tmp_path, "<control> default_path=Strings\\Violin Section\\\n<region> sample=a.wav key=60")
    ziel = tmp_path / "samples"
    assert setup_samples.setup(["harp"], str(ziel), quelle)
    assert sorted(os.listdir(ziel)) == ["Harp.sfz", "LIZENZ.txt", "Strings"]
    assert (ziel / "Strings" / "Violin Section" / "a.wav").is_file()
    assert setup_samples.hole("Harp.sfz", str(ziel), quelle)             # schon da
    assert not setup_samples.setup(["Gibtsnicht"], str(ziel), quelle)


def test_setup_keeps_the_sfz_file_back_until_all_recordings_are_there(tmp_path):
    quelle = _source(tmp_path, "<region> sample=Strings/Violin Section/a.wav key=60\n<region> sample=fehlt.wav key=62")
    ziel = tmp_path / "samples"
    assert not setup_samples.hole("Harp.sfz", str(ziel), quelle)
    assert not (ziel / "Harp.sfz").exists()                             # die App nimmt es nicht halb
    assert (ziel / "Strings" / "Violin Section" / "a.wav").is_file()    # beim nächsten Mal schon da
    assert not any(f.endswith(".download") for _, _, files in os.walk(ziel) for f in files)


def test_setup_refuses_recordings_outside_its_folder(tmp_path):
    quelle = _source(tmp_path, "<region> sample=..\\..\\boese.wav key=60", recordings=())
    assert not setup_samples.hole("Harp.sfz", str(tmp_path / "samples"), quelle)
    assert not (tmp_path / "boese.wav").exists()
